#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径 A：本地中小数据文件（CSV/Excel/JSON）统计摘要 + 可视化图表。

用法:
  python local_analysis.py --inspect --input data.csv            # 只打印行/列/类型概览（路由判定用）
  python local_analysis.py --input data.csv [--outdir output]    # 产出统计摘要 md + 图表 png

路由口径：单文件、行数 <=1000（默认阈值，可 --max-rows 覆盖）且不需跨表关联时走本脚本。
"""
import argparse
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

DATE_HINT = re.compile(r'日期|时间|date|time', re.I)
NUM_UNITS = {'%', '元', '亿', '万', '美元', '港元', '日元'}


def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        for enc in ('utf-8-sig', 'utf-8', 'gbk'):
            try:
                return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError:
                continue
        raise SystemExit('ERROR 无法解码 %s（已试 utf-8/gbk）' % path)
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(path)
    if ext == '.json':
        return pd.read_json(path)
    raise SystemExit('ERROR 不支持的扩展名 %s（支持 .csv/.xlsx/.xls/.json）' % ext)


def col_kind(s):
    return ('时间' if DATE_HINT.search(str(s)) else '数值' if pd.api.types.is_numeric_dtype(s) else '文本')


def inspect(path):
    df = load(path)
    print('rows=%d' % len(df))
    print('cols=%d' % len(df.columns))
    for c in df.columns:
        print('  col %s | type=%s | kind=%s | nonnull=%d/%d' % (
            c, str(df[c].dtype), col_kind(df[c]), int(df[c].notna().sum()), len(df)))
    print('preview=')
    print(df.head(3).to_string())


def main():
    ap = argparse.ArgumentParser(description='本地数据文件分析')
    ap.add_argument('--input', required=True, help='CSV/Excel/JSON 文件')
    ap.add_argument('--outdir', default='output')
    ap.add_argument('--max-rows', type=int, default=1000)
    ap.add_argument('--inspect', action='store_true', help='仅打印概要，供路由判定')
    a = ap.parse_args()

    if not os.path.exists(a.input):
        sys.exit('ERROR 找不到输入文件 %s' % a.input)
    if a.inspect:
        inspect(a.input)
        return

    df = load(a.input)
    if len(df) > a.max_rows:
        print('WARN 行数 %d 超过阈值 %d，按路径 A 处理可能偏大；如需聚合/跨表考虑路径 B'
              % (len(df), a.max_rows))

    stem = re.sub(r'[^\w一-鿿-]+', '_', os.path.splitext(os.path.basename(a.input))[0])
    os.makedirs(a.outdir, exist_ok=True)

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    date_cols = [c for c in df.columns if col_kind(df[c]) == '时间']
    time_series = bool(date_cols) and bool(num_cols)
    rows, cols = df.shape
    dup = int(df.duplicated().sum())

    lines = []
    lines.append('# 数据概览 · %s' % stem)
    lines.append('')
    lines.append('- 文件：`%s`；行数 %d，列数 %d；重复行 %d' % (os.path.basename(a.input), rows, cols, dup))
    lines.append('- 时间列：%s；数值列：%s' % ('、'.join(date_cols) or '无', '、'.join(num_cols[:8]) + ('…' if len(num_cols) > 8 else '') or '无'))
    lines.append('')

    lines.append('## 各列概览')
    lines.append('| 列 | 类型 | 缺失 | 非空 | 类别数 |')
    lines.append('| --- | --- | --- | --- | --- |')
    for c in df.columns:
        lines.append('| %s | %s | %d | %d | %d |' % (c, str(df[c].dtype), int(df[c].isna().sum()), int(df[c].notna().sum()), int(df[c].nunique())))
    lines.append('')

    if num_cols:
        lines.append('## 数值统计')
        lines.append('| 列 | 均值 | 标准差 | 最小 | 中位数 | 最大 |')
        lines.append('| --- | --- | --- | --- | --- | --- |')
        for c in num_cols[:12]:
            s = df[c].describe()
            lines.append('| %s | %s | %s | %s | %s | %s |' % (
                c, _n(s['mean']), _n(s['std']), _n(s['min']), _n(s['50%']), _n(s['max'])))
        lines.append('')

    charts = []
    try:
        if time_series:
            x = df[date_cols[0]]
            xs = pd.to_datetime(x, errors='coerce')
            ts = df.assign(__x=xs.fillna(pd.to_datetime(x, errors='coerce').min())).sort_values('__x')
            for c in num_cols[:2]:
                fig, ax = plt.subplots(figsize=(9, 4.5))
                ax.plot(ts['__x'], ts[c])
                ax.set_title('%s 走势' % c)
                ax.set_xlabel(date_cols[0])
                ax.grid(alpha=.3)
                p = os.path.join(a.outdir, 'chart_%s_%s.png' % (stem, _slug(c)))
                fig.savefig(p, dpi=110, bbox_inches='tight')
                plt.close(fig)
                charts.append(p)
        for c in num_cols[:4]:
            fig, ax = plt.subplots(figsize=(6.5, 4))
            df[c].dropna().hist(ax=ax, bins=30)
            ax.set_title('%s 分布' % c)
            p = os.path.join(a.outdir, 'hist_%s_%s.png' % (stem, _slug(c)))
            fig.savefig(p, dpi=110, bbox_inches='tight')
            plt.close(fig)
            charts.append(p)
        if not charts and num_cols:
            c = num_cols[0]
            fig, ax = plt.subplots(figsize=(6.5, 4))
            df[c].value_counts().head(15).plot.bar(ax=ax)
            ax.set_title('%s 频次 Top15' % c)
            p = os.path.join(a.outdir, 'bar_%s_%s.png' % (stem, _slug(c)))
            fig.savefig(p, dpi=110, bbox_inches='tight')
            plt.close(fig)
            charts.append(p)
    except Exception as e:  # 图表失败不影响摘要
        print('WARN 绘图失败：%s' % e)

    if charts:
        lines.append('## 图表')
        for p in charts:
            lines.append('- ![chart](%s)' % os.path.basename(p))
        lines.append('')

    md_path = os.path.join(a.outdir, 'summary_%s.md' % stem)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('OK 摘要 -> %s' % md_path)
    for p in charts:
        print('OK 图表 -> %s' % p)
    print('概要：%d 行 × %d 列；数值列 %d 个%s' % (rows, cols, len(num_cols),
          '；检测到时间序列' if time_series else ''))


def _slug(c):
    return re.sub(r'[^\w一-鿿-]+', '_', str(c))[:24]


def _n(x):
    return 'NA' if pd.isna(x) else ('%.4f' % float(x))


if __name__ == '__main__':
    main()

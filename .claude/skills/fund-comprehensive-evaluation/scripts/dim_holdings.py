#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子代理 2：持仓分析。读最新持仓报告（+ 上期可选）-> 行业分布、个股集中度、重仓股变动、换手近似。

用法:
  python dim_holdings.py --fund 999999 --latest temp/_inputs/holdings_latest.csv \
      --prev temp/_inputs/holdings_prev.csv --out temp/holdings_999999.md

列口径：持仓 csv 需含 代码/名称 与一个权重列（列名含 '占净值' 或 '比例'，数值为百分比，如 9.5=9.5%）；可选 '行业' 列。
实际换手率只在半年报/年报披露——文件没给就从"前十大重仓重叠"给近似，并如实标注。
"""
import argparse
import os
import re
import sys

import pandas as pd


def load(path):
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    sys.exit('ERROR 无法解码 %s' % path)


def wcol(df):
    hit = [c for c in df.columns if re.search(r'占净值|比例|权重|占比', str(c))]
    return hit[0] if hit else df.columns[-1]


def normalize(df):
    c = wcol(df)
    w = pd.to_numeric(df[c], errors='coerce')
    keep = w.notna()
    out = df[keep].copy()
    out['__w'] = w[keep].astype(float)
    return out


def ind_dist(df):
    if '行业' not in df.columns:
        return None
    return df.groupby('行业')['__w'].sum().sort_values(ascending=False)


def topN(df, n):
    return df['__w'].sort_values(ascending=False).head(n).sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fund', required=True)
    ap.add_argument('--latest', required=True)
    ap.add_argument('--prev')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    lat = normalize(load(a.latest))
    if lat.empty:
        sys.exit('ERROR %s 无有效权重列（需列名含 占净值/比例/权重）' % a.latest)
    lines = ['# 持仓分析 · %s' % a.fund, '',
             '- 数据来源：最新持仓报告 %s（披露 %d 行）' % (os.path.basename(a.latest), len(lat)), '']

    total_hold = lat['__w'].sum()
    lines += ['## 集中度（占净值比，%）', '', '| 口径 | 数值 |', '| --- | --- |',
              '| 前 1 大 | %.2f |' % topN(lat, 1),
              '| 前 5 大 | %.2f |' % topN(lat, 5),
              '| 前 10 大 | %.2f |' % topN(lat, 10)]
    if len(lat) < 10:
        lines.append('| 披露行数 | %d（不足 10，汇总为披露合计） |' % len(lat))
    lines.append('')

    ind = ind_dist(lat)
    if ind is not None:
        lines += ['## 行业分布（占净值比，%）', '',
                  '| 行业 | 占比 |', '| --- | --- |'] + \
                 ['| %s | %.2f |' % (k, v) for k, v in ind.head(12).items()] + ['']
    else:
        lines += ['## 行业分布', '', '- 未提供 行业 列，跳过。', '']

    lines += ['## 重仓股变动（前十大）', '']
    if a.prev and os.path.exists(a.prev):
        pre = normalize(load(a.prev))
        codes = None
        for k in ('代码', 'code', '股票代码', '证券代码'):
            if k in lat.columns:
                codes = k
                break
        if codes:
            cur = set(lat[codes].astype(str).head(10))
            old = set(pre[codes].astype(str).head(10))
            add = cur - old
            drop = old - cur
            overlap = len(cur & old)
            lines += ['- 较上期前十大：新增 %d 只 / 退出 %d 只 / 重合 %d 只。' % (len(add), len(drop), overlap),
                      '- 换手率近似 = 名单变动程度（真实换手以半年报/年报披露为准）。']
            add_names = lat[lat[codes].astype(str).isin(add)]['名称'].tolist() if '名称' in lat.columns else list(add)
            drop_names = pre[pre[codes].astype(str).isin(drop)]['名称'].tolist() if '名称' in pre.columns else list(drop)
            lines += ['- 新增：%s' % ('、'.join(str(x) for x in add_names) or '无')]
            lines += ['- 退出：%s' % ('、'.join(str(x) for x in drop_names) or '无')]
        else:
            lines += ['- 无 代码 列，无法与上期比对名单；换手率待半年报披露值。']
    else:
        lines += ['- 未提供上期报告（--prev），重仓变动与换手率待补。']

    lines += ['', '## 口径与限制', '',
              '- 集中度/行业用披露持仓市值占净值比加总；基金定期报告通常只披露前十大，可能低估真实集中度。',
              '- 换手率为名单近似，非披露口径。']

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('%s 前10大集中度 %.2f%% / 披露合计 %.2f%% / %s'
          % (a.fund, topN(lat, 10), total_hold, '有行业分布' if ind is not None else '无行业列'))
    print('OK -> %s' % a.out)


if __name__ == '__main__':
    main()

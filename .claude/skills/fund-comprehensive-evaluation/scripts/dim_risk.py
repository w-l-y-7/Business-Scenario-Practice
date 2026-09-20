#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子代理 3：风险评估。读净值 + 基准 -> 年化波动、Beta、相关系数、跟踪误差、历史 VaR。

用法:
  python dim_risk.py --fund 999999 --nav temp/_inputs/nav.csv --bench temp/_inputs/bench.csv \
      --out temp/risk_999999.md

列口径：nav/bench 第 1 列日期、第 2 列数值。无基准时 Beta/跟踪误差给 N/A（标注）。
VaR 用历史分位法：单日 95%/99%，占净值百分比；附"持有期为 1 日"提示。
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd


def load(path):
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    sys.exit('ERROR 无法解码 %s' % path)


def series(df):
    v = pd.to_numeric(df.iloc[:, 1], errors='coerce')
    keep = v.notna()
    return df.iloc[:, 0].astype(str)[keep].reset_index(drop=True), v[keep].astype(float).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fund', required=True)
    ap.add_argument('--nav', required=True)
    ap.add_argument('--bench', help='基准指数 csv（可选）')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    _, nav = series(load(a.nav))
    r = nav.pct_change().dropna()
    if len(r) < 30:
        sys.exit('ERROR 净值样本过少（%d 个收益日），无法做风险分析' % len(r))
    vol_ann = r.std() * np.sqrt(252) * 100
    var95 = float(-np.percentile(r.dropna(), 5)) * 100
    var99 = float(-np.percentile(r.dropna(), 1)) * 100

    lines = ['# 风险分析 · %s' % a.fund, '',
             '- 净值样本：%d 个收益日' % len(r),
             '- VaR 口径：历史分位法，持有期 1 个交易日，占净值百分比。', '']

    if a.bench and os.path.exists(a.bench):
        _, bv = series(load(a.bench))
        rb = bv.pct_change().dropna()
        j = pd.concat([r.reset_index(drop=True), rb.reset_index(drop=True)], axis=1, keys=['f', 'b']).dropna()
        if len(j) < 30:
            lines += ['## 基准相关', '', '- 基准样本不足（%d 天对齐），Beta/跟踪误差 N/A。']
        else:
            beta = float(np.cov(j['f'], j['b'])[0, 1] / np.var(j['b'])) if np.var(j['b']) > 0 else float('nan')
            corr = float(np.corrcoef(j['f'], j['b'])[0, 1])
            te = float((j['f'] - j['b']).std() * np.sqrt(252)) * 100
            lines += ['## 相对基准（%s）' % os.path.basename(a.bench), '', '| 指标 | 数值 |', '| --- | --- |',
                      '| Beta | %.2f |' % beta, '| 与基准相关系数 | %.2f |' % corr,
                      '| 年化跟踪误差 | %.2f%% |' % te, '']
    else:
        lines += ['## 相对基准', '', '- 未提供基准（--bench），Beta/跟踪误差 N/A。', '']

    lines += ['## 风险指标', '', '| 指标 | 数值 |', '| --- | --- |',
              '| 年化波动率 | %.2f%% |' % vol_ann,
              '| 单日 VaR(95%%) | %.2f%% |' % var95,
              '| 单日 VaR(99%%) | %.2f%% |' % var99, '',
              '## 口径与限制', '',
              '- VaR 为历史分位法，未考虑极端尾部与相关性突变；供观察，非风控限额结论。']

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('%s 年化波动 %.2f%% / 单日VaR95 %.2f%% / 99 %.2f%% / 基准%s'
          % (a.fund, vol_ann, var95, var99, '有' if a.bench and os.path.exists(a.bench) else '无'))
    print('OK -> %s' % a.out)


if __name__ == '__main__':
    main()

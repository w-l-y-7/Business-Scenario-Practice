#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子代理 1：业绩分析。读净值序列 -> 区间/年化收益、夏普、最大回撤、（可选）同类排名。

用法:
  python dim_performance.py --fund 999999 --nav temp/_inputs/nav.csv --out temp/performance_999999.md
  python dim_performance.py --fund 999999 --nav temp/_inputs/nav.csv --rf 0.02 --peers temp/_peers --out ...

列口径：nav.csv 第 1 列日期、第 2 列单位净值（数字）。--peers 目录下每只同类基金各一个同格式 csv。
夏普默认按 rf=2%（年化）估算，--rf 覆盖。同类排名=区间年化收益降序。
"""
import argparse
import os
import sys
import glob

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


def annualized(nav):
    if len(nav) < 2 or nav.iloc[0] <= 0:
        return float('nan')
    return (nav.iloc[-1] / nav.iloc[0]) ** (252 / len(nav)) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fund', required=True)
    ap.add_argument('--nav', required=True)
    ap.add_argument('--rf', type=float, default=0.02)
    ap.add_argument('--peers', help='同类基金净值目录（可选）')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    if not os.path.exists(a.nav):
        sys.exit('ERROR 找不到 %s' % a.nav)
    dates, nav = series(load(a.nav))
    ret = nav.pct_change().dropna()
    n = len(nav)
    if n < 10:
        sys.exit('ERROR 净值样本过少（%d 条），无法做业绩分析' % n)

    total = (nav.iloc[-1] / nav.iloc[0] - 1) * 100
    ann = annualized(nav) * 100
    vol = ret.std() * np.sqrt(252) * 100
    sharpe = (ann - a.rf * 100) / vol if vol and vol > 0 else float('nan')
    cum = nav / nav.cummax()
    mdd = float((cum - 1).min()) * 100
    win_days = float((ret > 0).mean()) * 100

    peer_line = '同类排名：N/A（未给 --peers 同类基金池）'
    if a.peers and os.path.isdir(a.peers):
        mine = annualized(nav)
        peers = []
        for f in glob.glob(os.path.join(a.peers, '*.csv')):
            try:
                _, pnav = series(load(f))
                if len(pnav) >= 30:
                    peers.append(annualized(pnav))
            except Exception:
                pass
        if peers:
            rank = 1 + sum(1 for x in peers if x is not None and x > mine)
            peer_line = '同类排名：%d / %d（区间年化收益降序，含本基金）' % (rank, len(peers) + 1)

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join([
            '# 业绩分析 · %s' % a.fund, '',
            '- 数据区间：%s ~ %s（%d 个交易日，净值序列）' % (dates.iloc[0], dates.iloc[-1], n),
            '- 假设：无风险利率 rf=%g%%（年化，--rf 可覆盖）' % (a.rf * 100),
            '', '## 指标', '',
            '| 指标 | 数值 |', '| --- | --- |',
            '| 区间总收益 | %+.2f%% |' % total,
            '| 年化收益 | %+.2f%% |' % ann,
            '| 年化波动 | %.2f%% |' % vol,
            '| 夏普比率 | %.2f |' % sharpe,
            '| 最大回撤 | %.2f%% |' % mdd,
            '| 上涨交易日占比 | %.1f%% |' % win_days,
            '| %s |' % peer_line.replace('|', '\\|'), '',
            '## 口径与限制', '',
            '- 收益未含分红再投与费率；夏普用年化超额收益 / 年化波动估算。',
            '- 同类排名仅当提供 --peers 同类池才有意义；无池不硬排。',
        ]))
    print('%s 区间 %+.2f%% / 年化 %+.2f%% / 夏普 %.2f / 最大回撤 %.2f%% / 同类 %s'
          % (a.fund, total, ann, sharpe, mdd, peer_line.split('：', 1)[-1].replace('（', '').rstrip('）')))
    print('OK -> %s' % a.out)


if __name__ == '__main__':
    main()

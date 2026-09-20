#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取数（混合策略）：基金历史净值（+ 可选基准指数）写入 temp/_inputs/。

用法:
  python fetch_fund.py --fund 000001 --outdir temp/_inputs
  python fetch_fund.py --fund 000001 --bench 000300 --outdir temp/_inputs   # 000300=沪深300

先试 akshare（东方财富）；拉不到就友好退出并提示改用手动提供文件，不伪造。
本机东财接口常被拒——这是正常降级路径，不是 bug。
"""
import argparse
import datetime as dt
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fund', required=True, help='基金 6 位代码，如 000001')
    ap.add_argument('--bench', help='基准指数代码，如 000300（沪深300）')
    ap.add_argument('--outdir', default='temp/_inputs')
    a = ap.parse_args()

    code = a.fund.strip()
    if not (code.isdigit() and len(code) == 6):
        sys.exit('ERROR 基金代码应为 6 位数字，当前: %s' % code)

    try:
        import akshare as ak
    except ImportError:
        sys.exit('ERROR 未安装 akshare。请 `pip install -U akshare`，或手动提供 temp/_inputs/nav.csv。')

    os.makedirs(a.outdir, exist_ok=True)

    # ---- 基金单位净值（带一次重试）----
    nav_df = None
    last_err = None
    for attempt in (1, 2):
        try:
            nav_df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
            break
        except Exception as e:
            last_err = e
            if attempt == 1:
                print('WARN 东财净值获取失败（%s），重试一次…' % type(e).__name__)
    if nav_df is None or nav_df.empty:
        sys.exit('ERROR 两次尝试均无法获取 %s 净值（%s）。本机东财接口常被拒：请改由你提供 '
                 'temp/_inputs/nav.csv（列: date,nav），再继续四维评估。'
                 % (code, type(last_err).__name__ if last_err else '空数据'))

    nav = nav_df.rename(columns={nav_df.columns[0]: 'date', nav_df.columns[1]: 'nav'})[['date', 'nav']]
    nav.to_csv(os.path.join(a.outdir, 'nav.csv'), index=False, encoding='utf-8-sig')
    print('OK 净值 %d 条 -> %s/nav.csv' % (len(nav), a.outdir))

    # ---- 基准指数（best-effort，失败不阻塞）----
    if a.bench:
        try:
            idx = ak.index_zh_a_hist(symbol=a.bench, period='daily',
                                     start_date=(dt.date.today() - dt.timedelta(days=750)).strftime('%Y%m%d'),
                                     end_date=dt.date.today().strftime('%Y%m%d'))
            b = idx.rename(columns={idx.columns[0]: 'date', idx.columns[1]: 'value'})[['date', 'value']]
            b.to_csv(os.path.join(a.outdir, 'bench.csv'), index=False, encoding='utf-8-sig')
            print('OK 基准 %s 已存 bench.csv' % a.bench)
        except Exception as e:
            print('WARN 基准 %s 获取失败（%s）。如需风险维跟踪误差，请提供 temp/_inputs/bench.csv。'
                  % (a.bench, type(e).__name__))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径 C：实时行情需求 -> akshare(东财) 取 A股实时快照 + 近 N 交易日历史对比。

用法:
  python api_fetch.py --symbol 600519 [--days 120] [--outdir output]

说明：实时快照用 ak.stock_bid_ask_em（轻量，个股买卖盘+最新价）；历史用 ak.stock_zh_a_hist。
若实时接口失败（网络/休市），自动降级为"截至最近收盘"并在输出中标注，不影响产出。
数据来源为 akshare（东方财富），仅供分析演示，非投资建议。
"""
import argparse
import datetime as dt
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False


def fmt(x):
    try:
        return None if x in (None, '', 'nan') else '%.2f' % float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description='A股实时 + 历史对比')
    ap.add_argument('--symbol', required=True, help='A股 6 位代码，如 600519')
    ap.add_argument('--days', type=int, default=120)
    ap.add_argument('--outdir', default='output')
    a = ap.parse_args()

    sym = re.sub(r'^(sh|sz|bj)', '', str(a.symbol).lower()).strip()
    if not re.fullmatch(r'\d{6}', sym):
        sys.exit('ERROR 请给 6 位 A股代码，当前: %s' % sym)

    import akshare as ak
    today = dt.date.today()
    start = (today - dt.timedelta(days=max(a.days * 2, 90))).strftime('%Y%m%d')
    end = today.strftime('%Y%m%d')

    # ---- 历史（带一次重试；网络失败就友好退出，不伪造数据）----
    hist = None
    last_err = None
    for attempt in (1, 2):
        try:
            hist = ak.stock_zh_a_hist(symbol=sym, period='daily', start_date=start, end_date=end, adjust='')
            break
        except Exception as e:
            last_err = e
            if attempt == 1:
                print('WARN 东财历史行情获取失败（%s），重试一次…' % type(e).__name__)
    if hist is None or hist.empty:
        sys.exit('ERROR 两次尝试均无法从东财获取 %s 历史行情（%s）。请检查网络后重试；本脚本不会在无网时伪造实时数据。'
                 % (sym, type(last_err).__name__ if last_err else '数据为空'))
    hist = hist.sort_values('日期').reset_index(drop=True)
    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) >= 2 else last
    close_last = float(last['收盘'])
    close_prev = float(prev['收盘'])
    day_pct = (close_last / close_prev - 1) * 100 if close_prev else 0.0
    win_pct = (close_last / float(hist.iloc[0]['收盘']) - 1) * 100
    win_hi = float(hist['最高'].max())
    win_lo = float(hist['最低'].min())
    n = len(hist)

    # ---- 实时快照（失败降级）----
    realtime = {}
    rt_note = ''
    try:
        bd = ak.stock_bid_ask_em(symbol=sym)
        for _, r in bd.iterrows():
            realtime[str(r['item'])] = r['value']
        rt_note = '实时接口成功'
    except Exception as e:
        rt_note = '实时接口不可用（%s），改用最近收盘' % type(e).__name__

    os.makedirs(a.outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(pd.to_datetime(hist['日期']), hist['收盘'], label='收盘')
    ax.set_title('%s 近 %d 个交易日收盘' % (sym, n))
    ax.grid(alpha=.3)
    fig.autofmt_xdate()
    chart = os.path.join(a.outdir, 'realtime_%s.png' % sym)
    fig.savefig(chart, dpi=110, bbox_inches='tight')
    plt.close(fig)

    lines = ['# 实时与历史行情 · %s' % sym, '', '- 数据截至：%s（共 %d 个交易日）' % (last['日期'], n)]
    lines.append('- 状态：%s' % rt_note)
    lines.append('')
    if realtime:
        key = next((k for k in ('最新', '最新价') if k in realtime), None)
        lines.append('## 实时快照')
        lines.append('| 项目 | 数值 |')
        lines.append('| --- | --- |')
        for k in ('最新', '涨幅', '今开', '最高', '最低', '昨收', '买一', '卖一'):
            if k in realtime:
                lines.append('| %s | %s |' % (k, realtime[k]))
        lines.append('')
    lines.append('## 窗口统计（近 %d 个交易日）' % n)
    lines.append('')
    lines.append('- 最新收盘：%s（前一交易日 %s，日涨跌 %+.2f%%）' % (fmt(close_last), fmt(close_prev), day_pct))
    lines.append('- 窗口首日收盘：%s → 末收盘 %s，区间涨跌 **%+.2f%%**' % (fmt(float(hist.iloc[0]['收盘'])), fmt(close_last), win_pct))
    lines.append('- 窗口最高 %s / 最低 %s' % (fmt(win_hi), fmt(win_lo)))
    lines.append('')
    lines.append('## 图表')
    lines.append('')
    lines.append('![收盘走势](%s)' % os.path.basename(chart))
    lines.append('')
    lines.append('> 数据来源：akshare（东方财富），仅供分析演示，非投资建议。')

    md = os.path.join(a.outdir, 'realtime_%s_%s.md' % (sym, today.strftime('%Y%m%d')))
    with open(md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print('%s %s（%s）' % (sym, rt_note, last['日期']))
    print('最新收盘 %s / 日涨跌 %+.2f%% / 窗口 %d 日涨跌 %+.2f%%' % (fmt(close_last), day_pct, n, win_pct))
    print('OK 报告 -> %s' % md)
    print('OK 图表 -> %s' % chart)


if __name__ == '__main__':
    main()

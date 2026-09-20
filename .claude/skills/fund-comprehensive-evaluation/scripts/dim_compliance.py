#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子代理 4：合规检查（基金口径）。用披露持仓核对双十集中度 + 关联线索 + 行业禁投 + 信披完整性。

用法:
  python dim_compliance.py --fund 999999 --latest temp/_inputs/holdings_latest.csv \
      --meta temp/_inputs/meta.json --out temp/compliance_999999.md

--meta.json 可选字段: {"name","type","related_terms":["示例集团"],"blocked_industry":["房地产"]}
口径：
- 双十用"单一证券市值 ≤ 基金净值 10%"；定期报告只披露前十大时，此检查是**代理口径**，完整持仓的精确合规需监管报送数据。
- 关联线索/禁投行业只能做字符串初筛；命中即标"待人工"，不自行定论（证据式，与 investment-compliance 同口径）。
- 信披完整性：披露行数 <10 或缺失报告文件时提示，不以缺料当合规。
"""
import argparse
import json
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fund', required=True)
    ap.add_argument('--latest', required=True)
    ap.add_argument('--meta', help='meta.json（可选）')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    meta = {}
    if a.meta and os.path.exists(a.meta):
        with open(a.meta, encoding='utf-8') as f:
            meta = json.load(f)

    df = load(a.latest)
    wc = wcol(df)
    w = pd.to_numeric(df[wc], errors='coerce')
    df = df[w.notna()].copy()
    df['__w'] = w[w.notna()].astype(float)
    if df.empty:
        sys.exit('ERROR %s 无有效持仓权重列' % a.latest)
    rows = len(df)

    name_col = '名称' if '名称' in df.columns else (df.columns[1] if len(df.columns) > 1 else '标的')
    code_col = next((c for c in ('代码', '股票代码', '证券代码') if c in df.columns), None)

    # 1) 双十（披露代理口径）
    breach = df[df['__w'] > 10]
    # 2) 关联线索（字符串初筛）
    terms = meta.get('related_terms', [])
    rel_hits = []
    if terms:
        pat = '|'.join(re.escape(t) for t in terms)
        m = df[df[name_col].astype(str).str.contains(pat, regex=True, na=False)]
        rel_hits = m[name_col].tolist()
    # 3) 行业禁投
    blk = meta.get('blocked_industry', [])
    ind_hits = []
    if blk and '行业' in df.columns:
        ind_hits = df[df['行业'].astype(str).isin(blk)]['行业'].tolist()

    lines = ['# 合规检查 · %s' % a.fund, '',
             '- 依据口径：公募"双十"（单一证券市值 ≤ 基金净值 10%）；关联/禁投为字符串初筛。'
             '本技能用**披露持仓**做代理检查，非监管报送数据，精确结论需合规岗结合完整持仓核验。', '']

    wlabel = wc if ('%' in str(wc) or '占净值' in str(wc)) else wc + '(占净值%)'
    lines += ['## 双十集中度（披露前十大代理）', '',
              '| %s | %s | 双十(>10%%) |' % (name_col, wlabel),
              '| --- | --- | --- |'] + \
             ['| %s | %.2f | %s |' % (str(row[name_col]), row['__w'], '⚠️ 超限' if row['__w'] > 10 else '合规')
              for _, row in df.sort_values('__w', ascending=False).iterrows()]
    lines += ['', '- 超限数量：**%d** 只。' % len(breach)]

    lines += ['', '## 关联交易线索', '']
    lines += ['- 疑似关联（命中 related_terms）：%s'
              % ('、'.join(rel_hits) if rel_hits else '无（未提供名单则本项为 N/A）'), '']

    lines += ['## 行业禁投', '']
    lines += ['- 命中 blocked_industry：%s' % ('、'.join(ind_hits) if ind_hits else '无')]

    lines += ['', '## 信息披露完整性', '',
              '- 本报告披露持仓 %d 行；%s。' % (
                  rows,
                  '≥10，为常规前十大披露（代理口径）' if rows >= 10
                  else '不足前十大，覆盖不完整，结论置信度低'),
              '- 未含报告期/净值规模字段时，无法做全组合比例复核。']

    lines += ['', '## 口径与限制', '',
              '- 关联与禁投命中都只是**待人工确认线索**，不由本脚本定论（证据式原则）。',
              '- 双十精确检查需完整持仓 + 管理人全产品口径（第二条"双十"），本脚本不覆盖后者。']

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('%s 双十超限 %d 只 / 关联疑似 %d / 禁投命中 %d / 披露 %d 行'
          % (a.fund, len(breach), len(rel_hits), len(ind_hits), rows))
    print('OK -> %s' % a.out)


if __name__ == '__main__':
    main()

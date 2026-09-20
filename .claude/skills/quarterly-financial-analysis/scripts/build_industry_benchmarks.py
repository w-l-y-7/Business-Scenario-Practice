# -*- coding: utf-8 -*-
"""行业中位数基准生成器（权威化 industry_benchmarks.md，替代内置示例占位值）。

口径：
- 行业分类 = 申万一级（index_component_sw 成分，权威、可复现）。
- 可比期 = 最近一个完整披露年度（默认 FY2025，12-31 累计口径）。
- 毛利率  ：东财「业绩报表」(stock_yjbb_em) 销售毛利率，全市场单表一次取回。
- 净利率/加权ROE/资产负债率/流动比率：新浪「财务指标」(stock_financial_analysis_indicator) 的
  销售净利率(%)/加权净资产收益率(%)/资产负债率(%)/流动比率 的 FY(12-31) 行。
- 中位数对同一可比样本（随机抽样成分股，--sample 可调）计算；样本数、失败数随表标注。

用法：
  python build_industry_benchmarks.py                      # 内置行业清单 -> 覆盖 references/industry_benchmarks.md
  python build_industry_benchmarks.py --industries 801120  # 只生成指定申万一级
  python build_industry_benchmarks.py --fy 2025 --sample 24 --seed 42 --outfile <path>

说明：本机新浪/申万/东财业绩报表接口可达即可用；逐股东财三大报表被拒不影响本脚本。
输出 markdown 供 SKILL.md 第 3 步逐行业读取。
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import time

import numpy as np
import pandas as pd

try:
    import akshare as ak
except ImportError:
    sys.exit("未安装 akshare：pip install -U akshare")

# (申万一级代码, 名称)：与 sw_index_first_info 一致；排除金融业（SKILL 面向非金融上市公司）。
DEFAULT_INDUSTRIES = [
    ("801120", "食品饮料"), ("801730", "电力设备"), ("801080", "电子"), ("801030", "基础化工"),
    ("801880", "汽车"), ("801150", "医药生物"), ("801890", "机械设备"), ("801050", "有色金属"),
    ("801750", "计算机"), ("801770", "通信"), ("801760", "传媒"), ("801740", "国防军工"),
    ("801110", "家用电器"), ("801710", "建筑材料"), ("801950", "煤炭"), ("801960", "石油石化"),
]

SINA_COLS = {
    "net_margin": "销售净利率(%)",
    "roe_w": "加权净资产收益率(%)",
    "debt_ratio": "资产负债率(%)",
    "current_ratio": "流动比率",
}


def num(v):
    try:
        f = pd.to_numeric(v, errors="coerce")
        return None if pd.isna(f) else float(f)
    except Exception:
        return None


def fetch_sina(code, fy):
    """取一只股票 FY(fy-12-31) 累计行的 4 个指标。失败返回 None。"""
    last_err = None
    for attempt in (1, 2):
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year=str(fy))
            if df is None or df.empty:
                return None
            row = df[df["日期"].astype(str).str.startswith(f"{fy}-12")]
            if row.empty:
                return None
            r = row.iloc[0]
            return {k: num(r.get(c)) for k, c in SINA_COLS.items()}
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    return None


def median(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return float(np.median(vals))


def fmt_pct(x):
    return "—" if x is None else f"{x:.1f}"


def fmt_x(x):
    return "—" if x is None else f"{x:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--industries", nargs="*", default=None,
                    help="申万一级代码列表（默认内置 16 个非金融行业）")
    ap.add_argument("--fy", type=int, default=2025)
    ap.add_argument("--sample", type=int, default=24, help="每行业抽样成分股数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outfile", default=None,
                    help="输出 markdown 路径（默认覆盖 <skill>/references/industry_benchmarks.md）")
    a = ap.parse_args()

    if a.industries:
        inds = [(c[:6].split(".")[0], c) for c in a.industries]
        # 用 code 查名称（来自 sw_index_first_info）
        meta = None
        try:
            meta = ak.sw_index_first_info()
        except Exception:
            pass
        name_of = {str(r["行业代码"]).split(".")[0]: r["行业名称"] for _, r in meta.iterrows()} if meta is not None else {}
        inds = [(c, name_of.get(c, c)) for c in a.industries]
    else:
        inds = DEFAULT_INDUSTRIES

    outfile = a.outfile or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "industry_benchmarks.md")
    outfile = os.path.abspath(outfile)

    # 1) 东财业绩报表：全市场 FY 毛利率（一次调用，按股票代码索引）
    gm_by_code = {}
    try:
        yj = ak.stock_yjbb_em(date=f"{a.fy}1231")
        if yj is not None and not yj.empty:
            code = "股票代码" if "股票代码" in yj.columns else yj.columns[1]
            gm_col = "销售毛利率" if "销售毛利率" in yj.columns else None
            if gm_col:
                for _, r in yj.iterrows():
                    v = num(r.get(gm_col))
                    if v is not None:
                        gm_by_code[str(r[code]).zfill(6)] = v
    except Exception as e:
        print(f"[warn] yjbb 毛利率取数失败：{type(e).__name__}: {e}")

    random.seed(a.seed)
    lines = [
        "# 行业基准表（申万一级行业中位数，FY{} 年度）".format(a.fy),
        "",
        "> **数据来源与口径（自算，非第三方统计机构官方中位数）**",
        f"> - 行业分类：申万一级行业（`index_component_sw` 成分）；可比期：{a.fy} 完整年度（12-31 累计）。",
        "> - 毛利率：东方财富「业绩报表」销售毛利率；净利率/加权ROE/资产负债率/流动比率：新浪「财务指标」年报行。",
        "> - 中位数对每行业**随机抽样成分股**计算，样本数与失败数见各表；数值取自公司定期报告口径，未经专业数据复核，仅作同业对比参考。",
        f"> - 生成时间：{dt.date.today().isoformat()}。用 `scripts/build_industry_benchmarks.py` 可重算/扩行业。",
        "",
        "用法：与公司对比时，季报/中报场景请按 SKILL.md 第 3 步规则选用公司 TTM 或最近年度口径。",
        "",
    ]
    footer = []

    for code, iname in inds:
        print(f"[build] {iname}({code}) …")
        try:
            comp = ak.index_component_sw(symbol=code)
        except Exception as e:
            print(f"[skip] {iname} 成分取数失败：{type(e).__name__}: {e}")
            footer.append(f"- **{iname}**：成分取数失败，未生成。")
            continue
        if comp is None or comp.empty:
            footer.append(f"- **{iname}**：无成分数据，未生成。")
            continue
        members = [str(x).zfill(6) for x in comp.iloc[:, 1].tolist()]
        members = [m for m in members if re.fullmatch(r"\d{6}", m)]
        universe = members if len(members) <= a.sample else random.sample(members, a.sample)
        if not universe:
            footer.append(f"- **{iname}**：成分列表为空。")
            continue

        rows = {}
        fails = 0
        for m in universe:
            s = fetch_sina(m, a.fy)
            if s is None:
                fails += 1
                continue
            s["gross_margin"] = gm_by_code.get(m)
            rows[m] = s
        valid = {k: v for k, v in rows.items() if any(x is not None for x in v.values())}
        n = len(valid)
        print(f"   样本 {n}/{len(universe)}（失败 {fails}）")
        if n < 8:
            footer.append(f"- **{iname}**：有效样本仅 {n} 家，样本不足未生成。")
            continue

        med = {k: median([v[k] for v in valid.values()]) for k in
               ("gross_margin", "net_margin", "roe_w", "debt_ratio", "current_ratio")}
        lines += [
            f"## {iname}（{code}）",
            "",
            f"| 指标 | 单位 | 行业中位数 | 数值越高越好 | 口径说明 |",
            f"| --- | --- | --- | --- | --- |",
            f"| 毛利率 | % | {fmt_pct(med['gross_margin'])} | 是 | {a.fy}年度·样本{n}家 |",
            f"| 净利率 | % | {fmt_pct(med['net_margin'])} | 是 | {a.fy}年度·样本{n}家 |",
            f"| ROE(加权) | % | {fmt_pct(med['roe_w'])} | 是 | {a.fy}年度·加权平均 |",
            f"| 资产负债率 | % | {fmt_pct(med['debt_ratio'])} | 否 | 期末 |",
            f"| 流动比率 | 倍 | {fmt_x(med['current_ratio'])} | 是 | 期末 |",
            "",
        ]
        if fails:
            lines.append(f"> 注：{fails} 家成分股取数失败（新浪/东财偶发拒连），中位数基于 {n} 家有效样本。\n")

    if footer:
        lines += ["## 本次未生成", ""] + [f + "\n" for f in footer]
    lines += ["---", "", "### 新增/替换行业时保持的表头模板", "",
              "```text",
              "| 指标 | 单位 | 行业中位数 | 数值越高越好 | 口径说明 |",
              "| --- | --- | --- | --- | --- |",
              "| 毛利率 | % | 60.0 | 是 | 2025年度 |",
              "| 净利率 | % | 8.0 | 是 | 2025年度 |",
              "| ROE(加权) | % | 10.0 | 是 | 2025年度·加权平均 |",
              "| 资产负债率 | % | 60.0 | 否 | 期末 |",
              "| 流动比率 | 倍 | 1.5 | 是 | 期末 |",
              "```",
              "",
              "优先用 `scripts/build_industry_benchmarks.py` 重算；手工填写的须注明来源与日期，禁止留示例占位。",
    ]

    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[done] 已写入 {outfile}")


if __name__ == "__main__":
    main()

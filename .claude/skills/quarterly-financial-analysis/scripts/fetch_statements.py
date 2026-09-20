# -*- coding: utf-8 -*-
"""步骤1：用 akshare(东财EM) 抓取 A股上市公司三大报表，落盘为规范化 JSON。

输出（相对 --workdir，默认当前目录）：
    data/raw/{code}/meta.json              标的与报告期信息
    data/raw/{code}/profit.json            利润表（按报告期，年初至今累计）
    data/raw/{code}/profit_quarterly.json  利润表（按单季度）
    data/raw/{code}/balance.json           资产负债表（期末时点）
    data/raw/{code}/cashflow.json          现金流量表（按报告期，年初至今累计）
    data/raw/{code}/cashflow_quarterly.json 现金流量表（按单季度）

用法示例：
    python fetch_statements.py --ticker 600519
    python fetch_statements.py --ticker "SH600519" --report-date 2026-06-30 --workdir .
    python fetch_statements.py --ticker "贵州茅台" --refresh

说明：
- 所有金额单位为「元」（EM 原始口径）。
- akshare/东财接口偶尔变动；函数失败时会给出排查提示，可按提示调整后重试。
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

import akshare as ak
import pandas as pd

from fieldmap import PROFIT_FIELDS, BALANCE_FIELDS, CASHFLOW_FIELDS

# (函数名, 存储文件名, 字段映射, 说明)
FETCHES = [
    ("stock_profit_sheet_by_report_em",     "profit",            PROFIT_FIELDS,     "利润表·按报告期(累计)"),
    ("stock_profit_sheet_by_quarterly_em",  "profit_quarterly",  PROFIT_FIELDS,     "利润表·按单季度"),
    ("stock_balance_sheet_by_report_em",    "balance",           BALANCE_FIELDS,    "资产负债表·按报告期(期末)"),
    ("stock_cash_flow_sheet_by_report_em",  "cashflow",          CASHFLOW_FIELDS,   "现金流量表·按报告期(累计)"),
    ("stock_cash_flow_sheet_by_quarterly_em","cashflow_quarterly", CASHFLOW_FIELDS, "现金流量表·按单季度"),
]


def plain_to_em(code):
    first = code[0]
    if first == "6":
        ex = "SH"
    elif first in ("0", "2", "3"):
        ex = "SZ"
    elif first == "4":
        ex = "BJ"
    elif first == "8":
        ex = "BJ"
    elif first == "9":
        ex = "BJ" if code.startswith("920") else "SH"
    else:
        raise ValueError(f"无法识别代码前缀：{code}")
    return ex + code


def resolve(token):
    """token 可能是 '600519' / 'SH600519' / 中文名。返回 (em_code, plain_code, name)。"""
    t = token.strip()
    up = t.upper()
    if re.fullmatch(r"(SH|SZ|BJ)\d{6}", up):
        return up, up[2:], None
    if re.fullmatch(r"\d{6}", t):
        em = plain_to_em(t)
        return em, t, None
    # 尝试按名称匹配：先精确简称，再包含匹配；多命中时提示歧义，不静默取第一个
    df = ak.stock_info_a_code_name()
    name = t.strip()
    hit = df[df["name"] == name]
    if hit.empty:
        hit = df[df["name"].str.contains(name, na=False)]
    if hit.empty:
        raise ValueError(f"找不到标的：{token!r}。请用 6 位代码（如 600519）或完整证券简称。")
    if len(hit) > 1:
        cands = "、".join(f"{r['name']}({r['code']})" for _, r in hit.head(8).iterrows())
        raise ValueError(f"简称「{name}」匹配到多家（{cands}…），请用 6 位代码或更完整的证券简称。")
    code = str(hit.iloc[0]["code"])
    name = str(hit.iloc[0]["name"])
    em = plain_to_em(code)
    return em, code, name


def to_float(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if s in ("", "-", "--"):
            return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f


def fetch_df(func_name, symbol):
    fn = getattr(ak, func_name, None)
    if fn is None:
        raise AttributeError(f"akshare 中不存在函数 {func_name}，请先升级 akshare")
    return fn(symbol=symbol)


def parse_rows(df, fields):
    meta_cols = ["REPORT_TYPE", "REPORT_DATE_NAME", "NOTICE_DATE", "UPDATE_DATE", "SECURITY_NAME_ABBR"]
    rows = []
    if df is None or df.empty:
        return rows
    for i in range(len(df)):
        # report_date 用纯 Python 归一化，避免 pandas 不同版本对 str 存取器的差异
        rec = {"report_date": str(df["REPORT_DATE"].iloc[i]).split(" ")[0].split("T")[0]}
        for col in meta_cols:
            if col in df.columns:
                v = df.iloc[i][col]
                rec[col.lower()] = None if pd.isna(v) else str(v)
        vals = {}
        for key, col in fields.items():
            if col is None:
                continue
            if col not in df.columns:
                continue
            vals[key] = to_float(df.iloc[i][col])
        rec["fields"] = vals
        rows.append(rec)
    return rows


def dedupe_keep_latest(rows):
    """同一 report_date 可能有多版本（更正/更新），取 NOTICE_DATE 最新的一条。"""
    keyed = sorted(rows, key=lambda r: (r["report_date"], str(r.get("notice_date") or "")), reverse=True)
    seen = set()
    out = []
    for r in keyed:
        d = r["report_date"]
        if d in seen:
            continue
        seen.add(d)
        out.append(r)
    out.sort(key=lambda r: r["report_date"])  # 升序返回，便于下游读取
    return out


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def report_label(report_date):
    d = dt.date.fromisoformat(report_date)
    if (d.month, d.day) == (3, 31):
        return f"{d.year}一季报"
    if (d.month, d.day) == (6, 30):
        return f"{d.year}中报"
    if (d.month, d.day) == (9, 30):
        return f"{d.year}三季报"
    if (d.month, d.day) == (12, 31):
        return f"{d.year}年报"
    return report_date


def main():
    ap = argparse.ArgumentParser(description="抓取 A股三大报表(EM)")
    ap.add_argument("--ticker", required=True, help="6位代码/SH600519/证券简称")
    ap.add_argument("--report-date", default=None, help="目标报告期 YYYY-MM-DD；缺省取最新")
    ap.add_argument("--workdir", default=".", help="工作目录（在其下建 data/raw/...）")
    ap.add_argument("--refresh", action="store_true", help="忽略本地缓存，强制重新抓取")
    args = ap.parse_args()

    em_code, plain_code, name_hint = resolve(args.ticker)
    raw_dir = os.path.join(args.workdir, "data", "raw", plain_code)
    meta_path = os.path.join(raw_dir, "meta.json")

    # 缓存命中：目标报告期不变时直接复用，避免重复联网
    if not args.refresh and os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            old = json.load(f)
        if old.get("em_code") == em_code and (
            args.report_date is None or old.get("target_report_date") == args.report_date
        ):
            print(f"[fetch] 缓存命中：{raw_dir}（--refresh 可强制重抓）")
            return

    print(f"[fetch] {em_code} 开始抓取三大报表（共 {len(FETCHES)} 张表）…")
    saved = {}
    for func_name, stem, fields, note in FETCHES:
        try:
            df = fetch_df(func_name, em_code)
            rows = dedupe_keep_latest(parse_rows(df, fields))
            if not rows:
                print(f"[fetch]   ! {note} 为空，跳过")
                continue
            write_json(os.path.join(raw_dir, f"{stem}.json"),
                       {"source": f"akshare.{func_name}(symbol={em_code})",
                        "rows": rows})
            dates = [r["report_date"] for r in rows]
            saved[stem] = dates
            print(f"[fetch]   ok {note}: {len(rows)} 期，最新 {dates[-1]}")
        except Exception as e:
            print(f"[fetch]   FAIL {note}: {type(e).__name__}: {e}")
            print(f"[fetch]     提示：请确认 akshare 版本(>=1.14)、网络可达 eastmoney；"
                  f"或升级后重试：pip install -U akshare")

    if not saved:
        print("[fetch] 所有报表抓取失败，请检查上述错误。")
        sys.exit(1)

    # 确定目标报告期
    if args.report_date:
        target = args.report_date
        assert any(target in ds for ds in saved.values()), f"目标报告期 {target} 不在可取数据内: {sorted(set(d for ds in saved.values() for d in ds))}"
    else:
        target = max(d for ds in saved.values() for d in ds)

    # 尝试补充东财行业信息（用于同业对比；失败不影响主流程）
    industry = None
    try:
        info = ak.stock_individual_info_em(symbol=em_code)
        if info is not None and not info.empty:
            imap = dict(zip(info["item"], info["value"]))
            industry = str(imap.get("行业", "") or "").strip() or None
    except Exception:
        industry = None

    meta = {
        "em_code": em_code,
        "plain_code": plain_code,
        "name": name_hint,
        "industry_em": industry,
        "target_report_date": target,
        "target_report_label": report_label(target),
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tables_available": {k: (v[0], v[-1]) for k, v in saved.items()},
        "cache_note": "金额单位：元。profit/cashflow 按报告期为年初至今累计口径。",
    }
    write_json(meta_path, meta)
    print(f"[fetch] 完成。目标报告期：{target}（{meta['target_report_label']}）"
          f"  行业(东财)：{industry or '未知'}")
    print(f"[fetch] 缓存目录：{raw_dir}")


if __name__ == "__main__":
    main()

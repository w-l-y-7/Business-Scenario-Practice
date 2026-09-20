# -*- coding: utf-8 -*-
"""步骤2：基于 data/raw/{code}/ 的三大报表 JSON 计算核心财务比率。

输入（由 fetch_statements.py 生成）：
    data/raw/{code}/{profit,profit_quarterly,balance,cashflow,cashflow_quarterly}.json
输出：
    data/ratios_{code}_{report_date}.json

口径约定（务必读懂，成文时不能张冠李戴）：
- 「累计」= 年初至报告期末（报表本身口径）；「单季」= 单个自然季度；
  「TTM」= 截止该报告期的近四个单季之和，可近似年度盈利能力。
- 资产负债表为期末时点数。ROE/毛利率/净利率等如无特别说明按「归母」口径。
- 与行业基准（通常是最近完整年度）对比时用 for_peer_compare 里选好的值。

用法：
    python compute_ratios.py --ticker 600519 [--report-date 2026-06-30] [--workdir .]
"""

import argparse
import datetime as dt
import json
import os

from fieldmap import FIELD_LABELS

_Q_MONTHS = [3, 6, 9, 12]


def load_rows(raw_dir, stem):
    with open(os.path.join(raw_dir, f"{stem}.json"), "r", encoding="utf-8") as f:
        return json.load(f).get("rows", [])


def fields_by_date(rows):
    out = {}
    for r in rows:
        out[r["report_date"]] = r.get("fields", {})
    return out


def q_end(year, month):
    day = 30 if month in (6, 9) else 31
    return dt.date(year, month, day)


def prev_q(d):
    idx = _Q_MONTHS.index(d.month)
    if idx == 0:
        return q_end(d.year - 1, 12)
    return q_end(d.year, _Q_MONTHS[idx - 1])


def prev_year_same(d):
    return dt.date(d.year - 1, d.month, d.day)


def fiscal_start(d):
    """期初净资产对应日：报告期所在会计年度的期初，即上年 12-31。"""
    return dt.date(d.year - 1, 12, 31)


def get(container, d, key):
    rec = container.get(d.isoformat())
    if not rec:
        return None
    v = rec.get(key)
    return v if v is not None else None


def div(a, b, scale=100.0):
    if a is None or b in (None, 0):
        return None
    return a / b * scale


def r2(x):
    return None if x is None else round(x, 2)


def load_meta(raw_dir):
    with open(os.path.join(raw_dir, "meta.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="计算核心财务比率")
    ap.add_argument("--ticker", required=True, help="6位代码（对应 data/raw/{code}）")
    ap.add_argument("--report-date", default=None, help="目标报告期 YYYY-MM-DD；缺省取 meta 中最新")
    ap.add_argument("--workdir", default=".", help="工作目录")
    args = ap.parse_args()

    code = args.ticker.strip()
    raw_dir = os.path.join(args.workdir, "data", "raw", code)
    if not os.path.exists(os.path.join(raw_dir, "meta.json")):
        raise SystemExit(f"找不到 {raw_dir}，请先运行 fetch_statements.py --ticker {code}")

    meta = load_meta(raw_dir)
    D = dt.date.fromisoformat(args.report_date or meta["target_report_date"])
    if D.month not in _Q_MONTHS:
        raise SystemExit(f"报告期 {D.isoformat()} 不是季末日（03-31/06-30/09-30/12-31），无法按季计算；"
                         f"请改用季末日报告期（如 2026-06-30），或去掉 --report-date 取最新披露期。")
    label = f"{D.year}{('一季报','中报','三季报','年报')[_Q_MONTHS.index(D.month)]}"

    P = fields_by_date(load_rows(raw_dir, "profit"))            # 累计
    PQ = fields_by_date(load_rows(raw_dir, "profit_quarterly"))  # 单季
    B = fields_by_date(load_rows(raw_dir, "balance"))
    CF = fields_by_date(load_rows(raw_dir, "cashflow"))          # 累计
    CFQ = fields_by_date(load_rows(raw_dir, "cashflow_quarterly"))  # 单季

    # ---- 1) 资产负债表：期末时点 ----
    b = B.get(D.isoformat(), {})
    b_prev_end = B.get(fiscal_start(D).isoformat(), {})
    ta, tl, eqp, ca, cl = b.get("total_assets"), b.get("total_liabilities"), b.get("equity_parent"), b.get("current_assets"), b.get("current_liab")
    eqp_prev = b_prev_end.get("equity_parent")

    # ---- 2) 利润表（累计）与同比 ----
    p, pq = P.get(D.isoformat(), {}), PQ.get(D.isoformat(), {})
    D1y = prev_year_same(D)
    p1y = P.get(D1y.isoformat(), {})
    rev_cum = p.get("revenue") or p.get("revenue_total")
    rev_total_cum = p.get("revenue_total")
    cost_cum = p.get("operate_cost")
    pnp_cum, np_cum, deduct_cum = p.get("net_profit_parent"), p.get("net_profit"), p.get("net_profit_deduct")
    rev1y = p1y.get("revenue") or p1y.get("revenue_total")
    pnp1y = p1y.get("net_profit_parent")

    gross_profit_cum = div(rev_cum - cost_cum, 1, scale=1.0) if (rev_cum is not None and cost_cum is not None) else None

    # ---- 3) 单季与同比 ----
    Dq1 = prev_q(D)
    pq1 = PQ.get(Dq1.isoformat(), {})
    pq1y = PQ.get(prev_year_same(D).isoformat(), {})
    rev_sq = pq.get("revenue") or pq.get("revenue_total")
    pnp_sq = pq.get("net_profit_parent")
    # 若无单季表(极端情况)，用累计差分兜底
    if rev_sq is None and rev_cum is not None and D.month != 3:
        p_prev_q = P.get(Dq1.isoformat(), {})
        rev_sq = rev_cum - (p_prev_q.get("revenue") or p_prev_q.get("revenue_total"))
    if pnp_sq is None and pnp_cum is not None and D.month != 3:
        p_prev_q = P.get(Dq1.isoformat(), {})
        pnp_sq = pnp_cum - p_prev_q.get("net_profit_parent")

    rev_sq1y = pq1y.get("revenue") or pq1y.get("revenue_total")
    pnp_sq1y = pq1y.get("net_profit_parent")

    # ---- 4) TTM：近四个单季合计 ----
    def ttm(keys):
        out = {k: 0.0 for k in keys}
        d = D
        ok = True
        for _ in range(4):
            qr = PQ.get(d.isoformat(), {})
            for k in keys:
                v = qr.get(k)
                if v is None:
                    # 年报四季度可能只有三季单季缺失，此处允许缺失为 0 会失真，标记失败
                    ok = False
                else:
                    out[k] += v
            d = prev_q(d)
        return (out if ok else None)

    keys_ttm = ["revenue", "revenue_total", "operate_cost", "net_profit", "net_profit_parent"]
    tt = ttm(keys_ttm)

    # ---- 5) 现金流量 ----
    cf_cum = CF.get(D.isoformat(), {})
    cf_sq_r = CFQ.get(D.isoformat(), {})
    ocf_cum = cf_cum.get("ocf")
    ocf_sq = cf_sq_r.get("ocf")
    if ocf_sq is None and ocf_cum is not None and D.month != 3:
        prev_q_cf = CF.get(Dq1.isoformat(), {})
        ocf_sq = ocf_cum - prev_q_cf.get("ocf")

    # ---- 6) 组装 metrics（每项都带 basis + definition，成文时照抄口径）----
    gross_margin_cum = div(rev_cum - cost_cum, rev_cum) if (rev_cum and cost_cum) else None
    gross_margin_ttm = div(tt["revenue"] - tt["operate_cost"], tt["revenue"]) if tt else None
    net_margin_parent_cum = div(pnp_cum, rev_total_cum)
    net_margin_cum = div(np_cum, rev_total_cum)
    net_margin_parent_ttm = div(tt["net_profit_parent"], tt["revenue_total"]) if tt else None
    # 平均归母净资产 ROE
    roe_avg = div(pnp_cum, (eqp + eqp_prev) / 2) if (eqp and eqp_prev and pnp_cum is not None) else None
    roe_end = div(pnp_cum, eqp) if (eqp and pnp_cum is not None) else None

    # 最近完整年度（供与“年度行业中位数”对比）
    last_fy = None
    if D.month != 12:
        last_fy = dt.date(D.year - 1, 12, 31)
    fy = B.get(last_fy.isoformat(), {}) if last_fy else {}
    fy_prev = B.get(dt.date(last_fy.year - 1, 12, 31).isoformat(), {}) if last_fy else {}
    pf = P.get(last_fy.isoformat(), {}) if last_fy else {}
    fy_pnp, fy_eqp, fy_eqp_prev = pf.get("net_profit_parent"), fy.get("equity_parent"), fy_prev.get("equity_parent")
    fy_rev_total, fy_rev, fy_cost = pf.get("revenue_total"), pf.get("revenue"), pf.get("operate_cost")
    roe_last_fy = div(fy_pnp, (fy_eqp + fy_eqp_prev) / 2) if (fy_pnp is not None and fy_eqp and fy_eqp_prev) else (div(fy_pnp, fy_eqp) if (fy_pnp is not None and fy_eqp) else None)
    gross_margin_last_fy = div(fy_rev - fy_cost, fy_rev) if (fy_rev and fy_cost is not None) else None
    net_margin_parent_last_fy = div(fy_pnp, fy_rev_total)

    metrics = {
        "current_ratio": {"value": r2(div(ca, cl, 1.0)), "unit": "x", "basis": f"{D.isoformat()} 期末",
                          "definition": "流动资产合计 ÷ 流动负债合计", "label": "流动比率"},
        "debt_ratio": {"value": r2(div(tl, ta)), "unit": "%", "basis": f"{D.isoformat()} 期末",
                       "definition": "负债合计 ÷ 资产合计", "label": "资产负债率"},
        "gross_margin_cum": {"value": r2(gross_margin_cum), "unit": "%", "basis": "累计(年初至报告期末)",
                             "definition": "(营业收入-营业成本) ÷ 营业收入", "label": "毛利率·累计"},
        "net_margin_parent_cum": {"value": r2(net_margin_parent_cum), "unit": "%", "basis": "累计(年初至报告期末)",
                                  "definition": "归母净利润 ÷ 营业总收入", "label": "归母净利率·累计"},
        "roe_end": {"value": r2(roe_end), "unit": "%", "basis": "累计(年初至报告期末)",
                    "definition": "归母净利润 ÷ 期末归母净资产", "label": "ROE(期末口径)"},
        "roe_avg": {"value": r2(roe_avg), "unit": "%", "basis": "累计(年初至报告期末)",
                    "definition": "归母净利润 ÷ [(期初+期末)归母净资产/2]", "label": "ROE(平均净资产口径)"},
        "gross_margin_ttm": {"value": r2(gross_margin_ttm), "unit": "%", "basis": "TTM(近四个单季合计)",
                             "definition": "(Σ营业收入-Σ营业成本) ÷ Σ营业收入", "label": "毛利率·TTM"},
        "net_margin_parent_ttm": {"value": r2(net_margin_parent_ttm), "unit": "%", "basis": "TTM(近四个单季合计)",
                                  "definition": "Σ归母净利润 ÷ Σ营业总收入", "label": "归母净利率·TTM"},
        "gross_margin_last_fy": {"value": r2(gross_margin_last_fy), "unit": "%",
                                 "basis": f"{last_fy} 年度(若存在)", "definition": "同上，年度口径",
                                 "label": "毛利率·最近年度"},
        "net_margin_parent_last_fy": {"value": r2(net_margin_parent_last_fy), "unit": "%",
                                      "basis": f"{last_fy} 年度(若存在)", "definition": "同上，年度口径",
                                      "label": "归母净利率·最近年度"},
        "roe_last_fy": {"value": r2(roe_last_fy), "unit": "%", "basis": f"{last_fy} 年度(若存在)",
                        "definition": "归母净利润 ÷ 平均归母净资产(年度)", "label": "ROE·最近年度"},
    }

    for_peer_compare = {
        "current_ratio": metrics["current_ratio"],
        "debt_ratio": metrics["debt_ratio"],
        "gross_margin": metrics.get("gross_margin_ttm") or metrics.get("gross_margin_last_fy") or metrics["gross_margin_cum"],
        "net_margin": metrics.get("net_margin_parent_ttm") or metrics.get("net_margin_parent_last_fy") or metrics["net_margin_parent_cum"],
        "roe": metrics.get("roe_last_fy") or metrics["roe_end"],
    }

    result = {
        "schema_version": "1.0",
        "script": "compute_ratios.py",
        "ticker": meta.get("plain_code", code),
        "name": meta.get("name"),
        "em_code": meta.get("em_code"),
        "industry_em": meta.get("industry_em"),
        "report_date": D.isoformat(),
        "report_label": label,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "currency": "CNY",
        "amount_unit": "元",
        "data_origin": "akshare stock_*_sheet_by_*_em (东财)",
        "cumulative": {
            "revenue_total": rev_total_cum,
            "revenue": rev_cum,
            "operate_cost": cost_cum,
            "gross_profit": gross_profit_cum,
            "net_profit": np_cum,
            "net_profit_parent": pnp_cum,
            "net_profit_deduct": deduct_cum,
            "revenue_yoy_pct": r2(div(rev_cum - rev1y, abs(rev1y))) if rev_cum is not None and rev1y not in (None, 0) else None,
            "net_profit_parent_yoy_pct": r2(div(pnp_cum - pnp1y, abs(pnp1y))) if pnp_cum is not None and pnp1y not in (None, 0) else None,
        },
        "single_quarter": {
            "revenue": rev_sq,
            "net_profit_parent": pnp_sq,
            "gross_profit": (rev_sq - pq.get("operate_cost")) if (rev_sq is not None and pq.get("operate_cost") is not None) else None,
            "revenue_yoy_pct": r2(div(rev_sq - rev_sq1y, abs(rev_sq1y))) if rev_sq is not None and rev_sq1y not in (None, 0) else None,
            "net_profit_parent_yoy_pct": r2(div(pnp_sq - pnp_sq1y, abs(pnp_sq1y))) if pnp_sq is not None and pnp_sq1y not in (None, 0) else None,
            "gross_margin_pct": r2(div(rev_sq - pq.get("operate_cost"), rev_sq)) if rev_sq is not None else None,
            "net_margin_parent_pct": r2(div(pnp_sq, pq.get("revenue_total"))) if pnp_sq is not None else None,
        },
        "balance_sheet": {
            "total_assets": ta, "total_liabilities": tl, "equity_parent": eqp,
            "current_assets": ca, "current_liab": cl,
            "cash": b.get("cash"), "receivables": b.get("receivables"), "inventory": b.get("inventory"),
            "contract_liab": b.get("contract_liab"),
        },
        "cashflow": {
            "ocf": ocf_cum, "icf": cf_cum.get("icf"), "fcf": cf_cum.get("fcf"),
            "ocf_single_quarter": ocf_sq,
            "cash_cover_parent_cum": r2(div(ocf_cum, pnp_cum, 1.0)) if ocf_cum is not None else None,
        },
        "ttm": ({"revenue": tt["revenue"], "revenue_total": tt["revenue_total"],
                 "net_profit_parent": tt["net_profit_parent"]} if tt else None),
        "metrics": metrics,
        "for_peer_compare": for_peer_compare,
    }

    out_dir = os.path.join(args.workdir, "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"ratios_{code}_{D.isoformat()}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[ratios] 已写入 {out_path}")
    print(f"[ratios] 核心指标(报告期 {label}):")
    for k in ("current_ratio", "debt_ratio", "gross_margin_ttm", "net_margin_parent_ttm", "roe_last_fy"):
        m = metrics.get(k) or for_peer_compare.get({"gross_margin_ttm": "gross_margin"}.get(k, k))
        if m and m.get("value") is not None:
            print(f"    {m['label']:<18} {m['value']}{m['unit']}   [{m['basis']}]")
    print("[ratios] for_peer_compare 已选好与行业基准对比的口径；成文前请先阅读其 basis。")


if __name__ == "__main__":
    main()

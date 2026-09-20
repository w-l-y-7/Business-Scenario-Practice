"""把模型结果渲染成 Markdown 表格。

`analysis/valuation.md` 里的模型表由这里生成、**不手工维护**。
手工抄一遍必然与结果不一致，而且没人能看出哪里抄错了。
"""

from __future__ import annotations


def _pct(value, digits=2):
    return "—" if value is None else f"{value * 100:,.{digits}f}%"


def _num(value, digits=2):
    return "—" if value is None else f"{value:,.{digits}f}"


def _days(value):
    return "—" if value is None else f"{value:,.0f}"


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 逐年预测
# --------------------------------------------------------------------------

def render_forecast_table(results):
    """预测表拆成上下两张 8 列表。

    原本一张 15 列的表在 A4 纵向、17 mm 边距、10 pt 下越界 72.7 pt（试排实测）。
    拆表是 `output-format.md` §1.3 的办法。
    """
    top = [["Y" + str(r["year"]), _pct(r["volume_growth"]), _pct(r["asp_growth"]),
            _num(r["revenue"]), _pct(r["gross_margin"]), _num(r["gross_profit"]),
            _num(r["operating_expenses"]), _num(r["ebit"])] for r in results["forecast"]]
    bottom = [["Y" + str(r["year"]), _num(r["net_income"]), _num(r["depreciation_amortization"]),
               _num(r["capex"]), _num(r["delta_nwc"]), _num(r["net_borrowing"]),
               _num(r["dividend"]), "**" + _num(r["fcfe_ni_path"]) + "**"]
              for r in results["forecast"]]

    base = results["meta"].get("forecast_base") or {}
    parts = [
        _table(["年", "销量增速", "ASP 增速", "收入", "毛利率", "毛利", "期间费用", "EBIT"], top),
        "",
        "（续上表）",
        "",
        _table(["年", "净利润", "折旧摊销", "CapEx", "ΔWC", "净借款", "分红", "**FCFE**"], bottom),
        "",
    ]
    if base:
        parts.append(
            f"基期 {base.get('period')} 为 {base.get('months')} 个月，"
            f"流量项按 ×{base.get('annualize'):.2f} 年化："
            f"{_num(base.get('revenue_as_reported'))} → {_num(base.get('revenue_annualized'))} "
            f"{results['meta']['unit']}。存量项（存货、应收、现金、债务、股数）是时点数，不年化。"
        )
    parts.append(f"单位：{results['meta']['unit']}；利润与现金流为归母口径。")
    return "\n".join(parts)


def render_fcfe_paths(results):
    """FCFE 两条路与差额桥。"""
    rows = []
    for r in results["forecast"]:
        gap = r["fcfe_cfo_path"] - r["fcfe_ni_path"]
        rows.append(["Y" + str(r["year"]), _num(r["fcfe_ni_path"]), _num(r["fcfe_cfo_path"]),
                     _num(gap), _num(r["non_cash_items"]), _num(r["delta_nwc_other"])])
    primary = results["valuation"]["primary"]
    bridge = primary["bridge"]
    return "\n".join([
        _table(["年", "净利润路径 FCFE", "经营现金流路径 FCFE", "差额",
                "非现金项", "ΔNWC（三类之外）"], rows),
        "",
        f"差额合计折算到每股：**{_num(bridge['per_share_gap'])} 元**"
        f"（占主估值 {_pct(bridge['gap_ratio'])}）。差额来源：{bridge['driver']}。",
        "",
        f"两条路恒等时差为 0。{bridge['note']}",
    ])


# --------------------------------------------------------------------------
# 三个价格
# --------------------------------------------------------------------------

def render_prices(results):
    p = results["prices"]
    unit = results["meta"]["currency"]
    lines = [
        _table(["价格口径", f"数值（{unit}）", "说明"], [
            ["市价 market_price", "**" + _num(p["market_price"]) + "**",
             "行情输入，未复权收盘价"],
            ["即期公允价值 spot_fair_value", _num(p["spot_fair_value"]),
             "FCFE 折现直接得到，**不是**评级"],
            ["12 个月目标价 twelve_month_target_price",
             "**" + _num(p["twelve_month_target_price"]) + "**",
             "目标日剩余 FCFE 重估 ÷ 目标日预测稀释股本"],
            ["预期每股分红 expected_dividend", _num(p["expected_dividend"]),
             "第一年净利润 × 分红率 ÷ 目标日股数"],
            ["预期总回报 expected_total_return", _pct(p["expected_total_return"]),
             "（目标价 + 预期分红）÷ 市价 − 1"],
            ["预期价格回报 expected_price_return", _pct(p["expected_price_return"]),
             "目标价 ÷ 市价 − 1，不含分红"],
        ]),
        "",
    ]

    naive = p["naive_check"]
    lines += [
        f"**目标价不是「即期价值 × (1 + Ke)」.** "
        f"那个写法只有在第一年一分钱都不分出去时才成立；本例第一年分红 "
        f"{_num(p['revaluation']['retained_after_dividend'] + p['revaluation']['v0_equity'] * 0)} 亿元口径下，"
        f"两个口径差 **{_num(naive['gap'])} 元/股**（朴素写法 {_num(naive['naive_price'])}，"
        f"显式重估 {_num(p['twelve_month_target_price'])}）。",
        "",
        f"重估勾稽：V₀ × (1 + Ke) − FCFE₁ = {_num(p['revaluation']['v1_closed_form'])}，"
        f"显式重估 = {_num(p['revaluation']['v1_explicit'])}，"
        f"差 {_num(p['revaluation']['reconciliation_gap'])}（应为 0）。",
    ]

    alignment = p.get("alignment") or {}
    if alignment.get("aligned") is False:
        lines += ["", f"> **目标日与预测期年度末不对齐。** {alignment['reason']}"]
    elif alignment.get("aligned") is None:
        lines += ["", f"> 对齐情况未判定：{alignment.get('reason')}"]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 估值
# --------------------------------------------------------------------------

def render_valuation_table(results):
    primary = results["valuation"]["primary"]
    cross = results["valuation"]["cross_check"]
    consistency = results["valuation"]["consistency"]

    base = primary["per_share"]
    rows = [
        ["**FCFE（净利润路径）**", "**主估值**", _pct(primary["discount_rate"]),
         "**" + _num(base) + "**", "—", f"终值占比 {_pct(primary['terminal_share'])}"],
        ["FCFE（经营现金流路径）", "主估值的第二条路", _pct(primary["discount_rate"]),
         _num(primary["cfo_path"]["per_share"]),
         _pct(primary["bridge"]["gap_ratio"]),
         "差额来自非现金项与三类之外的营运资本变动"],
        ["FCFF（EBIT 路径）", "一致性核验", _pct(consistency["discount_rate"]),
         _num(consistency["per_share"]),
         _pct((consistency["per_share"] - base) / base if base else None),
         f"终值占比 {_pct(consistency['terminal_share'])}"],
        ["FCFF（经营现金流路径）", "一致性核验", _pct(consistency["discount_rate"]),
         _num(consistency["cfo_path"]["per_share"]),
         _pct((consistency["cfo_path"]["per_share"] - base) / base if base else None),
         "与 EBIT 路径的差同样只在非现金项与 ΔNWC"],
        ["远期可比（观察值中位数）", "交叉检验", "—", _num(cross["median_of_observations"]),
         _pct((cross["median_of_observations"] - base) / base if base else None),
         f"{cross['tier_count']} 层 × 2 口径 = {cross['observation_count']} 个观察值"],
    ]

    lines = [
        _table(["方法", "角色", "折现率", "隐含每股价值（元）", "与主估值偏离", "说明"], rows),
        "",
        "**不做加权合成**：FCFE 是主估值，FCFF 做一致性核验，远期可比做交叉检验，三者并列呈现。",
        "",
        f"WACC 加权基准：股权 {_pct(consistency['weight_equity'])}、"
        f"有息债务 {_pct(consistency['weight_debt'])}（{consistency['debt_basis']}）。",
        f"WACC 校验：假设计算值 {_pct(consistency['wacc_check'])}，"
        f"采用值 {_pct(consistency['discount_rate'])}，差 {_pct(consistency['wacc_gap'])}。",
    ]
    return "\n".join(lines)


def render_comparables(results):
    cross = results["valuation"]["cross_check"]
    rows = []
    for tier in cross["tiers"]:
        rows.append([
            tier["tier"], str(tier["peer_count"]),
            _num(tier["forward_pe"]["aggregate"]), _num(tier["forward_pe"]["per_share"]),
            _num(tier["ev_ebitda"]["aggregate"]), _num(tier["ev_ebitda"]["per_share"]),
        ])
    low, high = cross["range"]["low"], cross["range"]["high"]
    return "\n".join([
        f"统一日期 **{cross['as_of']}** 的前瞻口径，取{cross['aggregate']}。",
        "",
        _table(["分层", "家数", "远期 P/E", "隐含每股（元）", "EV/EBITDA", "隐含每股（元）"], rows),
        "",
        f"隐含价值区间 **{_num(low)} – {_num(high)} 元**，观察值中位数 **{_num(cross['median_of_observations'])} 元**。",
        "",
        f"前瞻分母：EPS {_num(cross['inputs']['consensus_eps'])}、"
        f"EBITDA {_num(cross['inputs']['consensus_ebitda'])}、"
        f"净债务 {_num(cross['inputs']['net_debt'])}、股数 {_num(cross['inputs']['shares'])}。"
        f"{cross['inputs']['basis']}。",
        "",
        cross["note"],
    ])


def render_scenario_table(results):
    rows = []
    labels = {"base": "基准", "bull": "乐观", "bear": "悲观"}
    for name in ("base", "bull", "bear"):
        block = results["scenarios"][name]
        override = block["override"]
        changed = "、".join(f"{k}={v}" for k, v in override.items()) if override else "—"
        delta = block.get("delta_vs_base")
        rows.append([labels[name], changed, "**" + _num(block["per_share"]) + "**",
                     "—" if delta is None else _pct(delta)])
    return "\n".join([
        _table(["情景", "改变的假设", "每股价值（元）", "相对基准"], rows),
        "",
        "**不预设情景概率、不给加权期望值** —— 报的是结果区间。",
    ])


# --------------------------------------------------------------------------
# 敏感性与反向估值
# --------------------------------------------------------------------------

def _two_way(title, corner, row_values, col_values, table, row_fmt=_num, col_fmt=_num):
    lines = [f"**{title}**", ""]
    lines.append("| " + corner + " | " + " | ".join(col_fmt(c) for c in col_values) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in col_values) + " |")
    for label, row in zip(row_values, table):
        cells = " | ".join("—" if v is None else _num(v) for v in row)
        lines.append(f"| {row_fmt(label)} | {cells} |")
    return "\n".join(lines)


def _pct_or_days(value):
    return f"{value * 100:,.2f}%" if abs(value) < 1 else f"{value:,.0f}"


def render_sensitivity(r1, r2):
    return "\n".join([
        _two_way("敏感性一：Ke × g（每股价值，元）", "Ke \\ g",
                 r1["ke_range"], r1["g_range"], r1["table"],
                 row_fmt=_pct, col_fmt=_pct),
        "",
        _two_way("敏感性二：毛利率 × DIO（每股价值，元）", "毛利率 \\ DIO",
                 r2["gm_range"], r2["dio_range"], r2["table"],
                 row_fmt=_pct, col_fmt=_pct_or_days),
        "",
        "Ke ≤ g 的格子留空 —— 那种组合下终值没有意义，**不硬算一个数填进去**。",
    ])


def render_reverse(results):
    block = results["reverse"]
    rows = []
    for key, item in block["unknowns"].items():
        if item["status"] == "无解":
            rows.append([item.get("unknown", key), "**无解**", "—", "—", item["reason"][:60] + "…"])
            continue
        if key == "revenue_growth":
            value, base = _pct(item["implied_revenue_cagr"]), _pct(item["base_revenue_cagr"])
            detail = f"销量增速整体平移 {_pct(item['shift_delta'])}"
        elif key == "steady_state_margin":
            value, base = _pct(item["implied_steady_state"]), _pct(item["base_steady_state"])
            detail = f"毛利率整体平移 {_pct(item['shift_delta'])}"
        else:
            value, base = _pct(item["implied_ke"]), _pct(item["base_ke"])
            detail = "直接解折现率，其余假设不动"
        rows.append([item["unknown"], "**" + value + "**", base, detail, "—"])
    return "\n".join([
        f"求解市场现价 **{_num(block['market_price'])} 元** 隐含的假设。{block['method']}。",
        "",
        _table(["未知量", "市场隐含", "基准假设", "口径", "说明"], rows),
        "",
        block["note"],
    ])


# --------------------------------------------------------------------------
# 资本结构
# --------------------------------------------------------------------------

def render_capital(results):
    capital = results.get("capital") or {}
    if capital.get("status") != "完成":
        return f"资本结构未完成：{capital.get('status')} —— {capital.get('reason', '—')}"

    bridge = capital["share_bridge"]
    items = [[bridge["opening"]["label"], _num(bridge["opening"]["shares"]), bridge["opening"]["source_id"]]]
    items += [[item["label"], _num(item["shares"]), item["source_id"]] for item in bridge["items"]]
    items += [["**" + bridge["closing"]["label"] + "**", "**" + _num(bridge["closing"]["shares"]) + "**",
               bridge["closing"]["source_id"]]]

    calibers = capital["calibers"]
    caliber_rows = [
        ["基本股本 basic_shares", _num(calibers["basic_shares"]["value"]), calibers["basic_shares"]["basis"]],
        ["已发行股本 issued_shares", _num(calibers["issued_shares"]["value"]), calibers["issued_shares"]["basis"]],
        ["潜在奖励 potential_awards", _num(calibers["potential_awards"]["value"]), calibers["potential_awards"]["basis"]],
        ["预测稀释股本 projected_diluted_shares",
         "**" + _num(calibers["projected_diluted_shares"]["value"]) + "**",
         calibers["projected_diluted_shares"]["basis"]],
        ["其中 H 股", _num(calibers["h_shares"]["value"]), calibers["h_shares"]["basis"]],
    ]

    plans = capital["restricted_stock"]["plans"] or []
    plan_rows = [[p["name"], _num(p["granted"]), _num(p["vested"]), _num(p["cancelled"]),
                  _num(p["unvested"]), p["source_id"]] for p in plans]

    proceeds = capital["h_share_proceeds"]
    if proceeds["status"] == "完成":
        proceed_lines = [
            _table(["项", "金额（亿元）", "说明"], [
                ["最近报告期货币资金", _num(proceeds["reported_cash"]), "报表数"],
                ["最终净募集资金", _num(proceeds["net_proceeds"]),
                 f"发行总额 {_num(proceeds['gross_proceeds'])} 扣发行费用 "
                 f"{_num(proceeds['implicit_fees'])}"],
                ["减：已知募集资金使用", _num(proceeds["use_total"]), "见下"],
                ["**估值日 pro forma 现金**", "**" + _num(proceeds["proforma_cash"]) + "**",
                 "现金桥闭合"],
            ]),
        ]
        for use in proceeds["uses"]:
            proceed_lines.append(f"- 募集资金用途：{use['label']} {_num(use['amount'])} 亿元")
    else:
        proceed_lines = [
            f"**H 股募集资金现金桥未闭合：{proceeds['status']}。** {proceeds['reason']}",
            "",
            f"已记录：发行总额 {_num(proceeds.get('gross_proceeds'))} 亿元、"
            f"最近报告期货币资金 {_num(proceeds.get('reported_cash'))} 亿元。"
            "pro forma 现金**暂不给数**。",
        ]

    return "\n".join([
        f"口径截至 **{capital['as_of']}**。",
        "",
        "**股本桥**（期初 + 各笔变动 = 期末，已闭合）",
        "",
        _table(["项目", "股数（亿股）", "来源"], items),
        "",
        "**四种股数口径**（同一个「股本」在四个地方含义不同，混用必然出错）",
        "",
        _table(["口径", "股数（亿股）", "含义"], caliber_rows),
        "",
        "**限制性股票归属计划**（授予 = 已归属 + 已作废 + 未归属，各计划未归属之和 = 总未归属，已勾稽）",
        "",
        _table(["计划", "授予", "已归属", "已作废", "未归属", "来源"], plan_rows),
        "",
        "**H 股募集资金现金桥**（最近报表日现金 + 最终净募集资金 − 已知使用 = 估值日 pro forma 现金）",
        "",
        *proceed_lines,
    ])


# --------------------------------------------------------------------------
# 三表勾稽
# --------------------------------------------------------------------------

def render_articulation(results):
    block = results.get("articulation") or {}
    checks = block.get("checks") or []
    if not checks:
        return "无勾稽记录。"

    rows = [[c["period"], c["check"], _num(c.get("calculated")), _num(c.get("recorded")),
             c["status"], c.get("note", "")] for c in checks]
    parts = [
        _table(["期间", "检查项", "复算值", "记录值", "结论", "备注"], rows),
        "",
        block.get("note", ""),
    ]
    gaps = block.get("gaps") or []
    if gaps:
        parts += ["", f"**未检索字段 {len(gaps)} 项**（记为「未检索」，不按 0 参与计算）：", ""]
        for gap in gaps[:20]:
            parts.append(f"- {gap['period']} · `{gap['field']}` —— {gap['reason']}")
        if len(gaps) > 20:
            parts.append(f"- …另有 {len(gaps) - 20} 项，见结果 JSON 的 `articulation.gaps`")
    return "\n".join(parts)


def render_reserved(results):
    rows = [[key, value] for key, value in results["reserved"].items()]
    return "\n".join([
        _table(["项目", "状态"], rows),
        "",
        "**预留项未实现，不写成已完成。**",
    ])


def _banner(results):
    """渲染片段的版本与状态标记。

    **刻意不用 `**假设版本**：…` 这种粗体写法** —— 门禁按那个格式比对版本，
    片段若也写成一样，粘进报告后会抢先匹配，把后面写错的版本盖住。
    这里只做标记：粘进去时人一眼能看出这批表和模型对不对得上。
    """
    meta = results.get("meta", {})
    status = meta.get("assumption_status")
    lines = [
        "<!-- 由 tools/model 生成，不手工维护。 -->",
        f"> **本表由 `tools/model` 自动生成，不手工维护。** 假设版本 "
        f"`{meta.get('assumption_version')}`；模型结果版本 `{meta.get('model_version')}`；"
        f"假设状态 `{status}`；运行模式 `{meta.get('mode')}`。",
    ]
    if status != "approved":
        lines.append(
            f"> 假设状态是 `{status}` —— **未经团队确认，本表不得作为评级、目标价"
            "或英文终稿的依据引用。** 模型表格只反映所填假设的算术结果。"
        )
    return "\n".join(lines)


def render_all(results):
    return "\n\n".join([
        _banner(results),
        "## 逐年预测（由 tools/model 生成，不手工维护）",
        render_forecast_table(results),
        "## FCFE 两条路与差额桥",
        render_fcfe_paths(results),
        "## 三个价格",
        render_prices(results),
        "## 估值总表",
        render_valuation_table(results),
        "## 远期可比（三层 × 两口径）",
        render_comparables(results),
        "## 情景",
        render_scenario_table(results),
        "## 敏感性",
        render_sensitivity(results["sensitivities"]["ke_g"], results["sensitivities"]["gm_dio"]),
        "## 反向估值：市场现价隐含了什么",
        render_reverse(results),
        "## 资本结构",
        render_capital(results),
        "## 三表勾稽",
        render_articulation(results),
        "## 预留项",
        render_reserved(results),
    ])

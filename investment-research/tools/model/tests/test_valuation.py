"""估值：FCFE 两路、FCFF 两路、三表勾稽、情景、三个价格、可比交叉检验。

对应 P6 清单：三表勾稽 / FCFE 两路 / FCFF 两路 / Bear ≤ Base ≤ Bull /
WACC > g / 目标价重估勾稽。
"""

from __future__ import annotations

import copy

import pytest

from model import engine


# --------------------------------------------------------------------------
# 三表勾稽
# --------------------------------------------------------------------------

def test_三表勾稽有检查项(results):
    checks = results["articulation"]["checks"]
    assert checks, "勾稽一项都没跑"
    for check in checks:
        assert check["period"]
        assert check["check"]
        assert check["status"] in ("通过", "不一致", "未检索", "参考")


def test_历史期利润表勾稽通过(results):
    rows = [c for c in results["articulation"]["checks"]
            if c["check"] == "收入 − 成本 − 期间费用 = EBIT"]
    assert rows
    for row in rows:
        assert row["status"] == "通过", f"{row['period']} 利润表勾稽不通过"


def test_历史期资产负债表恒等式(results):
    rows = [c for c in results["articulation"]["checks"]
            if c["check"].startswith("资产 = 负债")]
    assert rows
    for row in rows:
        assert row["status"] == "通过", f"{row['period']} 资产负债恒等式不通过"


def test_勾稽缺口记为未检索而不是零(results):
    articulation = results["articulation"]
    for gap in articulation["gaps"]:
        assert gap["status"] in ("未检索", "未披露/未检索")
        assert "不按 0" in gap["reason"]
    assert "不得默认为零" in articulation["note"]


def test_固定资产滚动勾稽通过(results):
    rows = [c for c in results["articulation"]["checks"]
            if c["check"].startswith("固定资产")]
    assert rows, "固定资产滚动一项都没跑"
    for row in rows:
        assert row["status"] == "通过", f"{row['period']} 固定资产滚动不通过"
        assert row["gap"] == pytest.approx(0.0, abs=1e-6)


def test_固定资产对不上就报不一致(raw_inputs, raw_assumptions, register):
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2025A"]["ppe_net"] = 45.00       # 应为 38.00
    inputs = engine.load_inputs(raw, register, "test")
    assumptions = engine.load_assumptions(copy.deepcopy(raw_assumptions), "test", register)
    projection = engine.build_forecast(inputs, assumptions)
    rows = [c for c in engine.articulation(inputs, projection)["checks"]
            if c["check"].startswith("固定资产")]
    flagged = [row for row in rows if row["status"] == "不一致"]
    assert flagged, "固定资产对不上却没报不一致"
    assert flagged[0]["gap"] == pytest.approx(7.0)


def test_固定资产缺项时不重复报缺口(results, raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    del raw["actual"]["2024A"]["ppe_net"]
    inputs = engine.load_inputs(raw, register, "test")
    # 缺项由 articulation_gaps 记一次；固定资产检查跳过，不重复报
    assert any(gap["field"] == "ppe_net" for gap in inputs["articulation_gaps"])


def test_预测期收入按销量与ASP推(inputs, assumptions, projection):
    latest = inputs["actual"][inputs["periods"][-1]]
    prev = float(latest["revenue"]) * projection["base"]["annualize"]
    forecast = assumptions["forecast"]
    for index, row in enumerate(projection["rows"]):
        expected = prev * (1 + forecast["volume_growth"][index]) \
            * (1 + forecast["asp_growth"][index])
        assert row["revenue"] == pytest.approx(expected)
        prev = row["revenue"]


def test_预测期利润表逐项勾稽(projection):
    for row in projection["rows"]:
        assert row["cogs"] == pytest.approx(row["revenue"] * (1 - row["gross_margin"]))
        assert row["gross_profit"] == pytest.approx(row["revenue"] - row["cogs"])
        assert row["ebit"] == pytest.approx(row["gross_profit"] - row["operating_expenses"])
        assert row["ebt"] == pytest.approx(row["ebit"] - row["interest"])
        assert row["net_income"] == pytest.approx(row["ebt"] - row["tax"])


def test_预测期营运资本按周转天数推(projection, assumptions):
    forecast = assumptions["forecast"]
    for index, row in enumerate(projection["rows"]):
        assert row["inventory"] == pytest.approx(
            row["cogs"] * forecast["dio_days"][index] / 365)
        assert row["accounts_receivable"] == pytest.approx(
            row["revenue"] * forecast["dso_days"][index] / 365)
        assert row["accounts_payable"] == pytest.approx(
            row["cogs"] * forecast["dpo_days"][index] / 365)


# --------------------------------------------------------------------------
# FCFE 两条路
# --------------------------------------------------------------------------

def test_FCFE净利润路径逐项可复算(projection):
    for row in projection["rows"]:
        expected = (row["net_income"] + row["depreciation_amortization"]
                    - row["capex"] - row["delta_nwc"] + row["net_borrowing"])
        assert row["fcfe_ni_path"] == pytest.approx(expected)


def test_FCFE经营现金流路径逐项可复算(projection):
    for row in projection["rows"]:
        expected = row["operating_cash_flow"] - row["capex"] + row["net_borrowing"]
        assert row["fcfe_cfo_path"] == pytest.approx(expected)


def test_FCFE差额桥等于两项驱动之差(projection):
    # 两条路的差只来自「非现金项」与「三类之外的营运资本变动」
    for row in projection["rows"]:
        expected = row["non_cash_items"] - row["delta_nwc_other"]
        assert row["fcfe_cfo_path"] - row["fcfe_ni_path"] == pytest.approx(expected)
        assert row["fcfe_bridge"] == pytest.approx(expected)


def test_FCFE差额桥在结果里单列(projection, assumptions):
    fcfe = engine.value_fcfe(projection, assumptions)
    assert fcfe["bridge"]["yearly"] == pytest.approx(
        [r["fcfe_bridge"] for r in projection["rows"]])
    assert fcfe["bridge"]["driver"]
    assert "非现金项" in fcfe["bridge"]["driver"]


def test_FCFE两条路给出各自每股价值(projection, assumptions):
    fcfe = engine.value_fcfe(projection, assumptions)
    assert fcfe["per_share"] > 0
    assert fcfe["cfo_path"]["per_share"] > 0
    assert fcfe["bridge"]["per_share_gap"] == pytest.approx(
        fcfe["cfo_path"]["per_share"] - fcfe["per_share"])
    # 有非现金项时两条路不应恒等 —— 恒等说明第二条路没有独立驱动
    assert fcfe["bridge"]["per_share_gap"] != pytest.approx(0.0)


def test_FCFE两条路的年度序列长度一致(projection, assumptions):
    fcfe = engine.value_fcfe(projection, assumptions)
    assert len(fcfe["paths"]["net_income_path"]) == len(projection["rows"])
    assert len(fcfe["paths"]["cfo_path"]) == len(projection["rows"])


def test_主口径是净利润路径(projection, assumptions):
    fcfe = engine.value_fcfe(projection, assumptions)
    assert fcfe["paths"]["net_income_path"] == pytest.approx(
        [r["fcfe_ni_path"] for r in projection["rows"]])
    assert fcfe["per_share"] == pytest.approx(fcfe["equity_value"] / fcfe["shares"])
    assert fcfe["role"] == "主估值"


def test_终值折现回当期(projection, assumptions):
    fcfe = engine.value_fcfe(projection, assumptions)
    ke = assumptions["discount"]["ke"]
    n = len(projection["rows"])
    assert fcfe["pv_terminal"] == pytest.approx(
        fcfe["terminal_value"] / (1 + ke) ** n)
    assert fcfe["equity_value"] == pytest.approx(
        fcfe["pv_explicit"] + fcfe["pv_terminal"])


# --------------------------------------------------------------------------
# FCFF 两条路
# --------------------------------------------------------------------------

def test_FCFF企业价值与股权价值桥接(projection, assumptions, inputs):
    fcff = engine.value_fcff(projection, assumptions, inputs)
    shares = projection["rows"][-1]["shares"]
    assert fcff["equity_value"] == pytest.approx(
        fcff["enterprise_value"] - fcff["net_debt"])
    assert fcff["per_share"] == pytest.approx(fcff["equity_value"] / shares)


def test_FCFF两条路都不为空(projection, assumptions, inputs):
    fcff = engine.value_fcff(projection, assumptions, inputs)
    shares = projection["rows"][-1]["shares"]
    assert fcff["enterprise_value"] > 0
    assert fcff["cfo_path"]["enterprise_value"] > 0
    assert fcff["bridge"]["per_share_gap"] == pytest.approx(
        (fcff["cfo_path"]["enterprise_value"] - fcff["enterprise_value"]) / shares)


def test_FCFF差额桥与FCFE同一驱动(projection, assumptions):
    for row in projection["rows"]:
        assert row["fcff_cfo_path"] - row["fcff_ni_path"] == pytest.approx(
            row["non_cash_items"] - row["delta_nwc_other"])
        assert row["fcff_bridge"] == pytest.approx(row["fcfe_bridge"])


def test_盈利年份下FCFF两路恒等(projection):
    # EBT > 0 时 tax = (EBIT−利息)×t，两条路代数上恒等，差只来自那两项驱动
    for row in projection["rows"]:
        assert row["ebt"] > 0
        assert row["fcff_cfo_path"] - row["fcff_ni_path"] == pytest.approx(
            row["fcff_bridge"])


def test_WACC用市值加权且现金单列(projection, assumptions, inputs):
    fcff = engine.value_fcff(projection, assumptions, inputs)
    assert fcff["weight_equity"] + fcff["weight_debt"] == pytest.approx(1.0)
    assert "现金单列" in fcff["debt_basis"]
    # WACC 复核值与假设里填的值不一致时如实报出差额，不悄悄改成一致
    assert fcff["wacc_gap"] == pytest.approx(
        fcff["discount_rate"] - fcff["wacc_check"])


# --------------------------------------------------------------------------
# 情景
# --------------------------------------------------------------------------

def test_情景排序Bear不大于Base不大于Bull(results):
    scenarios = results["scenarios"]
    bear = scenarios["bear"]["per_share"]
    base = scenarios["base"]["per_share"]
    bull = scenarios["bull"]["per_share"]
    assert bear <= base <= bull


def test_情景不给概率也不给加权期望(results):
    scenarios = results["scenarios"]
    assert set(scenarios) == {"base", "bull", "bear"}
    text = str(scenarios)
    for banned in ("probability", "权重", "加权", "expected_value"):
        assert banned not in text
    for name in ("bull", "bear"):
        assert "delta_vs_base" in scenarios[name]


def test_情景偏置确实作用于预测(projection, assumptions, inputs):
    base_revenue = projection["rows"][0]["revenue"]
    bull = engine.build_forecast(inputs, assumptions, assumptions["scenarios"]["bull"])
    bear = engine.build_forecast(inputs, assumptions, assumptions["scenarios"]["bear"])
    assert bull["rows"][0]["revenue"] > base_revenue > bear["rows"][0]["revenue"]
    # 悲观情景同时上调了 DIO，营运资本占用更多
    assert bear["rows"][0]["inventory"] > projection["rows"][0]["inventory"]


# --------------------------------------------------------------------------
# 三个价格
# --------------------------------------------------------------------------

def test_三个价格是三个不同的数(results):
    prices = results["prices"]
    assert prices["market_price"] == pytest.approx(100.00)
    assert prices["spot_fair_value"] > 0
    assert prices["twelve_month_target_price"] > 0
    assert len({round(prices["market_price"], 4),
                round(prices["spot_fair_value"], 4),
                round(prices["twelve_month_target_price"], 4)}) == 3


def test_目标价重估勾稽为零(results):
    revaluation = results["prices"]["revaluation"]
    # 显式重估必须等于 V₀×(1+Ke) − FCFE₁
    assert revaluation["reconciliation_gap"] == pytest.approx(0.0, abs=1e-9)
    assert revaluation["v1_closed_form"] == pytest.approx(
        revaluation["v0_equity"] * (1 + results["valuation"]["primary"]["discount_rate"])
        - results["forecast"][0]["fcfe_ni_path"])


def test_朴素写法只在第一年不分红时成立(results):
    naive = results["prices"]["naive_check"]
    first_dividend = results["forecast"][0]["dividend"]
    assert naive["valid"] == (abs(first_dividend) < 1e-6)
    # 差额正好等于第一年分掉的那笔钱（每股）
    assert naive["gap"] == pytest.approx(
        naive["naive_price"] - results["prices"]["twelve_month_target_price"])
    assert naive["gap"] == pytest.approx(results["prices"]["expected_dividend"])


def test_目标价分子分母同口径(results):
    prices = results["prices"]
    assert prices["shares_at_target"] == pytest.approx(results["forecast"][0]["shares"])
    assert "同一口径" in prices["shares_basis"]


def test_目标价分母用预测期股数不含潜在奖励稀释(results):
    # 目标价分母 = 预测期第一年股数（最新报告期股本 + 预测期新发），
    # 潜在奖励（已授予未归属）不在其中 —— 这是「已归属口径」而非「上限稀释口径」。
    # 把差异固定下来：任何一边改了，报告里的分母口径就必须重新说明。
    prices = results["prices"]
    diluted = results["capital"]["calibers"]["projected_diluted_shares"]["value"]
    assert prices["shares_at_target"] == pytest.approx(
        results["forecast"][0]["shares"])
    assert diluted > prices["shares_at_target"]


def test_预期回报由目标价与分红构成(results):
    prices = results["prices"]
    assert prices["expected_total_return"] == pytest.approx(
        (prices["twelve_month_target_price"] + prices["expected_dividend"])
        / prices["market_price"] - 1.0)
    assert prices["expected_price_return"] == pytest.approx(
        prices["twelve_month_target_price"] / prices["market_price"] - 1.0)


def test_目标日与预测期首年年度末的对齐状态如实报出(results):
    alignment = results["prices"]["alignment"]
    assert "aligned" in alignment
    assert alignment["aligned"] in (True, False, None)
    if alignment["aligned"] is False:
        assert alignment["offset_days"] != 0
        assert "需要团队确认" in alignment["reason"]


# --------------------------------------------------------------------------
# 可比交叉检验
# --------------------------------------------------------------------------

def test_可比三层不合并(results):
    comparables = results["valuation"]["cross_check"]
    assert comparables["tier_count"] == 3
    assert [tier["tier"] for tier in comparables["tiers"]] == \
        ["直接同业", "海外光通信", "混合业务"]


def test_可比每层两个口径都不加权(results):
    comparables = results["valuation"]["cross_check"]
    for tier in comparables["tiers"]:
        assert tier["forward_pe"]["per_share"] > 0
        assert tier["ev_ebitda"]["per_share"] > 0
        assert tier["peer_count"] >= 1
    assert comparables["observation_count"] == 6      # 3 层 × 2 口径


def test_可比倍数必须同一日期(results):
    comparables = results["valuation"]["cross_check"]
    assert comparables["as_of"] == "2026-09-18"
    for tier in comparables["tiers"]:
        assert tier["as_of"] == comparables["as_of"]


def test_三个估值口径不合并成一个数(results):
    valuation = results["valuation"]
    assert set(valuation) == {"primary", "cross_check", "consistency"}
    text = str(valuation)
    for banned in ("weighted_average", "blended", "综合目标价"):
        assert banned not in text
    assert valuation["primary"]["role"] == "主估值"
    assert valuation["consistency"]["role"] == "一致性核验"
    assert valuation["cross_check"]["role"] == "交叉检验"


def test_预留项标为未实现(results):
    assert "预留" in results["reserved"]["broker_attribution"]
    with pytest.raises(NotImplementedError):
        engine.broker_attribution()

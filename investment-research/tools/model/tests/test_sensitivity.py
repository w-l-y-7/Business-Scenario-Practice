"""敏感性与方向性约束。

对应 P6 清单：提高 Ke 不得提高价值 / 提高 DIO 不得异常抬高 FCFE。

方向性约束是模型的**逻辑体检**：它不检查某个数字对不对，而是检查「往这边挪，
结果应该往那边走」。方向反了说明公式里某一项的符号错了 —— 这类错误不会让模型报错，
只会让结论悄悄反向，最难发现。

用差分而不是固定数值断言：换一组假设、换一家公司，方向仍应成立。
"""

from __future__ import annotations

import copy

import pytest

from model import engine


def _per_share(inputs, assumptions, override=None):
    return engine.value_fcfe(
        engine.build_forecast(inputs, assumptions, override), assumptions)["per_share"]


# --------------------------------------------------------------------------
# 折现率方向
# --------------------------------------------------------------------------

def test_提高Ke不得提高每股价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    for delta in (0.005, 0.01, 0.02, 0.05):
        trial = copy.deepcopy(assumptions)
        trial["discount"]["ke"] += delta
        higher = engine.value_fcfe(engine.build_forecast(inputs, trial), trial)["per_share"]
        assert higher < base, f"Ke 上调 {delta:.1%} 后每股价值反而升高"


def test_提高Ke使每一年的折现因子都变小(inputs, assumptions):
    trial = copy.deepcopy(assumptions)
    trial["discount"]["ke"] += 0.03
    base = engine.value_fcfe(engine.build_forecast(inputs, assumptions), assumptions)
    higher = engine.value_fcfe(engine.build_forecast(inputs, trial), trial)
    assert higher["pv_explicit"] < base["pv_explicit"]
    assert higher["pv_terminal"] < base["pv_terminal"]
    assert higher["equity_value"] < base["equity_value"]


def test_提高终值增长率提高每股价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    trial = copy.deepcopy(assumptions)
    trial["terminal"]["growth"] += 0.005
    assert engine.value_fcfe(
        engine.build_forecast(inputs, trial), trial)["per_share"] > base


def test_终值增长率追平折现率就报错(inputs, assumptions):
    trial = copy.deepcopy(assumptions)
    trial["terminal"]["growth"] = trial["discount"]["ke"]
    with pytest.raises(Exception):
        engine.value_fcfe(engine.build_forecast(inputs, trial), trial)


def test_敏感性表每一列随Ke单调递减(results):
    table = results["sensitivities"]["ke_g"]
    ke_range = table["ke_range"]
    for column, g in enumerate(table["g_range"]):
        values = [row[column] for row in table["table"] if row[column] is not None]
        for earlier, later in zip(values, values[1:]):
            assert later < earlier, f"g={g:.4f} 这一列随 Ke 上升没有下降"


def test_敏感性表在Ke不大于g的格子留空(results):
    table = results["sensitivities"]["ke_g"]
    for i, ke in enumerate(table["ke_range"]):
        for j, g in enumerate(table["g_range"]):
            if g >= ke:
                assert table["table"][i][j] is None, \
                    f"Ke={ke:.4f} ≤ g={g:.4f} 的格子应当留空，不该硬算"
            else:
                assert table["table"][i][j] is not None


# --------------------------------------------------------------------------
# 营运资本方向：DIO 上升 = 钱压在存货里 = 自由现金流下降
# --------------------------------------------------------------------------

def test_提高DIO不得抬高每股价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    for delta in (10, 20, 40):
        trial = copy.deepcopy(assumptions)
        trial["forecast"]["dio_days"] = [d + delta for d in trial["forecast"]["dio_days"]]
        higher = engine.value_fcfe(engine.build_forecast(inputs, trial), trial)["per_share"]
        assert higher < base, f"DIO 上调 {delta} 天后每股价值反而升高"


def test_提高DIO使存货占用增加(projection, inputs, assumptions):
    row = projection["rows"][0]
    higher = engine.build_forecast(inputs, assumptions, {"dio_days_delta": 20})["rows"][0]
    assert higher["inventory"] > row["inventory"]
    assert higher["accounts_payable"] == pytest.approx(row["accounts_payable"])
    assert higher["delta_nwc"] > row["delta_nwc"]


def test_提高DIO压低第一年FCFE(projection, inputs, assumptions):
    row = projection["rows"][0]
    higher = engine.build_forecast(inputs, assumptions, {"dio_days_delta": 20})["rows"][0]
    # 收入、成本、EBIT 都没变，变的只有营运资本占用
    assert higher["ebit"] == pytest.approx(row["ebit"])
    assert higher["fcfe_ni_path"] < row["fcfe_ni_path"]
    assert higher["fcfe_cfo_path"] < row["fcfe_cfo_path"]


def test_提高DIO不改变非现金项驱动(projection, inputs, assumptions):
    # DIO 只动营运资本，不该动差额桥的两项驱动
    row = projection["rows"][0]
    higher = engine.build_forecast(inputs, assumptions, {"dio_days_delta": 20})["rows"][0]
    assert higher["non_cash_items"] == pytest.approx(row["non_cash_items"])
    assert higher["delta_nwc_other"] == pytest.approx(row["delta_nwc_other"])
    assert higher["fcfe_bridge"] == pytest.approx(row["fcfe_bridge"])


def test_敏感性表每一行随DIO单调递减(results):
    table = results["sensitivities"]["gm_dio"]
    for row_index, gm in enumerate(table["gm_range"]):
        row = table["table"][row_index]
        for earlier, later in zip(row, row[1:]):
            assert later < earlier, f"毛利率 {gm:.2%} 这一行随 DIO 上升没有下降"


# --------------------------------------------------------------------------
# 毛利率方向
# --------------------------------------------------------------------------

def test_提高毛利率提高每股价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    trial = copy.deepcopy(assumptions)
    trial["forecast"]["gross_margin"] = [m + 0.02 for m in trial["forecast"]["gross_margin"]]
    assert engine.value_fcfe(
        engine.build_forecast(inputs, trial), trial)["per_share"] > base


def test_敏感性表每一列随毛利率单调递增(results):
    table = results["sensitivities"]["gm_dio"]
    columns = len(table["dio_range"])
    for column in range(columns):
        values = [table["table"][row][column] for row in range(len(table["gm_range"]))]
        for earlier, later in zip(values, values[1:]):
            assert later > earlier, f"DIO 第 {column} 列随毛利率上升没有升高"


def test_提高期间费用率压低价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    trial = copy.deepcopy(assumptions)
    trial["forecast"]["opex_ratio"] = [r + 0.02 for r in trial["forecast"]["opex_ratio"]]
    assert engine.value_fcfe(
        engine.build_forecast(inputs, trial), trial)["per_share"] < base


def test_提高税率压低价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    trial = copy.deepcopy(assumptions)
    trial["forecast"]["tax_rate"] = 0.25
    assert engine.value_fcfe(
        engine.build_forecast(inputs, trial), trial)["per_share"] < base


def test_提高资本开支率压低价值(inputs, assumptions):
    base = _per_share(inputs, assumptions)
    trial = copy.deepcopy(assumptions)
    trial["forecast"]["capex_ratio"] = [r + 0.03 for r in trial["forecast"]["capex_ratio"]]
    assert engine.value_fcfe(
        engine.build_forecast(inputs, trial), trial)["per_share"] < base


# --------------------------------------------------------------------------
# 反向估值的方向
# --------------------------------------------------------------------------

def test_提高现价则隐含Ke下降(inputs, assumptions):
    # 现金流不变而价格更高，说明市场要求的回报率更低 —— 现价涨，隐含 Ke 跌
    from model import reverse
    low_price = reverse.implied_ke(inputs, assumptions, 30.0)["implied_ke"]
    high_price = reverse.implied_ke(inputs, assumptions, 40.0)["implied_ke"]
    assert high_price < low_price


def test_提高现价则隐含收入增速上升(inputs, assumptions):
    # 现价更高，市场隐含的增长要求更高。两个价格都取在基准价值以下，
    # 落在价值随增速上升的那一段上。
    from model import reverse
    low_price = reverse.implied_revenue_growth(inputs, assumptions, 28.0)["shift_delta"]
    high_price = reverse.implied_revenue_growth(inputs, assumptions, 32.0)["shift_delta"]
    assert high_price > low_price


def test_隐含Ke满足Ke大于g(inputs, assumptions):
    from model import reverse
    result = reverse.implied_ke(inputs, assumptions, 35.0)
    assert result["implied_ke"] > result["terminal_growth"]


def test_现价超出假设能及的范围时报无解(inputs, assumptions):
    from model import reverse
    # 现价 100 万元远超任何一组合理假设能推出的每股价值 → 区间里扫不到符号变化
    results = reverse.reverse_valuation(inputs, assumptions, market_price=1_000_000.0)
    for name in ("revenue_growth", "steady_state_margin", "ke"):
        assert results["unknowns"][name]["status"] == "无解"
        assert "不硬凑" in results["unknowns"][name]["reason"]
        assert "低于" in results["unknowns"][name]["reason"]


def test_一个未知量无解不影响其余(inputs, assumptions):
    from model import reverse
    results = reverse.reverse_valuation(inputs, assumptions, market_price=1_000_000.0)
    # 三个分别报状态，不合并成一个结论
    assert set(results["unknowns"]) == {"revenue_growth", "steady_state_margin", "ke"}
    assert "不构成评级或目标价" in results["note"]


def test_求根器在单调函数上直接收敛():
    from model import reverse
    root, info = reverse._solve(lambda x: x - 3.0, 0.0, 10.0, "测试", 0.0)
    assert root == pytest.approx(3.0)
    assert info["roots_found"] == 1
    assert info["scanned"] is False


def test_求根器在两端同号但中间有解时仍能解出():
    # 目标函数非单调：区间两端同号，中间有两个解。
    # 只看两端就报「无解」，是把有解说成无解 —— 这正是隐含收入增速会撞上的情形。
    from model import reverse
    root, info = reverse._solve(lambda x: (x - 2.0) * (x + 2.0), -5.0, 5.0,
                                "测试", 0.0, base=0.0)
    assert info["scanned"] is True
    assert info["roots_found"] == 2
    assert abs(root) == pytest.approx(2.0)


def test_求根器优先报离基准最近的解():
    from model import reverse
    # 把基准放在 +2 附近，就该报 +2 而不是 −2
    root, info = reverse._solve(lambda x: (x - 2.0) * (x + 2.0), -5.0, 5.0,
                                "测试", 0.0, base=1.5)
    assert root == pytest.approx(2.0)
    assert info["roots_found"] == 2


def test_求根器扫不到符号变化才报无解():
    from model import reverse
    from model.errors import ReverseSolveError
    with pytest.raises(ReverseSolveError) as error:
        reverse._solve(lambda x: x * x + 1.0, -5.0, 5.0, "测试", 0.0)
    assert "不硬凑" in str(error.value)


def test_多个解时在结果里写明还有别的解(inputs, assumptions):
    from model import reverse
    result = reverse.implied_revenue_growth(inputs, assumptions, 30.0)
    if result["solve"]["roots_found"] > 1:
        assert "共有" in result["note"]
        assert "离基准假设最近" in result["note"]


def test_未登记无风险利率时不拆风险溢价(inputs, assumptions):
    from model import reverse
    trial = copy.deepcopy(assumptions)
    trial["discount"]["risk_free"] = None
    result = reverse.implied_ke(inputs, trial, 35.0)
    assert result["implied_equity_risk_premium"] is None
    assert "未登记" in result["premium_note"]


def test_登记了无风险利率才拆风险溢价(inputs, assumptions):
    from model import reverse
    result = reverse.implied_ke(inputs, assumptions, 35.0)
    assert result["risk_free"] == pytest.approx(0.025)
    assert result["implied_equity_risk_premium"] == pytest.approx(
        result["implied_ke"] - result["risk_free"])

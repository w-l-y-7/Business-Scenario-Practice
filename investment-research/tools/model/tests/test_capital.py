"""资本结构：股本桥、限制性股票、H 股募集资金现金桥、四种股数口径。

对应 P6 清单：现金/债务/PPE/股本桥、H 股募资不重复计入、限制性股票不重复计入。

这一组的共同风险是**重复计入**：同一批股票出现在两个计划里、同一笔募资既进
预测期现金又进现金桥 —— 都会让股数或现金凭空多出一块，进而把估值抬高。
"""

from __future__ import annotations

import copy

import pytest

from model import engine
from model.errors import BridgeError


# --------------------------------------------------------------------------
# 股本桥
# --------------------------------------------------------------------------

def test_股本桥闭合(inputs):
    bridge = inputs["capital"]["share_bridge"]
    assert bridge["balanced"] is True
    left = bridge["opening"]["shares"] + sum(i["shares"] for i in bridge["items"])
    assert left == pytest.approx(bridge["closing"]["shares"])


def test_股本桥各笔都有出处(inputs):
    bridge = inputs["capital"]["share_bridge"]
    for leg in [bridge["opening"], *bridge["items"], bridge["closing"]]:
        assert leg["source_id"]


def test_股本桥不闭合就报错(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["capital_structure"]["share_bridge"]["closing"]["shares"] = 10.70
    with pytest.raises(BridgeError) as error:
        engine.load_inputs(raw, register, "test")
    assert "股本桥" in str(error.value)


def test_漏记一笔股本变动就报错(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["capital_structure"]["share_bridge"]["items"].pop()
    with pytest.raises(BridgeError):
        engine.load_inputs(raw, register, "test")


# --------------------------------------------------------------------------
# 限制性股票：两个勾稽
# --------------------------------------------------------------------------

def test_单期授予拆分勾稽(inputs):
    for plan in inputs["capital"]["restricted_stock"]["plans"]:
        total = plan["vested"] + plan["cancelled"] + plan["unvested"]
        assert plan["granted"] == pytest.approx(total)


def test_各计划未归属之和等于总未归属(inputs):
    restricted = inputs["capital"]["restricted_stock"]
    summed = sum(plan["unvested"] for plan in restricted["plans"])
    assert summed == pytest.approx(restricted["total_unvested"])


def test_总未归属被改大就报错(raw_inputs, register):
    # 同一批股票被计入两个计划，潜在奖励会凭空翻倍
    raw = copy.deepcopy(raw_inputs)
    raw["capital_structure"]["restricted_stock"]["total_unvested"] = 0.58
    with pytest.raises(BridgeError) as error:
        engine.load_inputs(raw, register, "test")
    assert "未归属" in str(error.value)


def test_单期授予拆分对不上就报错(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    plan = raw["capital_structure"]["restricted_stock"]["plans"][0]
    plan["unvested"] = 0.20          # 0.10+0.02+0.20 = 0.32 ≠ 授予 0.30
    raw["capital_structure"]["restricted_stock"]["total_unvested"] = 0.40
    with pytest.raises(BridgeError):
        engine.load_inputs(raw, register, "test")


def test_潜在奖励不重复计入稀释股本(inputs):
    calibers = inputs["capital"]["calibers"]
    issued = calibers["issued_shares"]["value"]
    potential = calibers["potential_awards"]["value"]
    diluted = calibers["projected_diluted_shares"]["value"]
    # 稀释股本 = 已发行 + 潜在奖励，只加一次
    assert diluted == pytest.approx(issued + potential)
    # 潜在奖励就是总未归属，不是各计划授予之和（授予数含已归属、已作废部分）
    granted_total = sum(p["granted"] for p in inputs["capital"]["restricted_stock"]["plans"])
    assert potential == pytest.approx(inputs["capital"]["restricted_stock"]["total_unvested"])
    assert potential < granted_total
    assert calibers["restricted_reconciled"] is True


# --------------------------------------------------------------------------
# 四种股数口径
# --------------------------------------------------------------------------

def test_四种股数口径各不相同且关系正确(inputs):
    calibers = inputs["capital"]["calibers"]
    basic = calibers["basic_shares"]["value"]
    issued = calibers["issued_shares"]["value"]
    potential = calibers["potential_awards"]["value"]
    diluted = calibers["projected_diluted_shares"]["value"]

    # 期初 10.00 + 限制性股票归属 0.10 + H 股发行 0.50 = 期末 10.60
    assert basic == pytest.approx(10.00)
    assert issued == pytest.approx(10.60)
    assert potential == pytest.approx(0.38)
    assert diluted == pytest.approx(10.98)
    # 基本股本（加权平均）与已发行股本（期末时点）不是一回事
    assert basic < issued


def test_H股股数单独一栏(inputs):
    calibers = inputs["capital"]["calibers"]
    h_shares = calibers["h_shares"]["value"]
    # 股本桥里标注 H 股的各笔之和
    assert h_shares == pytest.approx(0.50)
    assert h_shares < calibers["issued_shares"]["value"]


def test_每个口径都写了依据(inputs):
    for name, caliber in inputs["capital"]["calibers"].items():
        if isinstance(caliber, dict):
            assert caliber["basis"], f"{name} 没写口径依据"


# --------------------------------------------------------------------------
# H 股募集资金现金桥
# --------------------------------------------------------------------------

def test_H股现金桥闭合(inputs):
    proceeds = inputs["capital"]["h_share_proceeds"]
    assert proceeds["status"] == "完成"
    assert proceeds["balanced"] is True
    # 最近报告期现金 10.00 + 净募集资金 7.60 − 已使用 2.00 = 15.60
    assert proceeds["proforma_cash"] == pytest.approx(15.60)
    assert proceeds["reported_cash"] == pytest.approx(10.00)
    assert proceeds["net_proceeds"] == pytest.approx(7.60)
    assert proceeds["use_total"] == pytest.approx(2.00)


def test_H股募资只用净额不用发行总额(inputs):
    proceeds = inputs["capital"]["h_share_proceeds"]
    assert proceeds["gross_proceeds"] == pytest.approx(8.00)
    assert proceeds["implicit_fees"] == pytest.approx(0.40)
    # 拿发行总额顶替会得到 16.00，比正确值多 0.40
    assert proceeds["proforma_cash"] != pytest.approx(16.00)
    assert proceeds["proforma_cash"] == pytest.approx(
        proceeds["reported_cash"] + proceeds["net_proceeds"] - proceeds["use_total"])


def test_H股募资不进预测期现金避免重复计入(inputs, projection):
    # 预测期的现金持有量就是最近报告期的实际数，募资只通过现金桥单独体现。
    # 若两处都加，同一笔钱会被计两次。
    proceeds = inputs["capital"]["h_share_proceeds"]
    assert projection["cash_end"] == pytest.approx(10.00)
    assert projection["cash_end"] == pytest.approx(proceeds["reported_cash"])
    assert proceeds["proforma_cash"] > projection["cash_end"]


def test_净募集资金缺失时不给proforma数(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    del raw["capital_structure"]["h_share_proceeds"]["net_proceeds"]
    loaded = engine.load_inputs(raw, register, "test")
    proceeds = loaded["capital"]["h_share_proceeds"]

    assert proceeds["status"] == "未完成"
    assert proceeds["balanced"] is False
    assert proceeds["proforma_cash"] is None
    assert "不得拿发行总额代替" in proceeds["reason"]


def test_净募集资金缺失时不拿总额顶替(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    del raw["capital_structure"]["h_share_proceeds"]["net_proceeds"]
    loaded = engine.load_inputs(raw, register, "test")
    proceeds = loaded["capital"]["h_share_proceeds"]
    # 10.00 + 8.00 − 2.00 = 16.00 就是「拿总额顶替」的结果，绝不能出现
    assert proceeds["proforma_cash"] != pytest.approx(16.00)


def test_没有H股材料时标未检索(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    del raw["capital_structure"]["h_share_proceeds"]
    loaded = engine.load_inputs(raw, register, "test")
    proceeds = loaded["capital"]["h_share_proceeds"]
    assert proceeds["status"] == "未检索"
    assert proceeds["balanced"] is False


def test_没有资本结构块时如实标出(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    del raw["capital_structure"]
    loaded = engine.load_inputs(raw, register, "test")
    assert loaded["capital"]["status"] == "未检索"


# --------------------------------------------------------------------------
# 债务与现金口径
# --------------------------------------------------------------------------

def test_债务滚动与净借款一致(projection, inputs):
    latest = inputs["actual"][inputs["periods"][-1]]
    debt = float(latest["interest_bearing_debt"])
    for row in projection["rows"]:
        debt += row["net_borrowing"]
        assert row["debt"] == pytest.approx(debt)


def test_现金不当作负债务(inputs, projection, assumptions):
    # 现金只影响「EV → 股权」的桥，不进 WACC 权重
    assert projection["cash_end"] >= 0
    fcff = engine.value_fcff(projection, assumptions, inputs)
    assert fcff["debt_basis"].startswith("有息债务市场价值")
    assert fcff["net_debt"] == pytest.approx(
        projection["debt_end"] - projection["cash_end"])

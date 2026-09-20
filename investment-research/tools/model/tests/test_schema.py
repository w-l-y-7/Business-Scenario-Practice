"""输入 schema：最小字段集、日期与单位、来源引用、审批与折现率门槛。

对应 P6 清单：输入 schema / 日期与单位 / deprecated 数字被拦截 /
Ke > g / WACC > g / 每个正式数字都要有出处。
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from model import engine, schema
from model.errors import AssumptionNotApprovedError, MissingInputError, SchemaError

QUOTE = dict(
    ticker="000000.SZ",
    exchange="SZ",
    requested_date="2026-09-18",
    actual_trade_date="2026-09-18",
    price_type="close",
    adjustment="none",
    close=100.00,
    currency="CNY",
    source="测试",
    source_grade="B",
    retrieved_at="2026-09-20T10:00+08:00",
    raw_record_path="tools/model/synthetic/raw/000000.SZ-2026-09-17.json",
    status="ok",
)


# --------------------------------------------------------------------------
# 最小字段集（CLAUDE.md §八）
# --------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["unit", "currency", "source_file",
                                     "source_id", "source_tier",
                                     "assurance_status", "status",
                                     "period_start", "period_end",
                                     "publication_date"])
def test_最小字段集缺一个就报错(raw_inputs, register, missing):
    raw = copy.deepcopy(raw_inputs)
    del raw["actual"]["2023A"][missing]
    with pytest.raises(SchemaError):
        engine.load_inputs(raw, register, "test")


def test_最小字段集齐了就通过(inputs):
    assert inputs["periods"] == ["2023A", "2024A", "2025A"]


def test_报告期期末早于期初报错(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2023A"]["period_start"] = "2024-01-01"
    raw["actual"]["2023A"]["period_end"] = "2023-01-01"
    with pytest.raises(SchemaError):
        engine.load_inputs(raw, register, "test")


def test_日期格式不对报错(raw_inputs, register):
    # 有值但格式不对，不是「缺失」—— 报错类型要分得清，否则会让人去补一个填过的字段
    raw = copy.deepcopy(raw_inputs)
    raw["meta"]["valuation_date"] = "2026/09/18"
    with pytest.raises(SchemaError) as error:
        engine.load_inputs(raw, register, "test")
    assert "YYYY-MM-DD" in str(error.value)


# --------------------------------------------------------------------------
# 四个日期
# --------------------------------------------------------------------------

def test_四个日期在结果里齐全且格式合法(results):
    meta = results["meta"]
    for field in ("info_cutoff", "price_date", "valuation_date", "target_date"):
        value = meta[field]
        assert isinstance(value, str)
        assert len(value) == 10 and value[4] == "-" and value[7] == "-"


def test_目标日必须是估值基准日加十二个月(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["meta"]["target_date"] = "2027-10-18"      # 应为 2027-09-18
    with pytest.raises(MissingInputError) as error:
        engine.load_inputs(raw, register, "test")
    assert "12 个月" in str(error.value)


def test_目标期限跟着估值基准日走而不是行情日(inputs):
    # 行情日 2026-09-17，估值基准日 2026-09-18，目标日 2027-09-18
    assert inputs["meta"]["price_date"] == "2026-09-17"
    assert inputs["meta"]["valuation_date"] == "2026-09-18"
    assert inputs["meta"]["target_date"] == "2027-09-18"


# --------------------------------------------------------------------------
# 单位与年化
# --------------------------------------------------------------------------

def test_半年报的流量项年化存量项不年化(half_year_inputs, assumptions):
    base = engine.build_forecast(half_year_inputs, assumptions)["base"]

    assert base["period"] == "2026H1"
    assert base["months"] == 6
    assert base["annualize"] == pytest.approx(2.0)
    assert base["revenue_as_reported"] == pytest.approx(60.00)
    assert base["revenue_annualized"] == pytest.approx(120.00)


def test_半年报的存量项保持原值(half_year_inputs):
    # 存货 / 股本 / 现金是时点数，年化会把它们凭空放大一倍
    latest = half_year_inputs["actual"]["2026H1"]
    assert latest["inventory"] == pytest.approx(20.00)
    assert latest["shares_outstanding"] == pytest.approx(10.00)
    assert latest["cash"] == pytest.approx(10.00)


def test_财年结束日从完整年度推导半年报期末不算(half_year_inputs):
    fiscal = half_year_inputs["fiscal"]
    # 2026H1 的期末是 6 月 30 日，不能当成财年结束日
    assert fiscal["base_year"] == 2024
    assert fiscal["year_end_month"] == 12


# --------------------------------------------------------------------------
# 来源引用完整性
# --------------------------------------------------------------------------

def test_引用未登记的source_id报错(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2023A"]["source_id"] = "SYN-NOPE"
    with pytest.raises(SchemaError) as error:
        engine.load_inputs(raw, register, "test")
    assert "没有这个 id" in str(error.value)


def test_引用线索类来源报错(raw_inputs, register):
    # SYN-LEAD 是 social_media + D 级，只作线索，不进正式模型
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2024A"]["source_id"] = "SYN-LEAD"
    with pytest.raises(SchemaError):
        engine.load_inputs(raw, register, "test")


def test_字段级来源也查登记(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2023A"].setdefault("field_meta", {})["revenue"] = {
        "source_id": "SYN-NOPE"
    }
    with pytest.raises(SchemaError):
        engine.load_inputs(raw, register, "test")


def test_线索类来源在两种模式下都被拦(register):
    # test 模式放宽了 candidate，但线索类仍然不许引用
    formal = schema.load_source_register(
        [row.model_dump() for row in register["rows"].values()], mode="formal")
    assert "SYN-LEAD" not in formal["allowed"]
    assert "SYN-LEAD" not in register["allowed"]


# --------------------------------------------------------------------------
# deprecated 数字被拦截
# --------------------------------------------------------------------------

def test_整个报告期标deprecated必须写原因(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2023A"]["status"] = "deprecated"
    with pytest.raises(SchemaError):
        engine.load_inputs(raw, register, "test")


def test_字段级deprecated被拦在输入层(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["actual"]["2023A"].setdefault("field_meta", {})["revenue"] = {
        "status": "deprecated"
    }
    with pytest.raises(SchemaError) as error:
        engine.load_inputs(raw, register, "test")
    assert "deprecated" in str(error.value) or "作废" in str(error.value)


def test_deprecated来源不许引用(register):
    rows = {row.source_id: row for row in register["rows"].values()}
    row = rows["SYN-AR-2023"].model_copy(update={"status": "deprecated"})
    assert row.blocking_reason() == "该来源已作废"


# --------------------------------------------------------------------------
# 假设文件审批与折现率门槛
# --------------------------------------------------------------------------

def test_未确认的假设不得跑正式模式(raw_assumptions, register):
    with pytest.raises(AssumptionNotApprovedError):
        engine.load_assumptions(copy.deepcopy(raw_assumptions), "formal", register)


def test_未确认的假设可以跑测试模式(raw_assumptions, register):
    loaded = engine.load_assumptions(copy.deepcopy(raw_assumptions), "test", register)
    assert loaded["status"] == "candidate"


def test_Ke必须大于终值增长率(raw_assumptions, register):
    raw = copy.deepcopy(raw_assumptions)
    raw["discount"]["ke"] = 0.02          # 低于 g=0.025
    with pytest.raises(MissingInputError) as error:
        engine.load_assumptions(raw, "test", register)
    assert "discount.ke" in str(error.value)


def test_WACC必须大于终值增长率(raw_assumptions, register):
    raw = copy.deepcopy(raw_assumptions)
    raw["discount"]["wacc"] = 0.01        # 低于 g=0.025
    with pytest.raises(MissingInputError) as error:
        engine.load_assumptions(raw, "test", register)
    assert "discount.wacc" in str(error.value)


def test_结果里的折现率满足门槛(results, assumptions):
    g = assumptions["terminal"]["growth"]
    assert assumptions["discount"]["ke"] > g
    assert assumptions["discount"]["wacc"] > g


# --------------------------------------------------------------------------
# 假设登记：每条都要登记，且登记值与文件值一致
# --------------------------------------------------------------------------

def test_没登记的假设被拦截(raw_assumptions, register):
    raw = copy.deepcopy(raw_assumptions)
    raw["forecast"]["new_invented_assumption"] = 0.5
    with pytest.raises(SchemaError) as error:
        engine.load_assumptions(raw, "test", register)
    assert "new_invented_assumption" in str(error.value)


def test_登记表还停在上一版会被拦(raw_assumptions, register):
    # 文件里毛利率改成 0.45，登记表还写 0.40 —— 模型会用着没审过的数
    raw = copy.deepcopy(raw_assumptions)
    raw["forecast"]["gross_margin"] = [0.45, 0.41, 0.41, 0.42, 0.42]
    with pytest.raises(SchemaError) as error:
        engine.load_assumptions(raw, "test", register)
    assert "对不上" in str(error.value)


def test_折现率假设也要登记(raw_assumptions, register):
    raw = copy.deepcopy(raw_assumptions)
    raw["assumptions_register"] = [
        entry for entry in raw["assumptions_register"] if entry["item"] != "discount.ke"
    ]
    with pytest.raises(SchemaError) as error:
        engine.load_assumptions(raw, "test", register)
    assert "discount.ke" in str(error.value)


def test_每条假设都登记了(assumptions):
    registered = {entry.item for entry in assumptions["register"].values()}
    assert "discount.ke" in registered
    assert "terminal.growth" in registered
    assert "forecast.gross_margin" in registered


def test_候选假设必须写复核说明(raw_assumptions, register):
    raw = copy.deepcopy(raw_assumptions)
    for entry in raw["assumptions_register"]:
        if entry["item"] == "forecast.gross_margin":
            entry["review_note"] = ""
    with pytest.raises(SchemaError):
        engine.load_assumptions(raw, "test", register)


# --------------------------------------------------------------------------
# 行情 schema（P5 审计建议）
# --------------------------------------------------------------------------

def test_前复权价不得进现价():
    with pytest.raises(ValidationError):
        schema.MarketQuote(**{**QUOTE, "adjustment": "forward"})


def test_回退时的实际交易日必须早于请求日():
    with pytest.raises(ValidationError):
        schema.MarketQuote(**{**QUOTE, "status": "fallback"})
    ok = schema.MarketQuote(**{**QUOTE, "status": "fallback",
                               "actual_trade_date": "2026-09-17"})
    assert ok.actual_trade_date == "2026-09-17"


def test_状态非ok时实际交易日不许等于请求日():
    with pytest.raises(ValidationError):
        schema.MarketQuote(**{**QUOTE, "status": "ok",
                              "actual_trade_date": "2026-09-17"})


def test_没取到价时不许带正数收盘价():
    for status in ("suspended", "no_data", "unavailable"):
        with pytest.raises(ValidationError):
            schema.MarketQuote(**{**QUOTE, "status": status})


def test_行情标注日期不一时一路透传():
    quote = schema.MarketQuote(**{**QUOTE, "status": "fallback",
                                  "actual_trade_date": "2026-09-17"})
    assert "2026-09-18" in quote.price_note()
    assert "2026-09-17" in quote.price_note()


def test_行情币种必须与输入币种一致(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["meta"]["market_quote"] = {**QUOTE, "currency": "HKD"}
    with pytest.raises(SchemaError) as error:
        engine.load_inputs(raw, register, "test")
    assert "币种" in str(error.value)


def test_行情收盘价必须等于输入的现价(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    raw["meta"]["market_quote"] = {**QUOTE, "close": 88.00}
    with pytest.raises(SchemaError) as error:
        engine.load_inputs(raw, register, "test")
    assert "latest_price" in str(error.value) or "现价" in str(error.value)


def test_行情块缺失不阻塞校验(raw_inputs, register):
    raw = copy.deepcopy(raw_inputs)
    del raw["meta"]["market_quote"]
    loaded = engine.load_inputs(raw, register, "test")
    assert loaded["meta"]["latest_price"] == pytest.approx(100.00)

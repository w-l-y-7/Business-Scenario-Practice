"""模型自测：用合成数据验证规则有没有真的落到实处。

这不是「跑通了就行」的冒烟测试，每一条断言对应一条写进技能与规范的硬规矩：

    1. 缺失数据不得默认为零
    2. 未确认的假设不得产出正式结果
    3. 确认记录不得预填
    4. Ke 必须大于终值增长率 g
    5. WACC 用有息债务加权，不是净债务
    6. 情景不给加权期望值（只报区间）
    7. 敏感性里 g >= Ke 的格子留空，不硬算
    8. 悲观 < 基准 < 乐观
    9. 输出门禁拦得住 candidate 状态
   10. 四个日期缺一不可
   11. 预留项没有被偷偷实现
   12. 渲染不崩且带单位说明
   13. 输出门禁拦得住作废数字
   14. 日期引号与否都归一成 YYYY-MM-DD
   15. 目标期限必须是 12 个月

用法：python tools/model/selfcheck.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import engine, render  # noqa: E402
from model.errors import AssumptionNotApprovedError, MissingInputError  # noqa: E402

HERE = Path(__file__).resolve().parent
SYNTHETIC = HERE / "synthetic"

PASSED = []
FAILED = []


def check(name):
    def decorator(func):
        try:
            func()
            PASSED.append(name)
        except AssertionError as error:
            FAILED.append(f"{name} —— {error}")
        except Exception as error:  # noqa: BLE001
            FAILED.append(f"{name} —— 意外异常 {type(error).__name__}: {error}")
        return func
    return decorator


def load(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def synthetic_inputs():
    return engine.load_inputs(load(SYNTHETIC / "historical.yaml"))


def synthetic_candidate():
    return load(SYNTHETIC / "assumptions_candidate.yaml")


def approve(raw):
    """把候选假设就地标成已确认 —— 只在自测里用。"""
    approved = copy.deepcopy(raw)
    approved["status"] = "approved"
    approved["confirmed_by"] = "自测（合成数据，非真实确认人）"
    approved["confirmed_on"] = "2026-09-18"
    return engine.load_assumptions(approved, mode="test")


@check("01 缺失数据不得默认为零")
def _():
    raw = load(SYNTHETIC / "historical.yaml")
    del raw["actual"][2025]["capex"]
    try:
        engine.load_inputs(raw)
    except MissingInputError as error:
        assert "capex" in str(error), f"报错信息没点出缺哪个字段：{error}"
        return
    raise AssertionError("少了 capex 竟然通过了校验 —— 说明缺失被静默按 0 处理了")


@check("02 未确认的假设不得产出正式结果")
def _():
    assumptions = engine.load_assumptions(synthetic_candidate(), mode="test")
    try:
        engine.load_assumptions(synthetic_candidate(), mode="formal")
    except AssumptionNotApprovedError:
        assert assumptions["status"] == "candidate"
        return
    raise AssertionError("candidate 状态的假设在 formal 模式下竟然放行了")


@check("03 确认记录不得预填")
def _():
    raw = synthetic_candidate()
    raw["status"] = "approved"          # 状态对了，但确认人还空着
    try:
        engine.load_assumptions(raw, mode="formal")
    except MissingInputError as error:
        assert "confirmed_by" in str(error), f"该报确认人缺失，实际报了：{error}"
        return
    raise AssertionError("状态改成 approved 就放行了，确认人空着也没人管")


@check("04 Ke 必须大于终值增长率")
def _():
    raw = synthetic_candidate()
    raw["terminal"]["growth"] = raw["discount"]["ke"] + 0.01
    try:
        engine.load_assumptions(raw, mode="test")
    except MissingInputError as error:
        assert "Ke" in str(error) or "g" in str(error)
        return
    raise AssertionError("g > Ke 竟然通过了 —— 终值会算出一个负数或无穷大")


@check("05 WACC 用有息债务加权，不是净债务")
def _():
    inputs = synthetic_inputs()
    results = engine.run_model(inputs, approve(synthetic_candidate()), mode="test")
    consistency = results["valuation"]["consistency"]
    weights = consistency["weight_equity"] + consistency["weight_debt"]
    assert abs(weights - 1.0) < 1e-9, f"权重之和是 {weights}，应为 1"
    assert consistency["weight_debt"] > 0, "债务权重为 0 —— 可能又拿净债务当权重了"
    assert "有息债务" in consistency["debt_basis"]


@check("06 情景不给加权期望值")
def _():
    inputs = synthetic_inputs()
    results = engine.run_model(inputs, approve(synthetic_candidate()), mode="test")
    for name, block in results["scenarios"].items():
        assert "probability" not in block, f"情景 {name} 里出现了概率"
        assert "expected_value" not in block, f"情景 {name} 里出现了加权期望值"


@check("07 敏感性里 g >= Ke 的格子留空")
def _():
    inputs = synthetic_inputs()
    assumptions = approve(synthetic_candidate())
    table = engine.sensitivity_ke_g(inputs, assumptions, [0.08, 0.10, 0.12], [0.02, 0.09, 0.13])
    assert table["table"][0][2] is None, "Ke=8%、g=13% 的格子应当留空"
    assert table["table"][2][0] is not None, "Ke=12%、g=2% 的格子应当有值"


@check("08 悲观 < 基准 < 乐观")
def _():
    inputs = synthetic_inputs()
    results = engine.run_model(inputs, approve(synthetic_candidate()), mode="test")
    bear = results["scenarios"]["bear"]["per_share"]
    base = results["scenarios"]["base"]["per_share"]
    bull = results["scenarios"]["bull"]["per_share"]
    assert bear < base < bull, f"情景排序不对：悲观 {bear:.2f} / 基准 {base:.2f} / 乐观 {bull:.2f}"


@check("09 输出门禁拦得住 candidate 状态")
def _():
    inputs = synthetic_inputs()
    results = engine.run_model(inputs, engine.load_assumptions(
        synthetic_candidate(), mode="test"), mode="test")
    from model import gate_check
    problems = gate_check.check_status(results)
    assert problems, "candidate 状态竟然过了状态门禁"
    assert any("approved" in p for p in problems)

    approved_results = engine.run_model(inputs, approve(synthetic_candidate()), mode="test")
    approved_results["meta"]["assumption_status"] = "approved"
    assert not gate_check.check_status(approved_results), "approved 状态被误拦"


@check("10 日期字段缺一不可")
def _():
    inputs = synthetic_inputs()
    results = engine.run_model(inputs, approve(synthetic_candidate()), mode="test")
    from model import gate_check
    assert not gate_check.check_dates(results), "四个日期齐全时不该报错"
    broken = copy.deepcopy(results)
    broken["meta"].pop("price_date")
    assert gate_check.check_dates(broken), "缺了行情日期竟然没报出来"


@check("11 预留项没有被偷偷实现")
def _():
    for func in (engine.reverse_dcf, engine.broker_attribution):
        try:
            func()
        except NotImplementedError:
            continue
        raise AssertionError(f"{func.__name__} 竟然能跑 —— 预留项不许写成已完成")


@check("12 渲染不崩且带单位说明")
def _():
    inputs = synthetic_inputs()
    results = engine.run_model(inputs, approve(synthetic_candidate()), mode="test")
    text = render.render_all(results)
    for keyword in ("逐年预测", "三路估值", "敏感性一", "敏感性二", "预留项", "归母口径"):
        assert keyword in text, f"渲染结果里缺 `{keyword}`"
    assert "不做加权合成" in text


@check("13 输出门禁拦得住作废数字")
def _():
    from pathlib import Path

    from model import gate_check
    block = {
        "status": "deprecated",
        "deprecated_values": "[790.26, -11.80%]",
        "reason": "自测用",
    }
    deprecated = [(Path("analysis/valuation.md"), block)]

    clean = "目标价由本次模型结果给出，未引用旧稿。"
    assert not gate_check.check_deprecated(deprecated, clean), "干净稿被误拦"

    dirty = "目标价 790.26 元，沿用旧结论。"
    problems = gate_check.check_deprecated(deprecated, dirty)
    assert problems, "含作废数字 790.26 的稿子竟然放行了"
    assert any("790.26" in p for p in problems), f"报错没点出是哪个数：{problems}"

    quoted = "见 analysis/valuation.md。"
    assert gate_check.check_deprecated(deprecated, quoted), "引用了已作废文件竟然没报"


@check("14 日期引号与否都归一成 YYYY-MM-DD")
def _():
    raw = load(SYNTHETIC / "historical.yaml")
    # 不加引号时 PyYAML 给的是 datetime.date；加引号时是字符串。两种都得能用。
    raw["meta"]["price_date"] = "2026-09-18"        # 字符串
    inputs = engine.load_inputs(raw)
    assert inputs["meta"]["price_date"] == "2026-09-18", "带引号的日期没归一对"
    assert isinstance(inputs["meta"]["info_cutoff"], str), "不带引号的日期没转成字符串"

    raw["meta"]["valuation_date"] = "2026/09/18"     # 格式不对的日期
    try:
        engine.load_inputs(raw)
    except MissingInputError as error:
        assert "YYYY-MM-DD" in str(error), f"该报格式不对，实际报了：{error}"
        return
    raise AssertionError("写了 2026/09/18 竟然通过了 —— 日期格式没真正校验")


@check("15 目标期限必须是 12 个月")
def _():
    raw = load(SYNTHETIC / "historical.yaml")
    assert engine._add_months("2026-09-18", 12) == "2027-09-18"
    assert engine._add_months("2024-02-29", 12) == "2025-02-28", "闰日加一年该退到 2 月末"

    raw["meta"]["target_date"] = "2027-03-18"      # 只有 6 个月
    try:
        engine.load_inputs(raw)
    except MissingInputError as error:
        assert "12 个月" in str(error), f"该报期限不对，实际报了：{error}"
        return
    raise AssertionError("6 个月的目标期限竟然放行了 —— 期限不同目标价不可比")


def main():
    print("统一模型自测（合成数据）")
    print("=" * 46)
    for item in PASSED:
        print(f"  通过  {item}")
    for item in FAILED:
        print(f"  失败  {item}")
    print("=" * 46)
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""输出门禁五项。

对应 P6 清单：报告版本与模型/假设版本一致 / 每个正式数字都有 source_id 或
已确认的 assumption_id / deprecated 数字被拦截（成品侧）。

门禁是**导出前的最后一道**：它不看模型算得对不对，只看「这份成品有没有资格出去」。
所以这一组的测试都用改造过的结果 dict，不重跑模型。
"""

from __future__ import annotations

import copy

import pytest

from model import gates


@pytest.fixture
def approved_results(results):
    """把 test 模式的结果改成「已确认」的样子，用来测门禁本身能不能过。

    这不是伪造确认记录 —— 它只活在内存里，不会落盘、不会进任何成品。
    真实的确认记录只能由分析师填（见 CLAUDE.md 红线）。
    """
    approved = copy.deepcopy(results)
    approved["meta"].update({
        "mode": "formal",
        "assumption_status": "approved",
        "confirmed_by": "测试用假名",
        "confirmed_on": "2026-09-20",
    })
    for entry in approved["provenance"]["assumptions"]:
        entry["status"] = "approved"
    return approved


@pytest.fixture
def report_text(results):
    return (
        "# 示例公司估值报告\n\n"
        "**模型结果版本**：v2\n"
        f"**假设版本**：{results['meta']['assumption_version']}\n"
    )


# --------------------------------------------------------------------------
# 一：状态门禁
# --------------------------------------------------------------------------

def test_候选假设的结果过不了状态门禁(results):
    problems = gates.check_status(results)
    assert problems
    assert any("不是 `approved`" in p for p in problems)


def test_缺确认记录过不了状态门禁(approved_results):
    for field in ("confirmed_by", "confirmed_on"):
        broken = copy.deepcopy(approved_results)
        broken["meta"][field] = None
        problems = gates.check_status(broken)
        assert any(field in p for p in problems)


def test_已确认的结果通过状态门禁(approved_results):
    assert gates.check_status(approved_results) == []


# --------------------------------------------------------------------------
# 二：版本一致
# --------------------------------------------------------------------------

def test_报告版本与模型结果版本一致(approved_results, report_text):
    assert gates.check_versions(approved_results, report_text) == []


def test_报告版本落后于模型就报错(approved_results):
    stale = (
        "# 报告\n\n"
        "**模型结果版本**：v1\n"          # 结果文件是 v2
        f"**假设版本**：{approved_results['meta']['assumption_version']}\n"
    )
    problems = gates.check_versions(approved_results, stale)
    assert problems
    assert any("没跟上模型" in p for p in problems)


def test_报告缺假设版本就报错(approved_results):
    text = "**模型结果版本**：v2\n"
    problems = gates.check_versions(approved_results, text)
    assert any("假设版本" in p for p in problems)


def test_报告写全角冒号也认(approved_results):
    text = ("**模型结果版本**：v2\n"
            f"**假设版本**：{approved_results['meta']['assumption_version']}\n")
    assert gates.check_versions(approved_results, text) == []


def test_没有报告文本时不比版本(approved_results):
    assert gates.check_versions(approved_results, None) == []


# --------------------------------------------------------------------------
# 三：废弃内容
# --------------------------------------------------------------------------

def test_成品里出现废弃数字被拦截(tmp_path):
    stale_note = tmp_path / "旧目标价.md"
    stale_note.write_text(
        "---\nstatus: deprecated\ndeprecated_values: [36.08, 40.00]\n---\n旧结论\n",
        encoding="utf-8",
    )
    found = gates.collect_deprecated([tmp_path])
    assert len(found) == 1

    problems = gates.check_deprecated(found, "本报告目标价 36.08 元")
    assert problems
    assert any("36.08" in p for p in problems)


def test_成品引用废弃文件被拦截(tmp_path):
    stale_note = tmp_path / "旧目标价.md"
    stale_note.write_text("---\nstatus: deprecated\n---\n", encoding="utf-8")
    found = gates.collect_deprecated([tmp_path])
    problems = gates.check_deprecated(found, f"见 {stale_note.as_posix()} 的结论")
    assert problems


def test_没出现废弃数字就放行(tmp_path):
    stale_note = tmp_path / "旧目标价.md"
    stale_note.write_text(
        "---\nstatus: deprecated\ndeprecated_values: [36.08]\n---\n", encoding="utf-8")
    found = gates.collect_deprecated([tmp_path])
    assert gates.check_deprecated(found, "本报告目标价 41.20 元") == []


def test_没标deprecated的文件不参与扫描(tmp_path):
    fresh = tmp_path / "草稿.md"
    fresh.write_text("---\nstatus: candidate\n---\n草稿\n", encoding="utf-8")
    assert gates.collect_deprecated([tmp_path]) == []


def test_目录不存在时安全跳过(tmp_path):
    assert gates.collect_deprecated([tmp_path / "不存在"]) == []


# --------------------------------------------------------------------------
# 四：日期完整
# --------------------------------------------------------------------------

def test_四个日期齐全格式合法(approved_results):
    assert gates.check_dates(approved_results) == []


def test_缺一个日期就报错(approved_results):
    broken = copy.deepcopy(approved_results)
    del broken["meta"]["valuation_date"]
    problems = gates.check_dates(broken)
    assert any("valuation_date" in p for p in problems)


def test_日期格式不对就报错(approved_results):
    broken = copy.deepcopy(approved_results)
    broken["meta"]["price_date"] = "2026年9月18日"
    problems = gates.check_dates(broken)
    assert any("YYYY-MM-DD" in p for p in problems)


# --------------------------------------------------------------------------
# 五：来源齐全
# --------------------------------------------------------------------------

def test_每个报告期都有出处(approved_results):
    assert gates.check_sources(approved_results) == []
    for item in approved_results["provenance"]["periods"]:
        assert item["source_id"]
        assert item["source_tier"]


def test_报告期缺source_id被拦截(approved_results):
    broken = copy.deepcopy(approved_results)
    broken["provenance"]["periods"][0]["source_id"] = None
    problems = gates.check_sources(broken)
    assert any("source_id" in p for p in problems)


def test_报告期缺source_tier被拦截(approved_results):
    broken = copy.deepcopy(approved_results)
    broken["provenance"]["periods"][0]["source_tier"] = None
    problems = gates.check_sources(broken)
    assert any("source_tier" in p for p in problems)


def test_每条假设都有登记id与出处(approved_results):
    for item in approved_results["provenance"]["assumptions"]:
        assert item["id"]
        assert item["source_id"]
        assert item["status"] in ("candidate", "approved", "derived", "reported")


def test_假设缺出处被拦截(approved_results):
    broken = copy.deepcopy(approved_results)
    broken["provenance"]["assumptions"][0]["source_id"] = None
    problems = gates.check_sources(broken)
    assert any("source_id" in p for p in problems)


def test_正式模式下假设出处的清单不能为空(approved_results):
    broken = copy.deepcopy(approved_results)
    broken["provenance"]["assumptions"] = []
    problems = gates.check_sources(broken)
    assert any("不能只给数字不给依据" in p for p in problems)


def test_没有provenance块直接拦(approved_results):
    broken = copy.deepcopy(approved_results)
    broken["provenance"] = None
    problems = gates.check_sources(broken)
    assert any("provenance" in p for p in problems)


def test_provenance覆盖每个报告期(results, inputs):
    periods = [item["period"] for item in results["provenance"]["periods"]]
    assert periods == inputs["periods"]


def test_provenance覆盖每条假设(results, assumptions):
    listed = {item["id"] for item in results["provenance"]["assumptions"]}
    assert listed == set(assumptions["register"])


# --------------------------------------------------------------------------
# 总入口
# --------------------------------------------------------------------------

def test_五项全过(approved_results, report_text, tmp_path):
    assert gates.run_gates(approved_results, report_text, [tmp_path]) == []


def test_候选结果五项不全过(results, report_text):
    problems = gates.run_gates(results, report_text)
    assert problems
    assert any("approved" in p for p in problems)


def test_问题清单不重复不遗漏五类(approved_results, report_text):
    broken = copy.deepcopy(approved_results)
    broken["meta"].update({"assumption_status": "candidate", "confirmed_by": None})
    broken["meta"]["target_date"] = "2027/09/18"
    broken["provenance"]["periods"][0]["source_id"] = None
    problems = gates.run_gates(broken, "**模型结果版本**：v1\n**假设版本**：x\n")
    # 状态、版本、日期、来源四类都该报出来（没有 deprecated 目录）
    assert any("approved" in p for p in problems)
    assert any("没跟上模型" in p for p in problems)
    assert any("YYYY-MM-DD" in p for p in problems)
    assert any("source_id" in p for p in problems)

"""输出门禁：五项检查，全过才允许导出 PDF。

    1. 状态门禁 —— 结果必须来自 approved 假设，且确认记录齐全
    2. 版本一致 —— 成品的假设版本 / 模型结果版本与结果文件一致
    3. 废弃内容 —— 被标 deprecated 的旧目标价、旧评分不得混进成品
    4. 日期完整 —— 四个日期字段齐全且格式合法
    5. 来源齐全 —— 每个正式数字都有 `source_id` 或 `approved assumption_id`

用法：

    python tools/model/run_model.py gates \
      --results model/results/valuation.json \
      --report output/investment-report.md \
      --scan analysis model/results

**检查没过就不导出。** 退出码 0 通过、1 不通过、2 结果文件读不了。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DATE_FIELDS = ("info_cutoff", "price_date", "valuation_date", "target_date")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def parse_status_block(path):
    """读出 Markdown 文件开头第一个 YAML 状态块，读不到返回 None。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    block = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            block[key.strip()] = value.strip()
    return block or None


def collect_deprecated(scan_dirs):
    """扫出所有标 deprecated 的状态块，返回 (路径, 状态块) 列表。"""
    found = []
    for directory in scan_dirs or []:
        base = Path(directory)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            block = parse_status_block(path)
            if block and block.get("status") == "deprecated":
                found.append((path, block))
    return found


def check_status(results):
    meta = results.get("meta", {})
    problems = []
    if meta.get("assumption_status") != "approved":
        problems.append(
            f"状态门禁：结果是 `{meta.get('assumption_status')}` 状态，不是 `approved`。"
            "未经确认的假设不得产出正式估值、评级与目标价。"
        )
    for field in ("confirmed_by", "confirmed_on"):
        if not meta.get(field):
            problems.append(f"状态门禁：确认记录缺 `{field}` —— 分析师没签字就不能出正式结果。")
    return problems


def check_versions(results, report_text):
    meta = results.get("meta", {})
    problems = []
    if report_text is None:
        return problems
    pairs = [
        ("模型结果版本", meta.get("model_version")),
        ("假设版本", meta.get("assumption_version")),
    ]
    for label, expected in pairs:
        if not expected:
            problems.append(f"版本一致：结果文件里没有 `{label}`，无法比对。")
            continue
        match = re.search(rf"\*\*{label}\*\*\s*[：:]\s*([^\s（(]+)", report_text)
        if not match:
            problems.append(f"版本一致：成品的元信息块里没有 `{label}`。")
            continue
        actual = match.group(1).strip()
        if actual != str(expected):
            problems.append(
                f"版本一致：成品写的是 `{label}` {actual}，结果文件是 {expected} —— 报告没跟上模型。"
            )
    return problems


def check_deprecated(deprecated, report_text):
    problems = []
    if report_text is None:
        return problems
    for path, block in deprecated:
        values = block.get("deprecated_values", "")
        for value in [v.strip() for v in values.strip("[]").split(",") if v.strip()]:
            if value in report_text:
                problems.append(f"废弃内容：成品里出现了被作废的数字 `{value}`（来自 {path}）。")
        if path.as_posix() in report_text:
            problems.append(f"废弃内容：成品引用了已作废的文件 {path}。")
    return problems


def check_dates(results):
    meta = results.get("meta", {})
    problems = []
    for field in DATE_FIELDS:
        value = meta.get(field)
        if not value:
            problems.append(f"日期完整：缺 `{field}`。四个日期是四件事，不许合并或省略。")
        elif not DATE_PATTERN.match(str(value)):
            problems.append(f"日期完整：`{field}` 取值 `{value}` 不是 YYYY-MM-DD 格式。")
    return problems


def check_sources(results):
    """每个正式数字都要有出处：历史数字引 source_id，假设引已登记的 assumption_id。

    来源的**引用完整性**在 `load_inputs` 就已经把关（引用了没登记的 id 会直接报错），
    这里查的是「有没有漏掉没引的」—— 结果文件里每个报告期、每条假设都得有出处，
    空出处照样拦。
    """
    provenance = results.get("provenance")
    if not provenance:
        return ["来源齐全：结果文件里没有 `provenance` 块，无法确认每个数字的出处。"]

    problems = []
    for item in provenance.get("periods", []):
        if not item.get("source_id"):
            problems.append(f"来源齐全：报告期 `{item.get('period')}` 没有 `source_id`。")
        if not item.get("source_tier"):
            problems.append(f"来源齐全：报告期 `{item.get('period')}` 没有 `source_tier`。")

    assumptions = provenance.get("assumptions") or []
    if results.get("meta", {}).get("mode") == "formal" and not assumptions:
        problems.append(
            "来源齐全：正式模式下 `provenance.assumptions` 是空的 —— "
            "每条假设都要登记出处，不能只给数字不给依据。"
        )
    for item in assumptions:
        if not item.get("id"):
            problems.append(f"来源齐全：假设 `{item.get('item')}` 没有登记 id。")
        if not item.get("source_id"):
            problems.append(f"来源齐全：假设 `{item.get('id')}` 没有 `source_id`。")
        if item.get("status") not in ("candidate", "approved", "derived", "reported"):
            problems.append(
                f"来源齐全：假设 `{item.get('id')}` 的状态是 `{item.get('status')}`，"
                "假设只能是 candidate / approved / derived / reported。"
            )
    return problems


ALL_CHECKS = (check_status, check_versions, check_deprecated, check_dates, check_sources)


def run_gates(results, report_text=None, scan_dirs=(), report_path="output/investment-report.md"):
    """跑全部五项，返回问题清单。空清单 = 全过。"""
    problems = []
    problems += check_status(results)
    problems += check_versions(results, report_text)
    problems += check_deprecated(collect_deprecated(scan_dirs), report_text)
    problems += check_dates(results)
    problems += check_sources(results)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="统一模型输出门禁")
    parser.add_argument("--results", required=True)
    parser.add_argument("--report", help="成品 Markdown，用于比对版本与扫废弃数字")
    parser.add_argument("--scan", nargs="*", default=[], help="扫 deprecated 状态块的目录")
    args = parser.parse_args(argv)

    try:
        results = read_json(args.results)
    except (OSError, json.JSONDecodeError) as error:
        print(f"读不了结果文件：{error}", file=sys.stderr)
        return 2

    report_text = None
    if args.report and Path(args.report).exists():
        report_text = Path(args.report).read_text(encoding="utf-8")

    problems = run_gates(results, report_text, args.scan)

    if problems:
        print("输出门禁未通过，不导出：")
        for item in problems:
            print(f"  - {item}")
        return 1

    print("输出门禁五项全部通过，可以导出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

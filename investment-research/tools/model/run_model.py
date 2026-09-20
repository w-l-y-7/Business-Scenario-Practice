"""统一模型命令行入口。三个子命令：

    validate  只校验，不计算 —— 输入 schema、四个日期、单位、来源引用
    run       跑模型，落结果 JSON 与渲染表格
    gates     输出门禁，导出 PDF 前必须全过

用法（依赖走 uv 临时隔离环境，见 `model/README.md`）：

    uv run --with-requirements tools/model/requirements.txt python tools/model/run_model.py validate

    uv run --with-requirements tools/model/requirements.txt python tools/model/run_model.py run `
      --inputs model/inputs/historical.yaml `
      --assumptions model/assumptions/candidate.yaml `
      --out model/results/valuation.json `
      --render model/results/valuation-tables.md --mode test

    uv run --with-requirements tools/model/requirements.txt python tools/model/run_model.py gates `
      --results model/results/valuation.json `
      --report output/investment-report.md --scan analysis model/results

默认是 `--mode formal`：要求假设文件 `status: approved` 且确认记录齐全。
用候选假设或合成数据跑测试时显式写 `--mode test` —— 测试结果**不进正式输出**。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import engine, gates, render, schema  # noqa: E402
from model.errors import ModelError  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_REGISTER = REPO / "model/inputs/source_register.csv"


def load_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_register(path, mode):
    """读 source_register.csv。文件不存在时返回 None，由调用方决定要不要报错。"""
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    # CSV 由 Excel / PowerShell 导出，可能是 utf-8-sig，剥掉 BOM
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return schema.load_source_register(rows, mode=mode)


def resolve_register(args, mode):
    register = load_register(args.register, mode)
    if register is None and mode == "formal":
        raise ModelError(
            f"正式模式必须提供来源登记表，但 `{args.register}` 不存在。"
            "来源索引是证据基础 —— 没有它无法确认每个数字的出处。"
            "先用 data-collector 建好 source_register.csv，或用 --mode test。"
        )
    return register


def cmd_validate(args):
    """只校验，不计算。校验过不了就不必往下跑。"""
    register = resolve_register(args, args.mode)
    inputs = engine.load_inputs(load_yaml(args.inputs), register, args.mode)
    assumptions = engine.load_assumptions(load_yaml(args.assumptions), args.mode, register)

    print(f"输入校验通过：{args.inputs}")
    print(f"  报告期：{'、'.join(inputs['periods'])}")
    print(f"  四个日期：信息截止 {inputs['meta']['info_cutoff']} / "
          f"行情 {inputs['meta']['price_date']} / "
          f"估值基准 {inputs['meta']['valuation_date']} / "
          f"目标 {inputs['meta']['target_date']}")
    print(f"  来源登记表：{'已加载，' + str(len(register['rows'])) + ' 条' if register else '未提供（仅 test 模式允许）'}")
    capital = inputs.get("capital") or {}
    if capital.get("status") == "完成":
        print(f"  资本结构：股本桥已闭合，口径截至 {capital['as_of']}")
        proceeds = capital["h_share_proceeds"]
        print(f"  H 股募集资金现金桥：{proceeds['status']}")
    else:
        print(f"  资本结构：{capital.get('status')} —— {capital.get('reason')}")

    gaps = inputs.get("articulation_gaps") or []
    if gaps:
        print(f"  勾稽字段缺口 {len(gaps)} 项（记为「未检索」，不按 0 算）")

    print(f"假设校验通过：{args.assumptions}")
    print(f"  状态：{assumptions['status']} / 版本 {assumptions['version']}")
    print(f"  假设登记：{len(assumptions.get('register') or {})} 条")
    unresolved = [
        entry.id for entry in (assumptions.get("register") or {}).values()
        if entry.status == "candidate"
    ]
    if unresolved:
        print(f"  仍待确认的假设 {len(unresolved)} 条：{'、'.join(sorted(unresolved))}")
    return 0


def cmd_run(args):
    register = resolve_register(args, args.mode)
    inputs = engine.load_inputs(load_yaml(args.inputs), register, args.mode)
    assumptions = engine.load_assumptions(load_yaml(args.assumptions), args.mode, register)
    results = engine.run_model(inputs, assumptions, mode=args.mode)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"结果已写入 {out_path}")

    if args.render:
        render_path = Path(args.render)
        render_path.parent.mkdir(parents=True, exist_ok=True)
        render_path.write_text(render.render_all(results), encoding="utf-8")
        print(f"表格已写入 {render_path}")

    prices = results["prices"]
    print(f"市价        {prices['market_price']:>10,.2f} 元")
    print(f"即期公允    {prices['spot_fair_value']:>10,.2f} 元")
    print(f"12 个月目标 {prices['twelve_month_target_price']:>10,.2f} 元"
          f"（含预期分红 {prices['expected_dividend']:,.2f} 元）")
    print(f"预期总回报  {prices['expected_total_return']:>10.2%}")
    print(f"[{results['meta']['assumption_status']} / "
          f"{results['meta']['assumption_version']} / {args.mode}]")

    if prices.get("alignment", {}).get("aligned") is False:
        print("注意：目标日与预测期年度末不对齐 —— 见结果文件的 prices.alignment")
    if args.mode == "test":
        print("注意：本次是 test 模式，结果仅供模型自测，不得进入正式输出。")
        print("      test 模式的结果**不构成评级或目标价**，未经团队确认不得对外。")
    return 0


def cmd_gates(args):
    results = gates.read_json(args.results)
    report_text = None
    if args.report and Path(args.report).exists():
        report_text = Path(args.report).read_text(encoding="utf-8")
    problems = gates.run_gates(results, report_text, args.scan)
    if problems:
        print("输出门禁未通过，不导出：")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("输出门禁五项全部通过，可以导出。")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="统一估值模型")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, with_assumptions=True):
        p.add_argument("--inputs", default=str(REPO / "model/inputs/historical.yaml"))
        if with_assumptions:
            p.add_argument("--assumptions",
                           default=str(REPO / "model/assumptions/approved.yaml"))
        p.add_argument("--register", default=str(DEFAULT_REGISTER),
                       help="source_register.csv 路径；正式模式必需")
        p.add_argument("--mode", choices=("formal", "test"), default="formal")

    validate = sub.add_parser("validate", help="只校验，不计算")
    common(validate)
    validate.set_defaults(func=cmd_validate)

    run = sub.add_parser("run", help="跑模型")
    common(run)
    run.add_argument("--out", default=str(REPO / "model/results/valuation.json"))
    run.add_argument("--render", default=str(REPO / "model/results/valuation-tables.md"))
    run.set_defaults(func=cmd_run)

    gate = sub.add_parser("gates", help="输出门禁")
    gate.add_argument("--results", default=str(REPO / "model/results/valuation.json"))
    gate.add_argument("--report", default=str(REPO / "output/investment-report.md"))
    gate.add_argument("--scan", nargs="*", default=[])
    gate.set_defaults(func=cmd_gates)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ModelError as error:
        print(f"[模型拒绝出数] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

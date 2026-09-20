"""统一模型入口。

用法：

    python tools/model/run.py \
      --inputs model/inputs/historical.yaml \
      --assumptions model/assumptions/approved.yaml \
      --out model/results/valuation.json \
      --render model/results/valuation-tables.md

默认是 `--mode formal`：要求假设文件 `status: approved` 且确认记录齐全。
用合成数据做测试时显式写 `--mode test` —— 测试结果**不进正式输出**。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import engine, render  # noqa: E402
from model.errors import ModelError  # noqa: E402


def load_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main(argv=None):
    parser = argparse.ArgumentParser(description="统一估值模型")
    parser.add_argument("--inputs", required=True, help="历史输入 YAML")
    parser.add_argument("--assumptions", required=True, help="假设文件 YAML")
    parser.add_argument("--out", required=True, help="结果 JSON 落盘路径")
    parser.add_argument("--render", help="表格 Markdown 落盘路径")
    parser.add_argument("--mode", choices=("formal", "test"), default="formal")
    args = parser.parse_args(argv)

    try:
        inputs = engine.load_inputs(load_yaml(args.inputs))
        assumptions = engine.load_assumptions(load_yaml(args.assumptions), mode=args.mode)
        results = engine.run_model(inputs, assumptions, mode=args.mode)
    except ModelError as error:
        print(f"[模型拒绝出数] {error}", file=sys.stderr)
        return 2

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

    primary = results["valuation"]["primary"]["per_share"]
    print(f"主估值（FCFE）每股 {primary:,.2f} 元 "
          f"[{results['meta']['assumption_status']} / {results['meta']['assumption_version']}]")
    if args.mode == "test":
        print("注意：本次是 test 模式，结果仅供模型自测，不得进入正式输出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

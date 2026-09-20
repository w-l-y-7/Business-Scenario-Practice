"""统一估值模型。

目录约定见 `model/README.md`：

    model/inputs/        历史输入与 source_register.csv 证据索引
    model/assumptions/   候选假设与已确认假设
    model/results/       生成结果
    model/verification/  核验记录

本包是计算程序，位于 `tools/model/`。模块分工：

    schema.py   输入的最小字段集、来源引用、行情口径（pydantic 校验）
    engine.py   计算内核：九模块 + 三情景 + 两组敏感性 + 三表勾稽 + 三个价格
    reverse.py  反向估值：brentq 求市场现价隐含的单一未知量
    gates.py    输出门禁：状态 / 版本 / 废弃数字 / 日期 / 来源
    render.py   结果 → Markdown 表格（`analysis/valuation.md` 里的表由它生成）
    run_model.py  命令行入口：validate / run / gates
"""

__all__ = ["schema", "engine", "reverse", "gates", "render", "errors"]

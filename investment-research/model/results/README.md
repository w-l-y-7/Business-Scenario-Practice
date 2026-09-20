# results/ —— 程序生成的结果

**这个目录下的文件都由 `tools/model/run.py` 生成，不手工编辑。** 手工改过之后，`analysis/valuation.md` 与模型就对不上了，而且没人看得出是哪一处对不上。

| 文件 | 是什么 |
| --- | --- |
| `valuation.json` | 完整结果：逐年预测、三路估值、情景、敏感性、预留项状态 |
| `valuation-tables.md` | 由结果渲染出的 Markdown 表格，直接粘进 `analysis/valuation.md` |

## 生成命令

```
python tools/model/run.py `
  --inputs model/inputs/historical.yaml `
  --assumptions model/assumptions/approved.yaml `
  --out model/results/valuation.json `
  --render model/results/valuation-tables.md
```

## 引用规则

正文与风险章节引用结果时，**标明字段名或行号**，写成「见估值报告」太粗 —— 报告本身也是引用的模型，链条要能一路追到程序。

例：`scenarios.combined_gm_dio`、`valuation.primary.per_share`、`sensitivities.ke_g.table[2][2]`。

## 版本

结果里带 `meta.assumption_version` 与 `meta.model_version`。**正文的版本必须与结果一致**，不一致就是门禁要拦的情形。假设改动后重跑，旧结果标 `superseded`，不要留在原地冒充新结果。

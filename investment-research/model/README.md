# model/ —— 统一模型的输入、假设与结果

`analysis/valuation.md` 是**文稿**，这里的 `model/` 是**模型**。两者分工：

- 文稿层（Markdown）写给人看：判断、依据、口径说明。**不许在其中手工维护正式模型数字。**
- 模型层（这里的结构化文件 + `tools/model/` 的程序）算给机器跑：输入 → 假设 → 结果

**模型表由程序生成，不手工维护。** `analysis/valuation.md` 里的逐年预测表、三路估值表、情景表、敏感性表、反向估值表，全部来自 `model/results/`，手工抄一遍必然对不上，而且抄错了看不出来。

## 目录

| 目录 | 放什么 | 谁写 |
| --- | --- | --- |
| `inputs/` | 历史输入（已发生的事实，无预测）+ `source_register.csv` 证据索引 | `financial-analyst` / `data-collector` |
| `assumptions/` | 候选假设 `candidate.yaml`、确认后的 `approved.yaml` | 候选由 AI 起草，**确认由团队签** |
| `results/` | 程序生成的结果，含 `valuation.json` 与渲染出的表格 | `tools/model/run_model.py` |
| `verification/` | 核验记录（口径核验、勾稽、独立复算、试排检查） | 各环节 |

**`source_register.csv` 是证据索引。** 模型输入只能引用其中存在、且 `status` 允许的 `source_id`；引用未登记的 id 或不允许的状态，模型报错而不是算下去。

## 怎么跑

**依赖不装进全局环境**，走 `uv` 的临时隔离环境。`tools/model/requirements.txt` 只写依赖，命令写在这里。

```powershell
cd investment-research

# 1. 校验输入与假设的 schema、日期、单位、来源引用（不计算）
uv run --with-requirements tools/model/requirements.txt python tools/model/run_model.py validate

# 2. 跑模型（候选假设只能跑 test 模式，正式模式要求 approved）
uv run --with-requirements tools/model/requirements.txt python tools/model/run_model.py run `
  --inputs model/inputs/historical.yaml `
  --assumptions model/assumptions/candidate.yaml `
  --out model/results/valuation.json `
  --render model/results/valuation-tables.md `
  --mode test

# 3. 输出门禁（导出 PDF 前必须全过）
uv run --with-requirements tools/model/requirements.txt python tools/model/run_model.py gates `
  --results model/results/valuation.json `
  --report output/investment-report.md `
  --scan analysis model/results

# 4. 测试套件（171 项，覆盖 schema / 勾稽 / 资本结构桥 / 两路 FCFE 与 FCFF /
#    情景 / 敏感性方向 / 门禁 / 渲染）
uv run --with-requirements tools/model/requirements.txt python -m pytest tools/model/tests -q
```

测试夹具走的都是**正式代码路径**（`engine.load_inputs` / `load_assumptions`），
不是手工拼的 dict —— 手工拼的 dict 绕过了输入层，而输入层恰恰最该测。
用合成数据只为数字好看，代码路径与真实数据一致。**合成数字不得引用。**

## 依赖记录

| 项 | 版本 / 值 |
| --- | --- |
| uv | 0.10.11 |
| python | 3.14.3 |
| pydantic | 2.13.5 |
| scipy | 1.18.1 |
| pytest | 9.1.1 |
| PyYAML | 6.0.3 |
| **依赖实测日期** | **2026-09-20** |

依赖清单见 `tools/model/requirements.txt`。**写进去的每个版本都是本机实测跑通的版本，且必须能通过 `uv run --with-requirements` 复现。** 全局环境里装了什么不算数 —— 这里没写就不许 import。

> **「依赖可用」不等于「真实模型已跑通」。** 上面这张表只说明这些包能装上、能 import。它不说明 `model/inputs/` 里的真实数据填齐了，也不说明模型算出来的结果对。**判断模型跑通与否要看**：真实历史数据是否录入并通过 schema 校验、测试套件是否全过、结果是否来自 `approved` 版本的假设。三条都满足才算跑通。

## 四条硬规矩

1. **缺失数据不得默认为零。** 输入缺了，程序报错，不静默按 0 参与计算。报错信息会点出缺哪个字段。
2. **未经确认的假设不得产出正式结果。** `candidate.yaml` 只能跑 `--mode test`；`--mode formal` 要求 `status: approved` 且确认记录（确认人、日期、版本）齐全。**AI 不得预填确认记录。**
3. **四个日期一个都不能少，且目标期限固定 12 个月。** `info_cutoff` / `price_date` / `valuation_date` / `target_date` 全填，日期写 `YYYY-MM-DD`；`target_date` 必须等于估值基准日加 12 个自然月。
4. **检查没过，不导出。** 门禁全过才导出 PDF。

## 口径

金额 **亿元**、股本 **亿股**、每股价值 **元**。利润与现金流一律**归母口径**。`debt` 是**有息债务**，`cash` 单列 —— 现金不是负债务，在 EV → 股权价值的桥里处理。

**FCFF 的 WACC 用有息债务的市场价值**，不用净债务。**FCFE 与 FCFF 不做加权合成**：FCFE 是主估值，前瞻可比做交叉检验，FCFF 做一致性核验 —— 三者并列呈现，不靠权重抹平。

> **「分歧超过阈值时阻塞输出」这条还没实现。** 阈值是要团队定的数，不能由 AI 预设一个。
> 阈值定下来之前，`gates.py` 的五项检查里**没有**这一项 —— 现在的结果是三个口径并列报出，
> 分歧由人判断。**不要以为门禁会替你拦住分歧。**

## 输出门禁的五项

`run_model.py gates` 检查这五项，全过才允许导出：

| # | 检查 | 拦什么 |
| --- | --- | --- |
| 1 | 状态门禁 | 结果必须来自 `approved` 假设，且确认人、确认日期齐全 |
| 2 | 版本一致 | 成品的假设版本 / 模型结果版本与结果文件一致（报告没跟上模型就拦） |
| 3 | 废弃内容 | 被标 `deprecated` 的旧目标价、旧评分、旧文件不得混进成品 |
| 4 | 日期完整 | 四个日期齐全且是 `YYYY-MM-DD` |
| 5 | 来源齐全 | 每个报告期有 `source_id` + `source_tier`，每条假设有登记 id 与出处 |

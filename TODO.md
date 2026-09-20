# 任务清单

## 这个文件怎么用 + 怎么配合 /loop

**TODO.md 是什么**

一张任务清单纸。干正事之前，先把要做的事按下面的格式记进来，标好状态，就不用靠脑子记了。

**/loop 是什么**

一个「定时重复器」。它让 Claude 每隔一段时间，把你交代的那句话重新执行一遍，一直循环，直到你喊停。适合反复盯进度、批量推进任务这类事。

**怎么配合用（三步）**

1. 先把任务写进下面的 task 块，状态填 `pending`。
2. 用 /loop 让 Claude 去干活。注意：/loop 只是「反复执行你交代的话」，Claude 不会自动知道你有个 TODO.md，所以交代的话里一定要写清楚「先读 TODO.md」。
   - 想定时推进，比如每 10 分钟干一件：
     `/loop 10m 打开 TODO.md，找第一个 pending 任务，动手做完，把状态改成 completed，再继续下一个`
   - 想一口气把清单清完、节奏让 Claude 自己把控（不带时间间隔）：
     `/loop 打开 TODO.md，把里面所有 pending 任务按顺序做完，做完一项就更新一次状态，全做完向我汇报`
3. 中途想停：直接发消息说「停掉 /loop」就行。

**几个提醒**

- /loop 每次重新执行，等于把你那句话从头再做一遍，不记得上一轮干了啥，所以那句话要写全（写清看 TODO.md、按什么顺序、做完怎么更新状态）。
- 只对「需要重复 / 需要盯进度」的事有意义。一次性任务直接交代即可，别用 /loop。

状态只有三种：`pending`（没开始）、`in_progress`（在做）、`completed`（做完了）。

## task-001

- 状态：pending
- 描述：决定 Business Scenario Practice 要不要装 `.githooks/pre-commit`。参考 `investment project` 那份：它读 `save-gate/` 下的 test.passed 和 quality.passed 标记，而标记是 quality-engineer 和 tester 两个 subagent 生成的 —— 这两个 agent 在 BSP 已经删掉，直接搬过来会永久拦下所有带 `.py` 的提交。两个选项：一是不装钩子（BSP 以文档和流程为主，本来也不适合代码门禁），二是写个轻量版（提交前自动拦密钥和大文件）

## task-002

- 状态：pending
- 描述：补齐 `workspace/.claude/CLAUDE.md` 文件路由表引用的 8 个 skill（minimax-xlsx、minimax-docx、mineru、pdf、minimax-pdf、pptx-generator、work-report、doc-coauthoring）。这 8 个当前一个都没装 —— 往 `inbox/` 丢文件后，loop 扫到便签会去调不存在的技能。两条路：逐个建成真实 skill，或者改路由表让它在技能不存在时先问用户

## task-003

- 状态：pending
- 描述：**investment-research P2 收尾** —— 把 `model/inputs/historical-gapfill.yaml`（36 个带页码的值）合并进 `model/inputs/historical.yaml`；给 6 个报告期补齐块级元信息（unit / currency / period_start / period_end / publication_date / source_file / source_tier / assurance_status / status）；补 `capital_structure` 块（股本桥 + 限制性股票 + H 股募集资金现金桥 + 四种股数口径）；`price_date` 改成实际交易日并加 `market_quote` 块。顺手订正 2024A `total_assets` 的页码（现标 p.96，实际在 p.93/p.94）。做完重跑 `validate` 和 `tools/model/tests`。背景见 `investment-research/model/verification/P0-P6执行进度-2026-09-20.md`

## task-004

- 状态：pending
- 描述：**investment-research P4 收尾** —— 删掉旧脚本 `tools/model/run.py`、`gate_check.py`、`selfcheck.py` 及 `__pycache__`。**不能只删文件**：这三个名字还被 10 处引用着（`financial-analyst`、`report-writer`、`valuation` 技能、`tools/pdf/build.ps1`、`tools/README.md`、`model/results/README.md`、`templates/cover/README.md`、`tools/pdf/smoke/试排.md`，以及 `model/verification/` 下的历史核验记录），要一并改成 `run_model.py` / `gates.py` / `tests`。**历史核验记录里的引用不改**（那是当时的实况）。改完再 grep 一遍，确认没有指向不存在文件的路线

## task-005

- 状态：pending
- 描述：**investment-research P6 试排** —— 用 `tools/pdf/build.ps1` 出 2–3 页 PDF 样张，测 ESG 表、敏感性表、超宽来源行、页码、字体嵌入、正文/附录分页，以及 CFA 官方封面（`templates/cover/cover-official.docx`）能不能排进去。封底仍未解决（CFA 只提供封面，无封底模板）

## task-006

- 状态：pending
- 描述：**investment-research P0 收尾** —— 给 `.claude/rules/data-standard.md` 补上 12 字段块与四态表述（未检索 / 已检索未找到 / 未披露 / 不适用）；跑 `rg -n "skills/governance|analysis/governance.md|governance" .` 并逐个分类剩余命中（应修改的旧引用 / 合法历史说明 / deprecated 文件）。**不允许存在还能路由到旧 skill 的有效引用**

## task-007

- 状态：pending
- 描述：**investment-research 交付** —— 装出 11 项报告，然后**停在人在回路节点②**。不得自动创建 `approved.yaml` 的确认记录，不得发布正式目标价、评级或英文终稿，不得自动 git 提交

## task-008

- 状态：pending
- 描述：**investment-research 已知未实现项**（三条都要团队定或写进报告口径）：① 三口径（FCFE 主估值 / 前瞻可比 / FCFF 一致性）分歧超过阈值时阻塞导出 —— `gates.py` 里**没有**这一项，阈值要团队定，不能由 AI 预设，所以现在分歧只能由人判断；② `scenarios`（牛熊偏置）与 `comparables` 两块不在假设登记覆盖范围内（现在只查 `forecast` / `discount` / `terminal`）；③ 目标价分母用的是预测期股数、**不含潜在奖励稀释** —— 报告里必须写明这个口径，否则会与「已发行 + 潜在奖励」的稀释口径混

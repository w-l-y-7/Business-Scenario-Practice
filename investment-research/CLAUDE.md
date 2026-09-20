# CLAUDE.md — 上市公司深度研究项目规则

## 项目信息

- 项目名：investment-research
- 目标：生成一份符合 **2026 年 CFA 投资分析比赛校赛**要求的英文投资研报
- 研究对象：中际旭创（300308.SZ）
- 创建日期：2026-09-12

> 说明：目录结构、`CLAUDE.md`、`.claude/rules/` 两份规范、`.claude/skills/` 技能与 `.claude/agents/` 角色均已就位。
>
> **「已就位」不等于「跑通」。** 截至 2026-09-20，这条流水线**尚未端到端跑完一轮** —— 六份中间报告只产出三份（`financial`、`industry`，以及已作废待重算的 `valuation`），`business.md`、`esg.md`、`risks.md` 未生成，`output/investment-report.md` 未生成。结构齐备只说明各环节的定义写完了，**不代表串起来能跑出合格成品** —— 判断跑通与否要看有没有一份完整成品走到底、过程中的缺口有没有被填上。
>
> **唯一跑通的一段是 PDF 工具链**：样张 `tools/pdf/smoke/试排.md` 已出片并通过**五项**版式检查（页数 / 溢出 / 页码 / 图片 / 内容），明细见 `model/verification/PDF工具链重构-2026-09-19.md`，用法见 `tools/pdf/README.md`。**已解决**：CFA 官方前封面（Word 可编辑版）已到手，落在 `templates/cover/cover-official.docx`。**未解决**：官方无封底模板，试排的封底仍是占位块。

### 比赛硬性要求（摘要）

正文全英文、PDF 提交、A4、正文 ≤ 10 页、附录 ≤ 10 页、每页标页码、封面封底用 CFA 规定模板且不计入正文、使用 AI 必须注明、引用须标来源、计算底稿须保留。完整规则见 `.claude/rules/output-format.md` 第一节。

**提交截止：2026-10-08 中午 12:00**（校赛说明）。赛程：报告提交 → 6 队入围 → 10 月下旬校赛现场决赛（路演 + 答辩）→ 前 2 队代表学校参加华南本地赛。**官方规则原文在 `reference/cfa-rules/`**，与本目录的逐条比对见 `reference/README.md`。

## 一、路径规范

- `raw_data/`：原始数据存储路径，由 data-collector 独占写入
- `analysis/`：六份分析报告路径，由 company-analyst、financial-analyst、risk-analyst 写入
- `model/`：统一估值模型的数据与状态。`inputs/` 历史输入与 `source_register.csv` 证据索引、`assumptions/` 候选与已确认假设、`results/` 程序产出、`verification/` 核验记录
- `tools/`：脚本。`model/` 下是估值程序（用法见 `tools/model/README.md`），`pdf/` 下是排版程序（用法见 `tools/pdf/README.md`）
- `figures/`：研报插图存放处。**本项目不产图** —— 图由使用者自绘后放进这里，规范见 `figures/README.md`
- `reference/`：外部参考资料（官方规则原文、书面报告指引、历届冠军报告与路演）。**不是本项目的数据** —— 中际旭创的材料在 `raw_data/`。只读
- `templates/cover/`：CFA 官方前封面落点（**封面已到**，Word 可编辑版 `cover-official.docx`；**官方未提供封底模板**，见 `output-format.md` §1.5）
- `build/`：PDF 编译产物，不入库
- `output/`：最终交付物路径，由 report-writer 写入
- **禁止跨目录写入**：采集 agent 不写 `analysis/`，分析 agent 不写 `output/`
- **量化只从模型出**：估值、情景、敏感性、反向估值的每个数字由 `tools/model/run_model.py` 算出并落在 `model/results/`，风险与撰写角色**只引用、不自己造数**。**`analysis/valuation.md` 是说明层，不是计算引擎 —— 不许在里面手工维护正式模型数字。**

## 二、数据来源声明

所有引用的数字必须标注来源，格式如下：

- 财报数据：`[指标名称]（来源：[年报/季报名称]，第 X 页）`
- 研报数据：`[指标名称]（来源：[券商名称]，[报告标题]，[日期]）`
- 新闻信息：`[事件描述]（来源：[媒体名称]，[日期]）`
- 计算指标：`[指标名称]（计算方式：[公式]，基于 [原始数据来源]）`

**禁止使用无来源标注的数字。** 如果某项数据无法确认来源，标记为 `[待核实]`，并在审阅阶段提醒分析师。

来源的可信度分级、口径标注要求、缺口处理方式，见 `.claude/rules/data-standard.md`。

## 三、免责声明

产出文件末尾必须包含声明，**中英文两版，各自原文照抄，一个字都不能改**：

**成品报告 `output/investment-report.md`（英文）**，`[date]` 填数据截止日期：

```
---
Disclaimer: This report was prepared with the assistance of AI tools for research
and educational purposes only. It does not constitute investment advice. All data
and conclusions must be independently verified by a qualified professional before
being used for any investment decision. Data as of [date]; completeness and
timeliness are not guaranteed.
---
```

**中间报告 `analysis/`（中文）**，`[日期]` 填数据截止日期：

```
---
免责声明：本报告由 AI 辅助生成，仅供研究参考，不构成投资建议。
所有数据和分析结论需经专业人士独立核验后方可用于投资决策。
数据截至 [日期]，不保证信息的完整性和时效性。
---
```

两版都是**按校赛要求推断的措辞**，拿到官方模板或机构要求后替换。

## 四、输出格式

最终交付物是一份 CFA 投资分析比赛研报，章节固定如下：

> **固定标题是项目自我约束，不是赛事原文的规定。** 校赛规定的是**必含哪几节**，没有找到「标题一个字不许改」的明文。沿用固定标题图的是跨版本可比、索引可查，方向对；但**不要把它当成不能问的硬规定** —— 拿到官方规则原文后，以原文为准。

```
【封面】CFA 协会规定模板 —— 不计入正文

【正文第 1 页开头 —— 七项必填】
① Business Description
② Industry Overview and Competitive Positioning
③ Investment Summary
④ Valuation（FCFE 逐年预测为主估值，校赛必含）
⑤ Financial Analysis
⑥ Investment Risks
⑦ Environmental, Social, and Governance（ESG 三块都要写；治理是其中 G 的核心块）

References
AI Usage Disclosure
Appendices（数据来源清单 + 计算底稿）

【封底】CFA 协会规定模板 —— 不计入正文
```

**第 ⑦ 节用名已定：`Environmental, Social, and Governance`。** 校赛说明写「公司治理」，官方规则与 Appendix D 评分表写 `Environmental, Social, and Governance`（15 分）；官方规则第 4 节另规定学校自评报告时**必须按 Appendix D 的标准打分**，而 Appendix D 那一节就叫这个名字。**评分用名是 ESG，故取官方用名，环境（E）、社会（S）、治理（G）三块都要有实质内容。** 证据与出处见 `reference/README.md`。

**七项必填抬头**（正文第 1 页开头）：公司名称、交易所、股票代码、**`Sector/Industry`**（一项填两个值：GICS 板块 + 行业）、投资建议（BUY / HOLD / SELL）、现价（注明日期）、目标价（注明相对现价的涨跌百分比）。

**四个日期是四件事，不许合并、不许省略**：信息截止时间、行情日期、估值基准日、目标日期。目标期限 12 个月。**估值基准日目前仍是 `candidate`，未经团队确认不得升为 `approved`。**

`analysis/` 下六份中间报告（business / industry / valuation / financial / risks / esg）的骨架、页数配比、AI 披露节写法，见 `.claude/rules/output-format.md`。

## 五、人在回路节点

以下环节**必须暂停等待分析师确认**，不得自行越过：

1. **数据源确认**：采集完成后，确认数据是否齐全、是否可靠
2. **核心假设审查**：逐年预测假设（收入增速、净利率、周转、CapEx、融资）、终值假设、可比集合等关键参数。**确认记录里必须有真实的确认人、日期、假设版本，不能预填**；阈值一旦跨过，才允许用这套假设出正式估值、评级与目标价。
3. **分析逻辑审查**：因果关系是否成立，结论是否过度外推
4. **结论措辞审查**：评级和目标价的措辞是否合理审慎
5. **免责声明合规**：确认声明内容完整且符合比赛要求
6. **AI 披露合规**：确认 AI 使用披露一节如实、完整，未少报或含糊
 
> 校赛明文要求保留**计算底稿**备查，所以估值模型的每一步中间量都要留在 `analysis/valuation.md` 和附录里，不能只给最终结果。

暂停时向分析师说明：当前到了哪个节点、需要确认什么、有哪些可选方案、各自的依据是什么。**确认之前不进入下一步。**

## 六、财报 PDF 工具链

`raw_data/earnings/` 下除关键指标 Markdown 外，另归档**财报 PDF 原件**（巨潮资讯网下载，A 级来源）。原件文件名按报告期命名，如 `中际旭创-2026半年报.pdf`。

**PDF 原件不入 git**（体积大且不会再变），已在仓库根 `.gitignore` 写明。连同 `temp/` 下的中间产物一起忽略。

处理 PDF 用 `tools/` 下的脚本，靠 `uv` 免装环境运行：

```powershell
# PDF → 带页码标记的纯文本（temp/pdf-text/）
uv run --with pdfplumber python tools\pdf_to_text.py -o temp\pdf-text <pdf...>

# 纯文本 → 按主题摘出关键章节（temp/pdf-digest/）
uv run --with pdfplumber python tools\extract_key_sections.py temp\pdf-text temp\pdf-digest
```

**为什么两步走**：一份年报两三百页，全量读会淹掉重点。转文本时每页插一行 `[[page N]]` 标记，摘录时按关键词定位 —— 这样下游引用的每个数字都能带页码，满足校赛「引用须标来源」与「保留计算底稿」的要求。

三个已知的坑，详见 `tools/PDF处理工具使用说明.md`：无边框表格要换 `text` 策略才抽得出；中文乱码说明该 PDF 没有文本层、需 OCR；跨页表格的表头只在第一页。

## 七、数据来源等级现状

`raw_data/earnings/` 下文件的可信度等级以**来源块里的标注为准**，不一律而论：

- **A 级**：来自已归档的财报 PDF 原件，带页码，可逐页回溯
- **B 级**：来自 akshare 数据终端（新浪财经 / 东方财富），无页码

等级写作「A 级」，不写「A 类」。**等级之外还有三个各自独立的属性**，不能互相替代：

| 属性 | 取值 |
| --- | --- |
| 审计 / 鉴证状态 | 经审计 / 未经审计 / 经审阅 / 不适用 |
| 事实或观点 | 事实 / 观点 |
| 是否交叉核验 | 单一来源 / 已交叉核验（N 路） |

**公司自己的 ESG 报告不因「ESG」二字一律降为 C 级** —— 按 `data-standard.md` §4.3 的三条件检验定级，够格就给 A 或 B。

同一指标两个来源打架时取等级高的，并在备注写清分歧。行情数据（股价、市值）目前只有 B 级来源。

**状态词是四种，不是两种。** `未检索`（本轮没查）/ `已检索未找到`（查了没有）/ `未披露`（公司没说）/ `不适用`（对该对象不成立）—— 四者含义不同、下一步动作不同，**不许互相顶替**。往下一层，**模型输入的 `status` 取值**是 `reported / derived / candidate / approved / deprecated / missing`（见 §八）。

四个日期的取值见 `.claude/rules/data-standard.md`：行情日期 ≠ 估值基准日。首轮行情日期定为 **2026-09-18**；遇休市取**前一个交易日**，并把实际交易日如实写出来。

**正式行情不得使用提交截止日的收盘价。** 提交截止是 **2026-10-08 中午 12:00**，该日收盘价在截止时点还不存在。正式行情必须取**截止前最近一个已经完成交易日**的收盘价，并保存该实际交易日日期。初稿的行情日期 2026-09-18 是暂定值，**该日是否交易日尚未核实**。

## 八、模型输入的最小字段集（每个原始输入都要带）

`model/inputs/` 下的每一条原始输入，**至少**带下面这些字段，缺一个就不许进模型：

| 字段 | 说明 |
| --- | --- |
| `value` | 数值本身 |
| `unit` | 单位（亿元 / 亿股 / 元 / % …） |
| `currency` | 币种（CNY / HKD / USD …） |
| `period_start` / `period_end` | 期间起止 —— 期间数与时点数都要能定位 |
| `publication_date` | 该数字对外披露的日期 |
| `source_file` | 来自哪个文件 |
| `page` | 页码（无页码的来源写「不适用」及理由） |
| `source_tier` | 来源等级 A / B / C / D |
| `assurance_status` | 审计 / 鉴证状态 |
| `status` | `reported` / `derived` / `candidate` / `approved` / `deprecated` / `missing` |
| `notes` | 口径、分歧、待核实说明 |

**模型的输入只能引用 `source_register.csv` 里存在、且 `status` 允许的 `source_id`。** 引用一个没登记过的 id，或引用 `status` 不允许的条目，模型必须报错而不是算下去。注册表是证据索引，不是可选台账。

**下游禁止直接写 `raw_data/`。** 新材料一律由 `data-collector` 归档并登记进 `source_register.csv`，别处只读。

**资金面来源的用法限定**：财联社、中国证券报、同花顺可用于**资金面旁证**；雪球、今日头条、财富号**只作线索**，其中的关税、清单、税率、禁令说法**必须回溯到基金报告、公司公告或政府原文**（USTR / BIS / CBP 等）才能形成关键结论，找不到官方依据的一律标 `unverified`，**不进正式模型**。

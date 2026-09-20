# reference —— 外部参考资料

赛事方与往届优胜者的原始文件。**这里不是本项目的数据** —— 中际旭创的财报、券商研报、新闻在 `raw_data/`，由 `data-collector` 独占写入。本目录只放「别人做的、给我们照着学和对着查的东西」。

```
reference/
├── cfa-rules/          赛事官方规则原文
└── past-champions/     历届全球冠军的书面报告与路演 PPT（2020–2026）
```

## cfa-rules/

| 文件 | 是什么 | 页数 |
| --- | --- | --- |
| `CFA-RC-官方规则-2026-2027赛季.pdf` | CFA Institute Research Challenge 官方规则全文，含 7 个附录 | 22 |
| `CFA-RC-书面报告指引.pdf` | Appendix A 的单行本，书面报告要求 + 评分表 | 2 |

**来源**：https://www.cfainstitute.org/-/media/documents/support/research-challenge/challenge/research-challenge-official-rules.pdf
**采集日期**：2026-09-19

官方前封面的**可编辑 Word 版**不在本目录，已落到 `../../templates/cover/cover-official.docx`（那里是项目指定的落点），来源见同目录的 `来源.md`。

这两份文件关掉了 `README.md` 待办里「2026 年官方规则核对」那一项 —— 规则原文与提交时点都拿到了。抽出的要点见下节。

## past-champions/

14 份，2020–2026 每年一份书面报告 + 一份路演 PPT。清单与原始链接见该目录自己的 `README.md`。

选用范围的理由：赛事规则与页数要求逐年变过，2008–2019 那批的格式与现在对不上；PPT 目前只在入围现场决赛时才用得上，一并下齐留作风格参考。赛事官方索引页：https://www.cfainstitute.org/en/societies/challenge/past-champions

**用法限定**（`../.claude/rules/output-format.md` §1.5 已写明）：**只借视觉风格与论点结构**。版式规则、页数上限、章节结构一律以官方规则为准 —— 参考作品用了几页、怎么配色，都不是能改规则的理由。

## 这些 PDF 不入 git

仓库根 `.gitignore` 已有 `investment-research/**/*.pdf`，本目录 68.8 MB 全部自动忽略。本地照常可读可检索。

---

## 规则原文抽出的要点（2026-2027 赛季）

抽自 `cfa-rules/` 那份 PDF，页码是该 PDF 的页序。**这几条与项目现有规范有出入，见每条的标注。**

### 硬性要求

| 项 | 官方原文说 | 与项目现状对比 |
| --- | --- | --- |
| 正文篇幅 | ≤ 10 页 A4，**不含 CFA 协会提供的前封面**（Appendix A，第 16 页） | 一致 |
| 附录篇幅 | ≤ 10 页 A4（同上） | 一致 |
| 纸张 | A4，210 mm × 297 mm（同上） | 一致 |
| 引用体例 | **须用通行引用体例**，明文举例 Chicago Manual of Style、Harvard、MLA（规则原文出现三次） | **不一致** —— 项目用的是自订的 `(Source: …)` 括注，不属于这三套。已要求 References 补正式条目，见 `output-format.md` §2.3 |
| 封面 | **必须用 CFA 协会提供的前封面，只填高亮处，其余部分含 CFA 标志一律不得改动**（同上） | **已获取** —— 官方 Word 可编辑版，见下；**官方未提供封底模板** |
| 必含章节 | Business description / Industry overview and competitive positioning / Investment summary / Valuation / Financial analysis / Investment risks / **Environmental, social, and governance**（同上，原文注明「包括但不限于」） | **与校赛说明对不上** —— 校赛说明第 ⑦ 项写的是「公司治理」，官方指引与评分表写的是 Environmental, Social, and Governance |
| 抬头字段 | `Company name / Exchange / Ticker symbol / **Sector/Industry** / Recommendation / Current price (as of __ date) / Target price (% increase/decrease)` —— 规则 PDF 第 16 页把 Sector 与 Industry 合写为**一项** | 项目 7 项里只写了 `Industry`，**Sector 掉了**。同一批文件的 Appendix A 单行本（`CFA-RC-书面报告指引.pdf` 第 1 页）又把两词**拆成两项** —— 三处口径不一，取最保险的写法 `Sector/Industry` 并两个值都填 |

### 评分表（Appendix D，第 19 页，总分 100）

| 章节 | 满分 |
| --- | --- |
| Business Description | 5 |
| Industry Overview & Competitive Positioning | 10 |
| Investment Summary | 15 |
| Valuation | 20 |
| Financial Analysis | 20 |
| Investment Risks | 15 |
| **Environmental, Social, Governance** | **15** |
| 合计 | 100 |

**ESG 占 15 分，与 Investment Summary、Investment Risks 同档。**

**用名有分歧，须用户定：** 校赛说明第 ⑦ 项写「公司治理」（与项目原先的 `Corporate Governance` 一致），官方评分表写 `Environmental, Social, and Governance`。官方规则另有一条直接命中校赛场景 —— **学校自评报告时必须按 Appendix D 的标准打分**（规则 PDF 第 12 页），而 Appendix D 那一节就叫 Environmental, Social, and Governance，15 分。**评分用名是 ESG。**

~~项目现行写法（治理为主、E/S 命中重要性才并入）在官方口径下偏窄 —— 15 分那一节，评委大概率会找 E 与 S 的实质内容。改不改见 `README.md` 待办。~~

> **已决（2026-09-20）：第 ⑦ 节完整迁移为 ESG。** 技能 `.claude/skills/governance/` 更名为 `.claude/skills/esg/`，产出路径改为 `analysis/esg.md`，环境（E）、社会（S）、治理（G）三块都写，治理是其中 G 的核心块。**评分用名以官方 Appendix D 为准。** 上面这段保留作决策留痕，不再代表现行做法。

### 封面模板：官方另发 Word 可编辑版（更正）

官方封面**不只是印在规则 PDF 里**。站点另发了一份可编辑 Word 文件 `rc-report-cover-pages-new.docx`（挂在 Student Welcome 页下载清单下），已下载、落到 `../../templates/cover/cover-official.docx`。规则 PDF 的 Appendix C（第 18 页）是同一张封面的印刷版。封面含两部分：

1. **抬头**：CFA Institute Research Challenge / hosted by-in / 赛区名 / Team Name
2. **Disclosures 披露块**（项目目前的免责声明没有这一块）：
   - Ownership and material conflicts of interest —— 成员及家属 [持有/不持有] 标的证券；[知道/不知道] 存在利害冲突
   - Receipt of compensation —— 本文作者报酬不基于投行业务收入
   - Position as an officer or a director —— 成员及家属不在标的公司任董监高或顾问
   - Market making —— 作者不为标的证券做市
   - Disclaimer —— 官方给定的免责声明原文，与项目自订的那版措辞不同

### AI 使用（Appendix B，第 17 页）

官方给的四条要求，比项目现行的三问（用了什么 / 用在哪几环 / 人工把关在哪）**多两条**：

| 官方要求 | 项目现状 |
| --- | --- |
| **Acknowledge** 用了哪些 AI 工具、怎么用、为什么用 | 已覆盖 |
| **Verify** 对照可信来源交叉核验，说明共识程度 | 部分覆盖（数据规范里有交叉核验字段） |
| **Evaluate** 查偏倚、遗漏、其他视角、数据来源的规模与严谨度，说明信心与风险 | **未覆盖** |
| **Reflect** 说明 AI 如何影响了你们的判断，所用 AI 工具与输出的强项与弱点 | **未覆盖** |

官方另注明：**评委很可能会就报告里任何重要数据与结论追问 AI 的使用方式**，参赛队要准备现场解释。

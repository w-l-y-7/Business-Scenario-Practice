# CLAUDE.md

Business Scenario Practice —— 业务场景练习工作区。本文件给 Claude Code 提供在本目录工作的规则。

## 项目概述

两条线，各管各的：

- **技能线**（根目录 `.claude/`）：分两层。**流程技能** 14 个 Superpowers 技能 + 1 个 git-save，管的是「想清楚 → 拆计划 → 验算 → 排错 → 存好档」这套做事方法；**领域技能** 6 个（财报分析、数据分析、基金评估、合规审计、政策简报、跨源研究），管具体的金融分析活。
- **业务线**（`workspace/`）：自动化办公工作区。文件从 `inbox/` 投递进来，按便签拆成任务做完，产出日报、周报，并留痕归档。

使用者是金融专业背景，做金融科技类课题，计算机基础薄弱。解释事情用大白话，术语首次出现配一句说明，别默认对方懂命令行、版本管理或数据结构。

## 技术栈

| 层 | 用什么 |
| --- | --- |
| 运行环境 | Claude Code（Skills、Subagents、Hooks、Loop） |
| 脚本 | PowerShell（这台机器没有可用的 bash，见「环境注意」） |
| 文档格式 | Markdown，全中文，不引入其他格式 |
| 版本控制 | Git（已是仓库，分支 main，远程 `origin` 指向 github.com/w-l-y-7/Business-Scenario-Practice） |

## 目录结构

| 路径 | 是什么 |
| --- | --- |
| `.claude/skills/` | 21 个技能：15 个流程技能（14 个 Superpowers 中文版 + git-save，含原 git-ignore 的扫描能力）+ 6 个金融领域技能。用途见 `.claude/skills/README.md` |
| `.claude/hooks/` | 会话启动 hook；`session-start.ps1` 是实际生效的那个 |
| `.claude/settings.json` | 项目级配置，注册 SessionStart hook |
| `TODO.md` | 待办清单，配 `/loop` 定时推进 |
| `workspace/inbox/` | 待处理文件投递箱 |
| `workspace/tasks/` | 任务工作区，一任务一文件夹 `{YYYY-MM-DD}-{任务名}/` |
| `workspace/daily/` | 每日处理流水 `{YYYY-MM-DD}.md` |
| `workspace/reports/` | 日报、周报成品 |
| `workspace/archive/` | 按月归档 `{YYYY-MM}/` |
| `workspace/templates/` | 文档模板 |
| `workspace/changelog.md` | 任务日志，最新一行在最上面 |

`workspace/` 有自己的 `.claude/`（规则、loop、子代理），细节见 `workspace/.claude/CLAUDE.md`。那套约定只有把 `workspace/` 当项目根打开时才自动生效。

## Skill 使用指引

用自己的话把需求说清楚就行，Claude 会自己挑技能；也可以直接打 `/技能名`。分档说明见 `.claude/skills/README.md`。

**真用得上**：

| 场景 | 走哪个技能 |
| --- | --- |
| 动手做新东西（写论文、做分析、搭工具） | `/brainstorming` 先厘清要什么，再 `/writing-plans` 拆成分步计划 |
| 结果不对、报错、数字对不上 | `/systematic-debugging`，先定位根因再改 |
| 金融计算（收益率、估值、手续费） | `/test-driven-development`，先写下期望值再让它算 |
| 即将声称「做完了」 | `/verification-before-completion`，先跑验证再下结论 |
| 想把改动存到 GitHub | `/git-save`，先扫垃圾文件写 `.gitignore`，再提交推送 |

**领域技能（做金融分析本身用）**：

| 场景 | 走哪个技能 |
| --- | --- |
| A 股公司财报分析、比率计算、同业对比 | `quarterly-financial-analysis`（联网抓三大报表 → 算比率 → 对比行业基准 → 出报告） |
| 分析 CSV / Excel / 数据库文件，或要实时行情 | `smart-data-analysis`（按行数和意图自动选本地 / sqlite / akshare 三条路） |
| 一只基金的综合评估 | `fund-comprehensive-evaluation`（业绩 / 持仓 / 风险 / 合规四路并发） |
| 一笔交易的合规检查 | `investment-compliance`（制裁筛查 + 集中度 + 关联交易 + 风险定级） |
| 把政策 / 研报压成结构化简报 | `policy-brief-generator`（模板成稿 → 检查脚本 → 最多 3 轮精修 → 溯源核对） |
| 跨学术文献 × 市场数据的主题研究 | `cross-platform-research`（**需先配两个 MCP，本机尚未配置**） |

两组容易撞的边界，问清意图再选：①「股价走势 / 现价」→ `smart-data-analysis`；「财报 / 比率」→ `quarterly-financial-analysis`。②`quarterly-financial-analysis` 是**联网抓数自己算**；`investment-research/` 下的 `financial`、`earnings-extract` 是**从已有材料里提取和判断**。同一句话两边都沾边时，先问用户是要补数据，还是要对现有材料下判断。

这 6 个技能的运行时产物（`data/`、`temp/`、`output/`）建在**当前会话工作目录**，仓库根已加入 `.gitignore`。


**偶尔用得上**：`/writing-skills`（把常做的流程固化成新技能）、`/requesting-code-review`、`/receiving-code-review`、`/dispatching-parallel-agents`。

**暂时不用管**：`using-superpowers`、`using-git-worktrees`、`finishing-a-development-branch`、`executing-plans`、`subagent-driven-development` —— 纯软件工程流程，跟课题关系不大。

## 工作区工作流（workspace/）

### 便签系统

便签（`inbox/task-*.md`）是 loop 无人值守处理的**唯一入口**：

- 带便签的文件 → 建任务、移文件、按便签指定的 skill 处理
- 没带便签的文件 → 一律跳过，不动、不记
- `inbox/` 里没有便签 → 静默结束，不输出任何内容

便签必须写到不看对话也能独立执行：涉及哪些文件、要什么产出、用哪个 skill、有无格式或篇幅要求，一次写全。生成便签走 `.claude/rules/inbox-interaction.md`。处理失败时把源文件和便签退回 `inbox/`，在 `changelog.md` 记一行「失败」+ 原因。

### 索引体系

三层索引，任务做完必须同步更新，规则见 `.claude/rules/task-changelog.md`：

| 索引 | 位置 | 粒度 | 记什么 |
| --- | --- | --- | --- |
| `changelog.md` | workspace 根 | 任务级 | 时间、任务、源文件、产出物、skill、备注 |
| `daily/{日期}.md` | `daily/` | 日 + 文件级 | 当天处理的所有文件 |
| `README.md` | 各目录内 | 目录级 | 该目录下所有条目的摘要 |

### Loop 工作流

| Loop | 间隔 | 定义文件 | 职责 |
| --- | --- | --- | --- |
| inbox-monitor | 每天 | `.claude/loops/inbox-monitor.md` | 扫 `inbox/`，处理带便签的文件 |
| weekly-routine | 每周日 | `.claude/loops/weekly-routine.md` | 汇总本周记录生成周报 + 复盘 |

Loop 只写定义文档，**不自动注册定时任务** —— 由用户手动喂给 `/loop` 触发。

## 开发规范

### Commit Message

格式 `<type>: <description>`，类型用 feat / fix / refactor / docs / test / chore。示例：`docs: 补充周报模板的数据一览`。

- 用 `git add <具体文件>` 明确暂存，不用 `git add .`
- 按逻辑分组提交，不一股脑全提
- 不添加 Co-Authored-By
- commit 前确认，push 前询问用户，不自动 push

### 分支策略

| 分支 | 用途 |
| --- | --- |
| main | 稳定版本 |
| dev | 日常开发 |
| feat/`<name>` | 功能分支，完成后合并回 dev |

主分支 main，远程 origin 已配好（`git remote -v` 可查）。日常提交走 `/git-save`。

### 测试

本目录以文档和流程为主，没有代码测试。新增脚本（PowerShell / Python）时遵循 `/test-driven-development`：先写验证，再写实现。

### 文档风格

- 全中文；中英文之间加半角空格，如 `Claude Code 是`、`第 1 章`
- 中文语境用全角标点，代码和英文语境用半角
- 专有名词保留英文：Claude Code、Git、Markdown、Skills、PowerShell
- 不用「值得注意的是」「需要强调的是」「综上所述」这类空话，少用「的」
- 引用中文用「」，如「失败」「未披露」

## 命名约定

| 对象 | 格式 |
| --- | --- |
| 任务文件夹 | `{YYYY-MM-DD}-{任务名}/`，任务名用中文、简洁 |
| 便签 | `inbox/task-{任务名}.md` |
| 日报 | `reports/{YYYY-MM-DD}-日报.md` |
| 周报 | `reports/{YYYY-MM-DD}-周报.md` |
| 每日流水 | `daily/{YYYY-MM-DD}.md` |
| 归档 | `archive/{YYYY-MM}/` |
| 产出物 | 文件名体现内容，不用 output.xlsx 这类通用名 |
| 时间戳 | `YYYY-MM-DD HH:MM`，精确到分钟 |

## 环境注意

这台 Windows 机器有几个坑，动手前先看：

- **没有可用的 bash**。`where bash` 命中的是 WSL，不可用；git 是便携版，装在 `D:\02-代码项目\Git\`。写脚本默认用 PowerShell（`.ps1`），确实需要 bash 时显式指向 `D:\02-代码项目\Git\bin\bash.exe`。
- **连 github.com 会被沙箱拦截**，`git clone` 要关沙箱才跑得动。
- `.claude/hooks/hooks.json`、`run-hook.cmd`、`session-start` 是上游带来的 bash 版本，本机跑不起来。实际生效的是 `.claude/settings.json` 注册的 PowerShell hook。
- `workspace/.claude/CLAUDE.md` 的「文件路由」表指向 8 个**尚未安装**的技能（minimax-xlsx、minimax-docx、mineru、pdf、minimax-pdf、pptx-generator、work-report、doc-coauthoring）。要用得先补装，否则会路由到不存在的技能。

### Python / 数据分析环境（2026-09-07/08 实测，改动前先复核）

领域技能用到 Python 时，这几条是实测结论，别凭记忆猜：

- **Python 3.14**，`akshare` 1.18.94 已装。命令入口依次试 `python`、`py -3`。
- **东财（EM）部分接口本机常被拒连**（`ConnectionError` / `RemoteDisconnected`）：
  - 常被拒：逐股三大报表 `stock_*_sheet_by_report_em`、`stock_individual_info_em`、行业板块 `stock_board_industry_*_em`
  - 实测可达：EM 业绩报表 `stock_yjbb_em(date=YYYYMMDD)`（全市场单表，含销售毛利率/所处行业）、申万 `sw_index_first_info` / `index_component_sw`、新浪 `stock_financial_analysis_indicator`（逐股）
  - 各技能已内置「重试一次 → 友好降级 / 向用户要文件」路径。**降级不是 bug，绝不要伪造数据**。
  - akshare 函数名用 `hasattr(ak, '...')` 内省现名，别凭记忆写。
- 东财返回的报告日期常带 ` 00:00:00`，需剥掉时间部分（见 `fetch_statements.py`）。
- 本机有 pandas / numpy / matplotlib / openpyxl / sqlite3 / requests；**没有** duckdb、flask。
- 中文字体：matplotlib 用 Microsoft YaHei / SimHei 可正常绘中文。
- CSV 中文读入按 utf-8(-sig) → gbk 回退，**别假定 UTF-8**。
- pandas 的 str 存取器、日期解析跨版本有差异，涉及日期用纯 Python 归一化（仓库脚本已示范）。

## 红线

- **不编数**：每个数字说清来源与口径（累计还是单季、归母还是含少数、单位），说不清就标「未披露」。
- **密钥不入库**：API Key 只从环境变量或仓库根 `memory.md` 取，不写进任何文件，不在汇报里明文出现。
- **不绕过门禁**：不用 `--no-verify` 跳过 hook，不用 `git push --force`。
- **先探索再动手**：动工前先看目标目录和已有材料，别闷头生成。
- 材料不足先列缺口，不硬凑结论。

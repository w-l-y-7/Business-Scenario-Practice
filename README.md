# Business Scenario Practice

金融科技课题的工作仓库。两条线并行：一条管**做事的方法**，一条管**真做出来的东西**。

- **技能线**（`.claude/`）：21 个技能，教 Claude 怎么「想清楚 → 拆计划 → 验算 → 排错 → 存好档」，外加 6 个能直接做金融分析的领域技能。
- **业务线**：`workspace/` 是自动化办公工作区，`investment-research/` 是 CFA 投资研报项目。

---

## 速查：我想…… 该去哪

| 我想…… | 去哪 |
| --- | --- |
| 搞明白 21 个技能分别干什么 | [.claude/skills/README.md](.claude/skills/README.md) |
| 往工作区丢文件让它自动处理 | [workspace/inbox/](workspace/inbox/)，流程见 [workspace/README.md](workspace/README.md) |
| 推进 CFA 研报项目 | [investment-research/README.md](investment-research/README.md) |
| 看还有哪些活没干 | [TODO.md](TODO.md) |
| 抓网页数据 / 批量截图 | [playwright handbook.md](playwright%20handbook.md) |
| 让长任务关掉窗口继续跑 | [psmux handbook.md](psmux%20handbook.md) |
| 改给 Claude 看的仓库规则 | [CLAUDE.md](CLAUDE.md) |

> 上面两个 handbook 文件名里带空格，链接里空格要写成 `%20`。点不开就在文件列表里直接双击。

---

## 根目录文件

| 文件 | 是什么 | 怎么用 |
| --- | --- | --- |
| `CLAUDE.md` | 给 Claude 读的项目规则：目录约定、技能指引、命名规范、环境坑、红线 | 你不用背。改了仓库结构或新增技能后，回来同步更新对应几节 |
| `TODO.md` | 任务清单，状态分 `pending` / `in_progress` / `completed` | 有活要排期，按格式加一个 `task-XXX` 块。配 `/loop` 定时推进，用法写在文件开头 |
| `playwright handbook.md` | 浏览器自动化指南：开网页、点击填表、截图存 PDF、把表格抠成 Excel | 数据只在网页上、没有下载按钮时看。本机实跑验证过，代码可直接复制 |
| `psmux handbook.md` | 命令行会话管理指南：任务关掉窗口也继续跑，一个界面同时盯几摊活 | 要跑长任务、或者想同时开好几个窗口时看。开头是快捷键速查表 |
| `.gitignore` | 哪些文件不提交到 GitHub | 新增「每次跑都重新生成」的产物时，在这里加一条。文件里按区注释了每条为什么被忽略 |
| `.gitattributes` | 换行符归一规则 | 一般不用动。它保证 `.sh` 用 LF、`.ps1` 和 `.cmd` 用 CRLF，免得跨平台报错 |

## 根目录文件夹

| 文件夹 | 是什么 | 详细文档 |
| --- | --- | --- |
| `.claude/` | Claude Code 的配置：21 个技能、会话启动 hook、项目设置 | 技能看 [.claude/skills/README.md](.claude/skills/README.md)，hook 与设置见下 |
| `.vscode/` | VSCode 的构建任务 | 见下 |
| `workspace/` | 自动化办公工作区 | [workspace/README.md](workspace/README.md) |
| `investment-research/` | CFA 投资研报项目 | [investment-research/README.md](investment-research/README.md) |

### `.claude/skills/` —— 21 个技能

分两档：**15 个流程技能**（14 个 Superpowers 中文版 + 本地攒的 `git-save`）管做事方法，**6 个金融领域技能**管具体分析活。哪些真用得上、哪些暂时不用管、两组容易混的边界怎么分，都在 [.claude/skills/README.md](.claude/skills/README.md)。

正常用不着记技能名 —— 把需求说清楚，Claude 自己会挑；想点名就打 `/技能名`。

### `.claude/` 其余文件

| 路径 | 说明 |
| --- | --- |
| `settings.json` | 项目配置，注册会话启动 hook，指向下面的 `session-start.ps1` |
| `hooks/session-start.ps1` | **实际生效的那个** hook，每次会话开始时跑 |
| `hooks/` 下其余文件 | `hooks.json`、`run-hook.cmd`、`session-start` 是上游带来的 bash 版本，本机跑不起来；`hooks-cursor.json` 是 Cursor 的 hook 配置，Claude Code 不读它，它调的也是那个跑不起来的 `run-hook.cmd`。都留着没删，改 hook 时别改错文件 |

### `.vscode/tasks.json` —— 三个构建任务

用法：`Ctrl+Shift+B` 直接跑默认任务，或 `Ctrl+Shift+P` → Run Task 选。

| 任务 | 干什么 |
| --- | --- |
| investment-research：试排 PDF（样张） | 默认任务。出 2–3 页样张验版式 |
| investment-research：导出正式报告 PDF | 把 `output/investment-report.md` 排成正式 PDF |
| investment-research：估值模型自测 | 注意：这条调的 `tools/model/selfcheck.py` 是标记待删的旧脚本，见 [TODO.md](TODO.md) 的 task-004 |

## 两个大目录

### `workspace/` —— 自动化办公工作区

文件从 `inbox/` 投递进来，按便签拆成任务做完，产出日报、周报，并留痕归档。**没有便签的文件一律跳过** —— 便签（`inbox/task-*.md`）是 loop 无人值守处理的唯一入口。

目录分工、便签怎么写、loop 怎么跑、三层索引怎么维护，全在 [workspace/README.md](workspace/README.md)，各子目录另有自己的索引 README。

### `investment-research/` —— CFA 投资研报项目

目标是 2026 年 CFA 投资分析比赛校赛的英文研报。五个阶段流水线与统一估值模型都已搭好，目录和角色齐备，但**一轮完整研报还没跑通**。

目录结构、成品长什么样、怎么跑一轮、三条硬规矩、当前进度与待办，全在 [investment-research/README.md](investment-research/README.md)。它下面还有 10 份 README，各管一个子目录，就近说明用法与坑。

---

## 动手前须知

几条容易踩的，详细版在 [CLAUDE.md](CLAUDE.md) 的「环境注意」与「红线」。

- **这台机器没有可用的 bash**，脚本一律用 PowerShell（`.ps1`）。
- **不编数**：每个数字说清来源与口径，说不清就标「未披露」。
- **密钥不入库**：API Key 只从环境变量或 `memory.md` 取，不写进任何文件。
- **不绕过门禁**：不用 `--no-verify` 跳 hook，不用 `git push --force`。
- 日常提交走 `/git-save`：先扫垃圾文件写 `.gitignore`，再 add + commit + push。提交前确认，push 前问你。

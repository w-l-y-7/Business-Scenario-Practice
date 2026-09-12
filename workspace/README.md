---
title: 自动化办公工作区
description: 收件、任务、日报、归档一体化处理的工作区，配合 Claude Code 自动化跑
date: 2026-09-09
---

自动化办公工作区。文件从 inbox/ 进来 → 拆成任务到 tasks/ 做 → 做完记 changelog.md → 要留痕的写进 daily/ → 成品放 reports/ → 过期归档到 archive/。

## 目录一览

| 目录/文件 | 是什么 | 怎么用 |
| --- | --- | --- |
| inbox/ | 待处理文档投递箱 | 需要处理的文件先丢进来排队 |
| tasks/ | 任务工作区 | 每个任务一个子文件夹，命名 `{YYYY-MM-DD}-{任务名}` |
| reports/ | 报表 | 日报、周报、月报成品放这里 |
| daily/ | 每日处理流水 | 每天一个 `{YYYY-MM-DD}.md`，记录当天处理了什么 |
| archive/ | 长期归档 | 已完成任务按月归档，子目录命名 `{YYYY-MM}/` |
| templates/ | 文档模板 | 做新文档先来这里复制打底 |
| changelog.md | 任务日志 | 每次任务做完，在表里追加一行 |
| .claude/ | 自动化配置 | 规则(rules/)、定时循环(loops/)、子代理(agents/)、项目规则(CLAUDE.md) |
| .gitignore | 排除规则 | 声明哪些文件不提交到版本库 |

## 一份文件走完的流程

1. **收件**：文件放进 `inbox/`。
2. **转任务**：Claude 按 [rules/inbox-interaction.md](.claude/rules/inbox-interaction.md) 先和用户确认要做什么、生成便签 `task-{任务名}.md`，再建 `tasks/{YYYY-MM-DD}-{任务名}/` 子文件夹处理。便签是 loop 的唯一入口，没便签的文件不会被处理。
3. **处理与留痕**：做完按 [rules/task-changelog.md](.claude/rules/task-changelog.md) 在 `changelog.md` 记一行；当天过程写进 `daily/{YYYY-MM-DD}.md`。
4. **出成品与归档**：能形成成品的放 `reports/`；做完不再动的移进 `archive/`（按月建子目录）。

## 自动化怎么跑

| 文件 | 作用 |
| --- | --- |
| [.claude/loops/inbox-monitor.md](.claude/loops/inbox-monitor.md) | 每天扫一次 inbox，处理带便签的文件（配 /loop 用） |
| [.claude/loops/weekly-routine.md](.claude/loops/weekly-routine.md) | 每周日自动汇总本周生成周报（配 /loop 用） |
| [.claude/agents/git-commit.md](.claude/agents/git-commit.md) | 提交子代理：只提交本工作区的改动 |
| [.claude/rules/](.claude/rules/) | Claude 遇到对应场景必须遵守的行为约定 |
| [.claude/CLAUDE.md](.claude/CLAUDE.md) | 以本文件夹作为项目打开时加载的项目规则 |

> 注意：`.claude/CLAUDE.md` 和 rules/ 里的约定，只有在 Claude 以本文件夹作为工作目录/项目时才会自动生效。在别处直接改这里的文件时，按需手动打开对应规则看。

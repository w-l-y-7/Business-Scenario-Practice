# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

自动化办公工作区。通过 inbox 投递待处理文档，定时轮询识别并路由到对应 skill 处理。覆盖 Excel 数据分析、会议纪要整理、日报/周报生成、PPT 制作、PDF 解析等场景。

## 目录结构

| 目录 | 用途 |
|------|------|
| inbox/ | 待处理文档投递箱，用户将文件放入此处 |
| tasks/ | 任务工作区，每个任务一个 {YYYY-MM-DD}-{名称}/ 子文件夹，源文件和产出物放在一起 |
| reports/ | 日报、周报、月报 |
| daily/ | 每日文件处理记录，每天一个 {YYYY-MM-DD}.md |
| archive/{YYYY-MM}/ | 已完成任务的长期归档 |
| templates/ | 常用文档模板 |

## Inbox 处理流程

便签是唯一入口：带便签（task-*.md）的文件才会被处理，没带便签的一律跳过。

1. 扫描 inbox/，挑出便签 task-*.md；一张便签一个任务。没有便签 → 静默结束，不输出任何内容
2. 按便签内容在 tasks/ 下创建任务文件夹 {YYYY-MM-DD}-{任务名}/
3. 将便签和对应源文件从 inbox/ 移入任务文件夹
4. 按便签指定的 skill 处理，产出物保存在同一任务文件夹
5. 更新 changelog.md、daily/{YYYY-MM-DD}.md、tasks/README.md

### 便签系统

用户将文件放入 inbox 后，在对话中说明处理意图。Claude 据此生成便签，记录任务需求和处理方案。便签命名：task-{任务名}.md。多个任务的便签在 inbox 中共存，互不覆盖。任务处理完成后，便签随源文件一起移入任务文件夹，作为任务记录保留。

便签要写到不看对话也能独立执行（涉及文件、需求、选定的 skill、处理步骤、产出要求一次写全），因为 loop 轮询处理时读不到当时的对话。

### 异常处理

单个任务处理失败只影响该任务：把源文件和便签退回 inbox/（已建的任务文件夹一并清掉），在 changelog.md 记一行「失败」+ 原因，然后继续处理其他便签。

### 文件路由

| 文件特征 | Skill |
|---------|-------|
| .xlsx / .csv / .tsv（数据分析、报表） | minimax-xlsx |
| .docx（编辑、排版、套模板） | minimax-docx |
| .pdf → Markdown 转换 | mineru |
| .pdf（合并、拆分、提取、表单填写） | pdf |
| 需要高品质设计的 PDF 输出 | minimax-pdf |
| .pptx 或 PPT 相关需求 | pptx-generator |
| 写日报 / 写周报 | work-report |
| 长文档协作撰写 | doc-coauthoring |

多个 PDF skill 的选择：处理现有 PDF（合并、拆分、提取）→ pdf；将 PDF 转为 Markdown → mineru；生成高品质设计 PDF → minimax-pdf。路由歧义时询问用户，不自行猜测。

## 索引体系

三层索引，各有分工：

| 索引 | 位置 | 粒度 | 内容 |
|------|------|------|------|
| changelog.md | 根目录 | 任务级 | 时间、任务名、源文件、产出物、skill、备注 |
| daily/{date}.md | daily/ | 日+文件级 | 当日处理的所有文件清单 |
| README.md | 各目录内 | 目录级 | 该目录下所有条目的摘要索引 |

## Loop 工作流

| Loop | 间隔 | 提示词 | 职责 |
|------|------|--------|------|
| inbox-monitor | 每天 | .claude/loops/inbox-monitor.md | 每天扫一次 inbox，拾取带便签的文件并处理完 |
| weekly-routine | 每周日 | .claude/loops/weekly-routine.md | 汇总本周记录生成周报（含复盘） |

## 命名约定

- 任务文件夹：{YYYY-MM-DD}-{任务名}/（任务名用中文，简洁描述）
- 报告：{YYYY-MM-DD}-日报.md、{YYYY-MM-DD}-周报.md
- 产出物文件名应体现内容，不用通用名如 output.xlsx

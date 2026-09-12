---
title: 每周例行
description: 每周日自动把本周处理记录汇总成周报，并写本周复盘
date: 2026-09-09
---

# 每周例行（周报 + 复盘）

**干什么**：每周日收尾，把本周（周一 ~ 周日）的处理流水汇总成一份周报放进 `reports/`，并按复盘三问写「本周复盘」。

**怎么触发**：每周日跑一次。把下面「循环指令」喂给 /loop，在周日启动（`/loop 1w <指令>` 近似每周一次，或每周日手动跑一遍）。

## 循环指令（可直接喂给 /loop）

> 打开 `workspace/.claude/loops/weekly-routine.md`，照里面的步骤跑一遍：
> 汇总本周 `changelog.md` 和 `daily/` 里的记录，用 `templates/周报-模板.md` 在 `reports/` 生成 `{今天日期}-周报.md`，写本周复盘，完成后在 `changelog.md` 记一行。

## 步骤

1. 定范围：本周 = 上一个周一到今天（周日）。
2. 读 `changelog.md` 里本周的行、`daily/{本周各天}.md`，确认本周处理了哪些任务、产出哪些文件。
3. 用 [templates/周报-模板.md](../../templates/周报-模板.md) 生成周报，存 `reports/{YYYY-MM-DD}-周报.md`（日期取生成当天）。
4. 复盘三问（效率回顾 / 经验沉淀 / 改进建议）写「本周复盘」，参照 [rules/daily-review.md](../rules/daily-review.md) 的复盘要求。
5. 在 `changelog.md` 追加一行「生成本周周报」。
6. 汇报：周报生成在哪、本周整体怎么样。

## 说明

- 本周没有任何处理记录 → 如实写「本周无任务处理」，复盘别硬编。
- 只做汇总收尾，**不要**顺手处理 inbox/ 的新文件——那是 inbox-monitor 的活儿。

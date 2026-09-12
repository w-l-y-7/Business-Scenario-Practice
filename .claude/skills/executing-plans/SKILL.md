---
name: executing-plans
description: 手头有一份写好的实现计划，要在单独的会话里、带审查检查点地执行时使用
---

# 执行计划（Executing Plans）

## 概述

加载计划，批判性地审阅，执行所有任务，完成后汇报。

**开始时要声明：** “我正在使用 executing-plans 技能来实现这份计划。”

**注意：** 告诉你的搭档，Superpowers 在有 subagent 可用时表现好得多（Claude Code、Codex CLI、Codex App、Copilot CLI 和 Gemini CLI 都算；各平台的工具说明见 `../using-superpowers/references/`）。如果有 subagent 可用，用 superpowers:subagent-driven-development 而不是这个技能。

## 流程

### Step 1: 加载并审阅计划
1. 确保有隔离工作区：用 superpowers:using-git-worktrees 创建一个，或者核实已有的那个
2. 读计划文件
3. 批判性审阅 —— 找出对计划的疑问或顾虑
4. 有顾虑：开始之前先跟搭档提出来
5. 没有顾虑：为计划里的各项建 todo，然后往下做

### Step 2: 执行任务

对每个任务：
1. 标记为 in_progress
2. 严格按每一步来（计划里都是小步的）
3. 按指定跑验证
4. 标记为 completed

### Step 3: 完成开发

所有任务完成并验证之后：
- 声明：“我正在使用 finishing-a-development-branch 技能来完成这项工作。”
- **必需的子技能：** 用 superpowers:finishing-a-development-branch
- 按那个技能验证测试、给出选项、执行选择

## 什么时候停下求助

**碰到下面这些立刻停止执行：**
- 撞上阻塞（缺依赖、测试失败、指令不清）
- 计划有严重缺口，根本没法开始
- 你看不懂某条指令
- 验证反复失败

**要问清楚，不要猜。**

## 什么时候回到前面的步骤

**回到审阅（Step 1）当：**
- 搭档根据你的反馈更新了计划
- 根本方法需要重新考虑

**不要硬闯阻塞** —— 停下，问。

## 记住
- 先批判性地审阅计划
- 严格执行计划的步骤
- 不要跳过验证
- 计划说要用哪些技能就用
- 卡住就停，不要猜
- 没有用户明确同意，绝不在 main/master branch 上开始实现

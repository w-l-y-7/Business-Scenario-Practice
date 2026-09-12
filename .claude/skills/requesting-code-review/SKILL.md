---
name: requesting-code-review
description: 完成任务、实现重大功能或准备合并之前使用，用来验证工作是否满足需求
---

# 请求代码审查（Requesting Code Review）

派出一个 code reviewer（代码审查员）subagent（子代理）去发现问题，趁问题还没层层扩散就把它揪出来。审查员拿到的是专门为评估准备好的上下文，绝不会是你这次会话的完整历史。

**核心原则：** 早审查，勤审查。

## 什么时候请求审查

**必须做：**
- subagent-driven development（由子代理驱动开发）中，每完成一个任务之后
- 完成重大功能之后
- 合并到 main 之前

**可选，但很有价值：**
- 卡住时（换一个视角）
- 重构之前（做基线检查）
- 修完复杂 bug 之后

## 怎么请求

**1. 取 git SHA：**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. 派出 code reviewer subagent：**

派一个 `general-purpose` subagent，填入 [code-reviewer.md](code-reviewer.md) 里的模板

**占位符：**
- `{DESCRIPTION}` - 你构建内容的简要说明
- `{PLAN_OR_REQUIREMENTS}` - 它应该做什么
- `{BASE_SHA}` - 起始 commit
- `{HEAD_SHA}` - 结束 commit

**3. 根据反馈行动：**
- Critical（严重）问题立刻修
- Important（重要）问题在继续之前修
- Minor（次要）问题记下来，往后放
- 如果审查员判错了，就用理由反驳

## 示例

```
[刚完成 Task 2：添加验证函数]

You: 继续之前，我先请求一次代码审查。

BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

[派出 code reviewer subagent]
  DESCRIPTION: 新增 verifyIndex() 和 repairIndex()，覆盖 4 种问题类型
  PLAN_OR_REQUIREMENTS: 来自 docs/superpowers/plans/deployment-plan.md 的 Task 2
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661

[Subagent 返回]：
  Strengths: 架构干净，有真实测试
  Issues:
    Important: 缺少进度提示
    Minor: 上报间隔用了魔法数字 (100)
  Assessment: 可以继续

You: [修好进度提示]
[继续 Task 3]
```

## 常见的自我开脱

| 借口 | 事实 |
|--------|---------|
| “我自己看一下 diff 就行，不用派审查员” | 你是协调者 —— 自己内联审查 diff 会烧掉你需要用来继续推进工作的上下文窗口。派一个审查员 subagent：diff 和评估都待在它的上下文里，只有发现的问题回到你这里。 |
| “审查员需要我整段会话历史才能看懂这次改动” | 交给它专门准备好的上下文，绝不要给会话历史。这样审查员盯的是工作产物，而不是你的思考过程。 |

## 危险信号

**绝不要：**
- 因为“很简单”就跳过审查
- 忽略 Critical 问题
- 带着没修的 Important 问题继续往前
- 跟合理的技术反馈抬杠

**如果审查员判错了：**
- 用技术理由反驳
- 拿出能证明它有效的代码/测试
- 请求澄清

模板见：[code-reviewer.md](code-reviewer.md)

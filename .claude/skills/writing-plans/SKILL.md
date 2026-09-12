---
name: writing-plans
description: 手里有多步骤任务的规格或需求时、动手写代码之前使用
---

# 编写计划

## 概述

写一份详尽的实施计划，假设执行这个计划的工程师对我们的代码库一无所知、品味也靠不住。把他们需要知道的一切都写下来：每个任务要改哪些文件、代码、测试、可能要查的文档、怎么测。把整份计划拆成一口大小的任务交出去。DRY。YAGNI。TDD。频繁 commit。

假设他们是一位熟练的开发者，但对我们的工具链和问题领域几乎一无所知。假设他们不太懂好的测试设计。

**开头先宣告：** 「I'm using the writing-plans skill to create the implementation plan.」

**上下文：** 如果在独立 worktree（独立工作副本）里干活，它应当在执行时已经由 `superpowers:using-git-worktrees` 技能创建好。

**计划的保存位置：** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- （用户对计划位置有偏好时，以用户偏好为准，覆盖这个默认值）

## 范围检查

如果规格覆盖了多个互相独立的子系统，那它在头脑风暴阶段就应该被拆成按子项目分的规格。如果没拆，就建议把它拆成几份独立的计划——每个子系统一份。每份计划本身都应当产出可以运行、可以测试的软件。

## 文件结构

定义任务之前，先画出哪些文件会被创建或修改、每个文件负责什么。分解的决策就在这一步锁定。

- 设计单元要有清晰的边界和定义良好的接口。每个文件只应有一个明确的职责。
- 你能一次揣在上下文里的代码，你才推理得最好；文件聚焦时，你的改动也更可靠。宁可要小而聚焦的文件，也不要大而无当、什么都干的文件。
- 一起改的文件应当放在一起。按职责拆分，别按技术分层拆。
- 在已有代码库里，跟随既有模式。如果代码库用的是大文件，不要单方面重构——但如果你要改的文件已经膨胀得难以驾驭，把拆分写进计划是合理的。

这个结构决定了任务怎么分解。每个任务都应当产出独立成立、自成一体、讲得通的改动。

## 任务大小是否合适

任务是自带测试循环、值得让一个新审查者把一次关的最小单元。划任务边界时：把环境搭建、配置、脚手架和文档这类步骤，折进需要这些交付物的那个任务里；只在「审查者能合理地否掉一个任务却认可它旁边那个」的地方才拆开。每个任务都以一个可以独立测试的交付物收尾。

## 一口大小的任务粒度

**每一步就是一个动作（2-5 分钟）：**
- 「写失败的测试」—— 一步
- 「运行它，确认它失败」—— 一步
- 「写最小实现，让测试通过」—— 一步
- 「运行测试，确认它们通过」—— 一步
- 「Commit」—— 一步

## 计划文档的头部

**每份计划都必须以这个头部开头：**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

**Spec:** [path to the spec/design doc this plan implements — the plan
argues from the spec, so the spec travels with it; executors read both]

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits,
naming and copy rules, platform requirements — one line each, with exact
values copied verbatim from the spec. Every task's requirements implicitly
include this section.]

---
```

## 任务结构

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks — exact signatures]
- Produces: [what later tasks rely on — exact function names, parameter
  and return types. A task's implementer sees only their own task; this
  block is how they learn the names and types neighboring tasks use.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## 不许留占位符

每一步都必须包含工程师真正需要的内容。下面这些是**计划失败**——绝不要写：
- 「TBD」「TODO」「稍后实现」「细节待补」
- 「加上适当的错误处理」／「加上校验」／「处理边界情况」
- 「为上述内容写测试」（不带真实的测试代码）
- 「和任务 N 类似」（把代码重复一遍——工程师可能是乱序读任务的）
- 只说要做什么、不展示怎么做的步骤（代码步骤必须有代码块）
- 引用任何任务里都没定义过的类型、函数或方法

## 自查

写完完整的计划后，用全新的眼光看规格，拿计划对照它检查。这是你自己跑的清单——不是派个 subagent 去查。

**1. 规格覆盖：** 把规格里的每一节/每项要求过一遍。你能指出哪个任务实现了它吗？把缺口都列出来。

**2. 占位符扫描：** 在计划里搜红旗——上面「不许留占位符」一节里的任何模式。改掉它们。

**3. 类型一致性：** 你在后面任务里用的类型、方法签名和属性名，和你在前面任务里定义的一致吗？一个函数在任务 3 里叫 `clearLayers()`，到任务 7 里叫 `clearFullLayers()`，这就是 bug。

发现问题就地改掉。不用重新审一遍——改完继续往下走就好。如果你发现规格里有某项要求没有任何任务对应，把任务补上。

## 交棒执行

保存计划之后，给出执行方式的选择：

**「计划已完成，保存到了 `docs/superpowers/plans/<filename>.md`。两种执行方式：**

**1. Subagent 驱动（推荐）** —— 我为每个任务派一个全新的 subagent，任务之间做审查，迭代快

**2. 就地执行（Inline Execution）** —— 在当前会话里用 executing-plans 执行任务，批量执行、设检查点

**选哪种？」**

**如果选了 Subagent 驱动：**
- **REQUIRED SUB-SKILL：** 使用 superpowers:subagent-driven-development
- 每个任务派一个新 subagent + 两阶段审查

**如果选了就地执行：**
- **REQUIRED SUB-SKILL：** 使用 superpowers:executing-plans
- 批量执行，设检查点供审查

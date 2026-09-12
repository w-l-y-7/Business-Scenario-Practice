---
name: verification-before-completion
description: 即将声称工作已完成、已修复或已通过时，在 commit 或创建 PR 之前使用 —— 要求先跑验证命令、确认输出，再做出任何成功的声称；永远证据先于断言
---

# 完成前的验证

## 概述

**核心原则：** 永远证据先于断言。

**违反这条规则的字面要求，就是违反这条规则的精神。**

## 铁律

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

如果你没在这条消息里跑过验证命令，就不能声称它通过。

## 闸门函数

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## 常见的失败

| 断言 | 需要 | 不够 |
|-------|----------|----------------|
| test 通过 | test 命令输出：0 个失败 | 上一次的运行结果、「应该能通过」 |
| linter 干净 | linter 输出：0 个错误 | 部分检查、外推 |
| 构建成功 | 构建命令：退出码 0 | linter 通过、日志看着不错 |
| bug 已修 | 测原始症状：通过 | 代码改了、假定修好了 |
| 回归 test 有效 | 验证过红-绿循环 | test 通过了一次 |
| agent 完成了 | 版本控制的 diff 显示了改动 | agent 报告「成功」 |
| 需求满足 | 逐行清单 | test 通过 |

## 危险信号 —— 停

- 用「应该」「大概」「好像」
- 在验证之前就表示满意（「太棒了！」「完美！」「搞定了！」等等）
- 准备不验证就 commit/push/开 PR
- 相信 agent 的成功报告
- 依赖部分验证
- 想着「就这一次」
- 累了，想赶紧把活干完
- **任何在没跑过验证的情况下暗示成功的措辞**

## 防止自我合理化

| 借口 | 真相 |
|--------|---------|
| 「现在应该能用了」 | 去跑验证 |
| 「我有信心」 | 信心不等于证据 |
| 「就这一次」 | 没有例外 |
| 「linter 通过了」 | linter 不等于编译器 |
| 「agent 说成功了」 | 独立验证 |
| 「我累了」 | 疲惫不是借口 |
| 「部分检查就够了」 | 部分什么都证明不了 |
| 「换了个说法，所以规则不适用」 | 精神高于字面 |

## 关键模式

**test：**
```
✅ [Run test command] [See: 34/34 pass] "All tests pass"
❌ "Should pass now" / "Looks correct"
```

**回归 test（TDD 红-绿）：**
```
✅ Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
❌ "I've written a regression test" (without red-green verification)
```

**构建：**
```
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check compilation)
```

**需求：**
```
✅ Re-read plan → Create checklist → Verify each → Report gaps or completion
❌ "Tests pass, phase complete"
```

**agent 委派：**
```
✅ Agent reports success → Check VCS diff → Verify changes → Report actual state
❌ Trust agent report
```

## 什么时候适用

**总是，在以下之前：**
- 任何形式的成功/完成声称
- 任何表示满意的话
- 任何关于工作状态的正面陈述
- commit、创建 PR、宣告任务完成
- 进入下一个任务
- 把活委派给 agent

**规则适用于：**
- 原样的措辞
- 改述和同义词
- 暗示成功
- 任何暗示完成/正确的沟通

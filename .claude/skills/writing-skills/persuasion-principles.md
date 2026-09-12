# 技能设计中的说服原理

## 概述

LLM 和人类一样，会对同一套说服原理起反应。理解这套心理学，能帮你设计出更有效的技能——不是要去操纵人，而是确保关键做法即使在压力之下也能被遵守。

**研究基础：** Meincke 等人（2025）用 N=28,000 段 AI 对话测试了 7 条说服原理。说服技巧让遵守率翻了一倍以上（33% → 72%，p < .001）。

## 七条原理

### 1. 权威（Authority）
**是什么：** 对专业、资历或官方来源的服从。

**在技能里怎么起作用：**
- 命令式语言：「YOU MUST」「Never」「Always」
- 不容商量的框架：「No exceptions」
- 消除决策疲劳和合理化

**什么时候用：**
- 约束纪律的技能（TDD、验证要求）
- 安全攸关的做法
- 已被确立的最佳实践

**例子：**
```markdown
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.
```

### 2. 承诺（Commitment）
**是什么：** 与先前的行为、声明或公开表态保持一致。

**在技能里怎么起作用：**
- 要求宣告：「Announce skill usage」
- 逼出明确的选择：「Choose A, B, or C」
- 用跟踪机制：给清单建 todo

**什么时候用：**
- 确保技能真的被遵守
- 多步骤流程
- 问责机制

**例子：**
```markdown
✅ When you find a skill, you MUST announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.
```

### 3. 稀缺（Scarcity）
**是什么：** 由时间限制或有限的可获得性带来的紧迫感。

**在技能里怎么起作用：**
- 限时要求：「Before proceeding」
- 顺序依赖：「Immediately after X」
- 防止拖延

**什么时候用：**
- 即时的验证要求
- 时效敏感的流程
- 防止「我待会儿再做」

**例子：**
```markdown
✅ After completing a task, IMMEDIATELY request code review before proceeding.
❌ You can review code when convenient.
```

### 4. 社会认同（Social Proof）
**是什么：** 从众，跟随别人怎么做、或跟随被视作常态的做法。

**在技能里怎么起作用：**
- 普遍化的模式：「Every time」「Always」
- 失败模式：「X without Y = failure」
- 确立规范

**什么时候用：**
- 记录普遍通用的做法
- 就常见失败发出警告
- 强化标准

**例子：**
```markdown
✅ Checklists without todo tracking = steps get skipped. Every time.
❌ Some people find a todo list helpful for checklists.
```

### 5. 统一（Unity）
**是什么：** 共享身份，「我们感」，同一个群体的归属。

**在技能里怎么起作用：**
- 协作式语言：「our codebase」「we're colleagues」
- 共享目标：「we both want quality」

**什么时候用：**
- 协作型流程
- 建立团队文化
- 非等级制的做法

**例子：**
```markdown
✅ We're colleagues working together. I need your honest technical judgment.
❌ You should probably tell me if I'm wrong.
```

### 6. 互惠（Reciprocity）
**是什么：** 受了好处就该回报的义务。

**在技能里怎么起作用：**
- 少用——会让人觉得在操纵人
- 技能里很少需要

**什么时候避免：**
- 几乎总是（其他原理更有效）

### 7. 好感（Liking）
**是什么：** 更愿意和自己喜欢的人合作。

**在技能里怎么起作用：**
- **不要用它来换取遵守**
- 与诚实反馈的文化相冲突
- 会催生谄媚

**什么时候避免：**
- 在约束纪律的场合，永远避免

## 按技能类型组合原理

| 技能类型 | 用 | 避免 |
|------------|-----|-------|
| 约束纪律型 | 权威 + 承诺 + 社会认同 | 好感、互惠 |
| 指导/技术型 | 适度权威 + 统一 | 重压式权威 |
| 协作型 | 统一 + 承诺 | 权威、好感 |
| 参考型 | 只求清晰 | 一切说服手法 |

## 为什么管用：背后的心理学

**明确的界线规则减少合理化：**
- 「YOU MUST」消除决策疲劳
- 绝对化的措辞消灭「这算例外吗？」这类问题
- 明确的反合理化驳斥堵住具体的漏洞

**执行意图把行为变成自动的：**
- 清晰的触发条件 + 要求的动作 = 自动执行
- 「当 X 时，做 Y」比「一般要去做 Y」更有效
- 降低遵守时的认知负担

**LLM 是类人的（parahuman）：**
- 在包含这些模式的人类文本上训练
- 训练数据里，权威式语言往往紧跟着顺服
- 承诺序列（表态 → 行动）被大量建模
- 社会认同模式（大家都做 X）建立起规范

## 合乎伦理的用法

**正当的：**
- 确保关键做法被遵守
- 写出有效的文档
- 防止可预见的失败

**不正当的：**
- 为个人利益操纵他人
- 制造虚假的紧迫感
- 靠内疚来换取遵守

**检验标准：** 如果对方完全看懂了这套技巧，它是否仍服务于对方真实的利益？

## 研究文献

**Cialdini, R. B. (2021).** *Influence: The Psychology of Persuasion (New and Expanded).* Harper Business.
- 七条说服原理
- 影响力研究的实证基础

**Meincke, L., Shapiro, D., Duckworth, A. L., Mollick, E., Mollick, L., & Cialdini, R. (2025).** Call Me A Jerk: Persuading AI to Comply with Objectionable Requests. University of Pennsylvania.
- 用 N=28,000 段 LLM 对话测试了 7 条原理
- 用了说服技巧后遵守率从 33% 升到 72%
- 权威、承诺、稀缺最有效
- 验证了 LLM 行为的类人模型

## 速查

设计技能时，问自己：

1. **这是什么类型？**（约束纪律 vs. 指导 vs. 参考）
2. **我想改变的是什么行为？**
3. **哪条/哪些原理适用？**（约束纪律通常用权威 + 承诺）
4. **我是不是叠得太多了？**（别把七条全用上）
5. **这合乎伦理吗？**（是否服务于对方真实的利益？）

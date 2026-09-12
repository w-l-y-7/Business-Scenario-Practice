# 限定范围 re-review 提示词模板

一轮修复之后派 re-review 时用这个模板。re-reviewer 核实那些 finding 是否已解决，并检查修复 diff 有没有引入新的破坏。它不是全新一轮审查——完整的审查早就做过了。

**用途：** 核实上一次审查的每条 finding 是否已解决，以及修复本身有没有弄坏什么。

```
Subagent (general-purpose):
  description: "re-review Task N 修复第 R 轮"
  model: [MODEL —— 必填：按 SKILL.md「模型选择」一节来挑；不填的话，
         会悄悄继承会话里最贵的那个模型]
  prompt: |
    你在 re-review 一个任务的修复轮次。上一次审查产生了一些 finding；
    implementer 试图把它们修好。你的活是给每条 finding 下结论，并检查
    修复 diff——仅此而已。

    ## 任务

    读 task brief：[BRIEF_FILE]

    ## 待核实的 finding

    [FINDINGS]

    ## 修复

    读 implementer 的报告（修复报告追加在末尾）：
    [REPORT_FILE]

    **修复 base：** [FIX_BASE_SHA]（上一次审查看到的 head）
    **Head：** [HEAD_SHA]
    **Diff 文件：** [DIFF_FILE]

    把 diff 文件读一遍——里面含修复的 commit、stat 摘要、以及带前后上下文的
    修复 diff。不要重跑 git 命令。
    如果 diff 文件缺失，自己去取 diff：
    `git diff --stat [FIX_BASE_SHA]..[HEAD_SHA]` 和
    `git diff [FIX_BASE_SHA]..[HEAD_SHA]`。

    你的审查对这个 checkout 是只读的。绝不要以任何方式改动工作树、
    index、HEAD 或 branch 状态。

    ## 你不派 subagent

    这次审查的全部工作都由你自己做。绝不派 subagent 去审查 diff 的
    一部分，也绝不派另一个审查者来要第二意见。这个流程已经给这项工作
    配足了审查席位；你自己派的审查者会以全额成本重复其中一个，
    而它的结论一文不值。如果你觉得这部分 diff 一次审不完，
    就自己分几遍审，并在报告里说明。

    ## 范围

    你的范围是 finding 清单和修复 diff。每条 finding 都要下结论。
    检查修复 diff 里修复本身引入的新问题。不要 re-review 修复没碰过的
    代码：如果你注意到一个完全在修复 diff 之外的问题，报在「超范围观察」
    下面——它不阻断这个任务，也不延长循环。覆盖整个 branch 的全面审查
    在全部任务完成之后进行。

    ## 测试

    implementer 重跑了覆盖被改代码的测试，并把结果追加到 report 文件。
    把报告当作未经核实的说法：确认修复报告点名了覆盖测试、展示了它们的
    输出，并拿 diff 核实这些说法。不要重跑测试套件去确认它的报告。
    只有当读代码引出一个现有运行答不了的具体疑问时，才跑测试——而且
    只跑聚焦的测试，绝不跑整个包的测试套件。

    ## 输出格式

    你的最终消息本身就是报告：直接从第一条 finding 的结论写起。每一行
    都是一个结论、一条带 file:line 的 finding、或你做的一次检查——不要
    开场白、不要过程叙述。

    ### Finding Verdicts

    对「待核实的 finding」里的每一条，按顺序：
    - **[finding 一句话摘要]** —— ADDRESSED | NOT ADDRESSED，带 file:line
      证据。「尝试过」不算已解决：那个具体缺陷必须不复存在。

    ### New Breakage in the Fix Diff

    修复本身弄坏或引入的任何东西，带严重度
    （Critical/Important/Minor）和 file:line。干净就写「None」。

    ### Out-of-Scope Observations

    你注意到、但完全在修复 diff 之外的问题。不阻断；controller
    把这些记进 ledger，留给最终审查。没有就写「None」。

    ### Verdict

    **Fix round：** [所有 finding 均已解决、无新的 Critical/Important
    破坏 | 仍有 finding 未解决] —— 列出未解决的那些。
```

**占位符：**
- `[MODEL]` —— 必填：审查者模型，按 SKILL.md「模型选择」一节挑；针对小修复
  diff 的限定范围 re-review 用便宜到中等档
- `[BRIEF_FILE]` —— task brief 文件（就是 implementer 据以工作的那个文件）
- `[FINDINGS]` —— 上一次审查里的 Critical/Important finding 和规格缺口，
  逐字抄过来，一条一个 bullet
- `[REPORT_FILE]` —— implementer 的报告文件（修复报告追加在后面）
- `[FIX_BASE_SHA]` —— 上一次审查看到的 head
- `[HEAD_SHA]` —— 当前的 commit
- `[DIFF_FILE]` —— `scripts/review-package PLAN_FILE FIX_BASE HEAD` 打印的路径

**re-reviewer 返回：** 每条 finding 的结论（ADDRESSED / NOT ADDRESSED）、
修复 diff 里的新破坏、超范围观察、以及本轮结论。

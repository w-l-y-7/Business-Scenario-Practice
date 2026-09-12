# 任务清单

## 这个文件怎么用 + 怎么配合 /loop

**TODO.md 是什么**

一张任务清单纸。干正事之前，先把要做的事按下面的格式记进来，标好状态，就不用靠脑子记了。

**/loop 是什么**

一个「定时重复器」。它让 Claude 每隔一段时间，把你交代的那句话重新执行一遍，一直循环，直到你喊停。适合反复盯进度、批量推进任务这类事。

**怎么配合用（三步）**

1. 先把任务写进下面的 task 块，状态填 `pending`。
2. 用 /loop 让 Claude 去干活。注意：/loop 只是「反复执行你交代的话」，Claude 不会自动知道你有个 TODO.md，所以交代的话里一定要写清楚「先读 TODO.md」。
   - 想定时推进，比如每 10 分钟干一件：
     `/loop 10m 打开 workspace/TODO.md，找第一个 pending 任务，动手做完，把状态改成 completed，再继续下一个`
   - 想一口气把清单清完、节奏让 Claude 自己把控（不带时间间隔）：
     `/loop 打开 workspace/TODO.md，把里面所有 pending 任务按顺序做完，做完一项就更新一次状态，全做完向我汇报`
3. 中途想停：直接发消息说「停掉 /loop」就行。

**几个提醒**

- /loop 每次重新执行，等于把你那句话从头再做一遍，不记得上一轮干了啥，所以那句话要写全（写清看 TODO.md、按什么顺序、做完怎么更新状态）。
- 只对「需要重复 / 需要盯进度」的事有意义。一次性任务直接交代即可，别用 /loop。

状态只有三种：`pending`（没开始）、`in_progress`（在做）、`completed`（做完了）。

## task-001

- 状态：pending
- 描述：决定 Business Scenario Practice 要不要装 `.githooks/pre-commit`。参考 `investment project` 那份：它读 `save-gate/` 下的 test.passed 和 quality.passed 标记，而标记是 quality-engineer 和 tester 两个 subagent 生成的 —— 这两个 agent 在 BSP 已经删掉，直接搬过来会永久拦下所有带 `.py` 的提交。两个选项：一是不装钩子（BSP 以文档和流程为主，本来也不适合代码门禁），二是写个轻量版（提交前自动拦密钥和大文件）

## task-002

- 状态：<填：pending / in_progress / completed>
- 描述：<一句话说明这个任务要做什么>

# 写好 test

**什么时候加载这份参考：** 写或改 test 时，加 mock 时，或者给 test 加清理/辅助方法时。

## 概述

一个 test 存在的意义，是抓到某一个具体的破坏。下面两条原则管着这里的一切：

```
1. Every test names the break it catches
2. Every test exercises the real thing
```

严格的 TDD 会自然产生这两点：一个先写、并且对着真实代码看着它失败过的 test，已经证明了自己能失败；只有当真实依赖确实慢或者是外部的，才配用 mock。

## 原则 1：说清楚它抓的是哪个破坏

写 test 主体之前，先回答：**哪个生产代码的改动应该让这个 test 失败 —— 而且那个改动是 bug 还是一个有意决定？** 一个 test 靠抓到错误分支、漏掉的副作用、错的参数、边界情况或坏掉的契约，来赢得自己的位置。

**独立地推出期望值。** 用字面量和手工核对过的固定数据；带字面量 `want` 值的表驱动 test 是首选写法。由被测代码（或它的辅助函数）算出来的期望值，不管那段代码干了什么都会通过：

```typescript
// ❌ Mirror assertion: the same builder computes both sides — always true
const expected = buildSearchQuery({ tag: 'urgent' });
expect(buildSearchQuery({ tag: 'urgent' })).toBe(expected);

// ✅ Hand-derived literal
expect(buildSearchQuery({ tag: 'urgent' })).toBe('tag:"urgent"');
```

**不要「变化探测器」。** 如果只有有意的决定才能让一个 test 失败 —— 比如某个常量的值、消息的具体措辞、私有结构 —— 那它在重设计时会报警，却在真出 bug 时睡大觉。要测依赖那个决定的行为：不是 `expect(MAX_RETRIES).toBe(5)`，而是「一次失败的调用会被重试 5 次，第 6 次绝不会发生」。

**测行为，不测文本。** 断言一个脚本、skill 或配置里有某一行原样文本，只证明了源码就是源码。要让脚本跑在受控输入上，断言输出、副作用或退出码。给 agent 下指令的文档，要通过消费它的那个 agent 的行为来测（superpowers:writing-skills）；给人读的散文根本不配拥有 test。

**测你的代码，不测框架。** 测你的代码在边界上做出的契约 —— 你注册的路由、你发出的查询、你产出的 payload。上游的机制是它们维护者该写的 test（经典例子：断言你的 router 调用了一个注册过的 handler —— 那是框架的 test，不是你的）。当上游行为真的让你意外时，写一个窄窄的特征描述 test，把那个假设写出来。同一条边界也适用于你的代码内部：构造函数、getter、常量、简单的转发，只有在校验、规范化、设默认值、派生、强制约束或产生副作用时，才值得有 test —— 否则就去断言第一个依赖它们的、消费者可见的结果。

### 闸门函数

```
BEFORE writing the test body:
  Name the production change that would make this test fail.

  Cannot name one            → redesign around an observable behavior
  "The source text changed"  → run the artifact and assert its effects
  Only intentional decisions → change detector; test the behavior
                               that depends on the decision

  Confirm the expected value is derived without the code under test.
  IF it reuses the code's logic or helpers:
    Replace it with a literal or hand-checked fixture
```

## 原则 2：操练真东西

**mock 不配拥有断言。** 一个 mock 断言，在 mock 存在时通过、在 mock 不存在时失败 —— 它对组件本身什么都没说。要断言真实组件的行为；如果你检查的是 mock，那就把 mock 去掉，或者把断言删掉。

```typescript
// ✅ Real behavior
expect(screen.getByRole('navigation')).toBeInTheDocument();

// ❌ Mock existence
expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
```

**你的搭档的纠正：**「我们是在测一个 mock 的行为吗？」

**在正确的层级打 mock。** 替换真实方法之前，先把它的每个副作用搞清楚；只对慢的或外部的操作打 mock，让 test 依赖的东西保持真实。拿不准时，先让 test 跑在真实实现上，看看实际上需要发生什么。

```typescript
// ❌ The mock swallows the config write that duplicate detection reads
vi.mock('ToolCatalog', () => ({
  discoverAndCacheTools: vi.fn().mockResolvedValue(undefined)
}));

// ✅ Mock only the slow server startup; the config write stays real
vi.mock('MCPServerManager');
```

**让替身具体。** 当参数、调用次数、调用顺序是契约的一部分时，要把它们断言出来 —— 一个什么都接受的假货，什么都验证不了。给每个分支（成功、出错、格式错误）各自的固定数据或 spy，这样错误的分支就满足不了期望。

**完整地镜像真实数据。** 按它现实中的样子，把完整的结构 mock 出来 —— 所有有文档的字段 —— 而不只是你的 test 读的那几个。下游代码读到被省略的字段时，残缺的 mock 会悄悄失效：test 通过，集成却坏了。

**生产类只放生产方法。** 只有 test 才需要的清理，放在 test 工具里，绝不作为 `destroy()` 挂到生产类上。问自己：这个方法是不是只从 test 里被调用？这个类是不是拥有这个资源的生命周期？答案是否定的 → 放进 test 工具。

**优先用真实组件，而不是复杂的 mock。** 当 mock 的准备代码比 test 逻辑还大、当 mock 少了真实组件有的方法、当 mock 一变 test 就坏时，换成用真实组件的集成 test。**你的搭档的问题：**「这里我们真的需要用 mock 吗？」

### 闸门函数

```
BEFORE adding a mock or test helper:
  List the real method's side effects; keep the ones the test
  depends on real — mock the slow/external level below them.

  Mock responses mirror the complete real structure.

  A method only tests call lives in test utilities, not production.

  About to assert on the mock itself?
    Unmock it or delete the assertion.
```

## test 跟实现一起交付

TDD 循环 —— 失败的 test、最少的实现、重构 —— 就是「完成」的含义。交付这个行为需要的 test，且只要这些：琐碎的代码和给人读的散文一个都不配，为了应付流程而写的 test，会永远背着维护成本。

## 变异检查

收尾之前，在心里给生产代码做变异；每个贴近现实的变异，都应该至少让一个 test 失败：

- 错的常量或参数
- 错的分支处理
- 缺失的状态变化或副作用
- 空的或默认的返回值
- 对零、空、nil、未授权或格式错误的输入缺少校验

一个没被任何东西抓到的变异，要么说明这个行为没有保护 —— 要么说明那个 test 是套套逻辑。

## 速查表

| 当你…… | 就做 |
|-------------|-----|
| 写任何 test | 说清楚它抓的破坏 —— 是 bug，不是决定 |
| 构造期望值 | 手工推出来；绝不用被测代码推 |
| 测脚本或文档 | 跑它 / 给它的消费者加压；绝不 grep 它的文本 |
| 想给依赖写 test | 测你的边界契约，不测它们有文档的机制 |
| 想对 mock 出来的元素断言 | 测真实组件，或者把它 unmock 掉 |
| 准备 mock 一个方法 | 先搞懂它的副作用；只 mock 慢的/外部的层级 |
| 构造 mock 响应 | 完整镜像真实结构 |
| 需要只有 test 用的清理 | 放进 test 工具 |
| 看着 mock 的准备代码越滚越大 | 换成用真实组件的集成 test |
| 写完一个 test 文件 | 跑一遍变异检查 |

## 警告信号

- 准备代码和断言共用同一个对象，等于保证了相等
- test 只能通过 panic、崩溃或找不到选择器来失败
- test 在每次有意改动时都失败，却从不因意外破坏而失败
- 期望值藏在循环、builder 或辅助函数后面
- test grep 源码文本，或者断言一个被删掉的符号依然被删掉
- 就算只剩框架，这个 test 也还是「有意义」
- test 只是为了覆盖率而存在，不检查任何副作用或结果
- 某个断言检查的是 `*-mock` 的 test ID，或者你一去掉 mock 它就失败
- 某个方法只从 test 文件里被调用
- mock 的准备代码超过 test 的一半，或者你说不清为什么需要这个 mock
- 「为了保险起见」打 mock

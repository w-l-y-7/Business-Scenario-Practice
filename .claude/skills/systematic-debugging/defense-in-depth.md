# Defense-in-Depth 多层校验

## 概览

你修好一个由非法数据引发的 bug，在某一处加上校验，感觉就够了。但这一道检查，可能被别的代码路径、重构或 mock 绕过去。

**核心原则：** 数据流经的每一层都要校验。让这个 bug 从结构上就不可能出现。

## 为什么要多层

只有一层校验：「我们把 bug 修好了」
多层校验：「我们让这个 bug 不可能发生」

不同的层拦住不同的情况：
- 入口校验拦住大多数 bug
- 业务逻辑拦住边缘情况
- 环境守卫防止特定场景下的危险操作
- Debug log 在别的层都失效时提供线索

## 四个层

### Layer 1：入口校验
**目的：** 在 API 边界就拒掉明显非法的输入

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === '') {
    throw new Error('workingDirectory cannot be empty');
  }
  if (!existsSync(workingDirectory)) {
    throw new Error(`workingDirectory does not exist: ${workingDirectory}`);
  }
  if (!statSync(workingDirectory).isDirectory()) {
    throw new Error(`workingDirectory is not a directory: ${workingDirectory}`);
  }
  // ... proceed
}
```

### Layer 2：业务逻辑校验
**目的：** 确保数据对这个操作来说是合理的

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) {
    throw new Error('projectDir required for workspace initialization');
  }
  // ... proceed
}
```

### Layer 3：环境守卫
**目的：** 防止在特定场景下执行危险操作

```typescript
async function gitInit(directory: string) {
  // In tests, refuse git init outside temp directories
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    const tmpDir = normalize(resolve(tmpdir()));

    if (!normalized.startsWith(tmpDir)) {
      throw new Error(
        `Refusing git init outside temp dir during tests: ${directory}`
      );
    }
  }
  // ... proceed
}
```

### Layer 4：Debug 埋点
**目的：** 留下排查用的上下文

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  logger.debug('About to git init', {
    directory,
    cwd: process.cwd(),
    stack,
  });
  // ... proceed
}
```

## 如何套用这个模式

你发现一个 bug 时：

1. **追踪数据流** —— 坏值从哪儿来？在哪儿被用掉？
2. **列出所有检查点** —— 把数据流经的每一个点都列出来
3. **在每一层加校验** —— 入口、业务、环境、debug
4. **逐层测试** —— 试着绕过 Layer 1，验证 Layer 2 能拦住它

## 一次实际案例

Bug：空的 `projectDir` 导致 `git init` 跑到了源码目录里

**数据流：**
1. Test setup → 空字符串
2. `Project.create(name, '')`
3. `WorkspaceManager.createWorkspace('')`
4. `git init` 在 `process.cwd()` 里跑

**加上的四层：**
- Layer 1：`Project.create()` 校验不为空、存在、可写
- Layer 2：`WorkspaceManager` 校验 projectDir 不为空
- Layer 3：`WorktreeManager` 在 test 中拒绝在 tmpdir 之外执行 git init
- Layer 4：git init 之前记录 stack trace

**结果：** 1847 个 test 全过，这个 bug 再也复现不出来

## 关键洞察

这四层都是必要的。测试过程中，每一层都拦到了别的层漏掉的 bug：
- 不同的代码路径绕过了入口校验
- Mock 绕过了业务逻辑检查
- 不同平台上的边缘情况需要环境守卫来兜住
- Debug log 帮助识别出了结构性的误用

**不要只在一个点上加校验。** 每一层都加检查。

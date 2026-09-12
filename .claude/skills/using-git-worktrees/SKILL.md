---
name: using-git-worktrees
description: 开始需要与当前工作区隔离的功能开发时，或执行实现计划之前使用 —— 通过平台原生工具或退回 git worktree 来保证有一个隔离工作区
---

# 使用 Git Worktree

## 概述

确保工作在隔离的工作区里进行。优先用你所在平台的原生 worktree 工具。只有没有原生工具时，才退回手动的 git worktree。

**核心原则：** 先检测是否已经隔离，再用原生工具，最后才退回 git。绝不跟平台较劲。

**开始时要声明：** “我正在使用 using-git-worktrees 技能来搭建隔离工作区。”

## Step 0: 检测是否已经隔离

**动手创建任何东西之前，先检查自己是不是已经在一个隔离工作区里了。**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**Submodule（子模块）防线：** 在 git submodule 里，`GIT_DIR != GIT_COMMON` 同样成立。下结论说“已经在 worktree 里”之前，先确认自己不在 submodule 里：

```bash
# If this returns a path, you're in a submodule, not a worktree — treat as normal repo
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**如果 `GIT_DIR != GIT_COMMON`（且不在 submodule 里）：** 你已经在某个关联 worktree 里了。跳到 Step 2（项目初始化）。不要再创建 worktree。

连同 branch 状态一起汇报：
- 在某个 branch 上：“已经在隔离工作区 `<path>`，位于 branch `<name>`。”
- Detached HEAD：“已经在隔离工作区 `<path>`（detached HEAD，外部托管）。收尾时需要创建 branch。”

**如果 `GIT_DIR == GIT_COMMON`（或处于 submodule 中）：** 你在普通仓库的 checkout 里。

用户是否已经在给你的指令里表明了 worktree 偏好？如果没有，创建 worktree 之前先征得同意：

> “要我给你搭一个隔离的 worktree 吗？它能保护你当前的 branch 不受改动影响。”

用户已经声明过的偏好，直接用，不用再问。如果用户不同意，就地干活，跳到 Step 2。

## Step 1: 创建隔离工作区

**你有两套机制。按这个顺序试。**

### 1a. 原生 worktree 工具（首选）

用户已经要求了隔离工作区（Step 0 的同意）。你手上有没有现成创建 worktree 的办法？可能是名字类似 `EnterWorktree`、`WorktreeCreate` 的工具，一个 `/worktree` 命令，或者一个 `--worktree` 参数。有就直接用，跳到 Step 2。

原生工具会自动处理目录位置、branch 创建和清理。手上有原生工具却去用 `git worktree add`，会造出你的平台看不见、管不了的幽灵状态。

只有没有原生 worktree 工具可用时，才往下走 Step 1b。

### 1b. 退回 git worktree

**只在 Step 1a 不适用时用这个** —— 你没有原生 worktree 工具。用 git 手动创建 worktree。

#### 选目录

按这个优先级来。用户明确的偏好永远高于文件系统里现存的状态。

1. **检查你的指令里有没有声明好的 worktree 目录偏好。** 用户已经指定了就直接用，不用问。

2. **检查项目本地有没有现成的 worktree 目录：**
   ```bash
   ls -d .worktrees 2>/dev/null     # Preferred (hidden)
   ls -d worktrees 2>/dev/null      # Alternative
   ```
   找到就用。两个都存在时，`.worktrees` 优先。

3. **如果没有任何其他指引**，默认用项目根目录下的 `.worktrees/`。

#### 安全校验（只针对项目本地目录）

**创建 worktree 之前必须确认目录已被忽略：**

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

**如果没有被忽略：** 加到 .gitignore，提交这次改动，再往下做。

**为什么关键：** 防止把 worktree 的内容误提交进仓库。

#### 创建 worktree

```bash
# Determine path based on chosen location
path="$LOCATION/$BRANCH_NAME"

git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

**沙箱降级：** 如果 `git worktree add` 因为权限错误失败（沙箱拦截），告诉用户沙箱挡住了 worktree 创建，你改成在当前目录里干活。然后就地跑初始化和基线测试。

## Step 2: 项目初始化

自动检测并跑对应的初始化：

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

## Step 3: 验证基线是干净的

跑测试，确保工作区起步时是干净的：

```bash
# Use project-appropriate command
npm test / cargo test / pytest / go test ./...
```

**如果测试失败：** 汇报失败情况，问是继续还是先查。

**如果测试通过：** 汇报就绪。

### 汇报

```
Worktree 已就绪，位于 <full-path>
测试通过（<N> 个测试，0 失败）
可以开始实现 <feature-name>
```

## 速查

| 情况 | 动作 |
|-----------|--------|
| 已经在关联 worktree 里 | 跳过创建（Step 0） |
| 在 submodule 里 | 按普通仓库处理（Step 0 防线） |
| 有原生 worktree 工具 | 用它（Step 1a） |
| 没有原生工具 | 退回 git worktree（Step 1b） |
| `.worktrees/` 存在 | 用它（确认已忽略） |
| `worktrees/` 存在 | 用它（确认已忽略） |
| 两个都存在 | 用 `.worktrees/` |
| 都不存在 | 查指令文件，再默认 `.worktrees/` |
| 目录没被忽略 | 加到 .gitignore + 提交 |
| 创建时权限报错 | 沙箱降级，就地干活 |
| 基线测试失败 | 汇报失败 + 询问 |
| 没有 package.json/Cargo.toml | 跳过装依赖 |

## 常见的自我开脱

| 借口 | 事实 |
|--------|---------|
| “我肯定不在 worktree 里 —— 不用查” | 跑 Step 0。平台创建的隔离和 submodule 都能骗过肉眼，检测命令才能定论。 |
| “`git worktree add` 比找原生工具快” | 原生工具（比如 `EnterWorktree`）负责位置、branch 和清理。绕过它是头号错误 —— 会造出你的平台看不见、管不了的幽灵状态。 |
| “worktree 目录肯定早就被忽略了” | 跑 `git check-ignore`。worktree 目录没被忽略，就会把整棵树提交进仓库。 |
| “随便什么目录名都行” | 明确指令 > 现成的项目本地目录 > `.worktrees/` 默认值。 |
| “工作区是全新的 —— 基线测试可以等等” | 基线不干净会让之后每一次失败都说不清。现在就跑测试；测试失败还要继续，那是你搭档的决定。 |

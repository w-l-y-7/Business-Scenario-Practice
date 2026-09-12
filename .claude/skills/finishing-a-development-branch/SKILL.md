---
name: finishing-a-development-branch
description: 实现完成、所有测试通过后，需要决定如何整合这些工作时使用
---

# 收尾一个开发 branch

## 概述

**核心原则：** 验证测试 → 检测环境 → 给出选项 → 执行选择 → 清理。

**开始时要声明：** “我正在使用 finishing-a-development-branch 技能来完成这项工作。”

## Step 1: 验证测试

跑项目的完整测试套件（`npm test` / `cargo test` / `pytest` / `go test ./...`）。

**如果测试失败**，汇报失败情况并停下 —— 菜单要在一套全绿的测试之后才上：

```
测试失败（<N> 个失败）。收尾之前必须先修：

[显示失败内容]
```

**如果测试通过：** 继续 Step 2。

## Step 2: 检测环境

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
# Capture now, while still inside the workspace — Step 5 changes directory
# before cleanup (Step 6) needs this value
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

这决定了该显示哪个菜单，以及清理怎么走：

| 状态 | 菜单 | 清理 |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON`（普通仓库） | 标准 3 个选项 | 没有 worktree 要清理 |
| `GIT_DIR != GIT_COMMON`，有具名 branch | 标准 3 个选项 | 按来源判断（见 Step 6） |
| `GIT_DIR != GIT_COMMON`，detached HEAD | 精简 2 个选项（不含合并） | 外部托管 —— 保持原样 |

## Step 3: 确定 base branch

base branch 就是这次工作分叉出来的那个 —— 通常在计划、对话或 branch 的 upstream 里写了名字。如果还不确定，就问：“这个 branch 是从 <你的最佳猜测> 分出来的 —— 对吗？” 合并之前先确认：合错 base 想撤销代价很大。

## Step 4: 给出选项

**普通仓库和具名 branch 的 worktree —— 只给这 3 个选项：**

```
实现完成。你想怎么做？

1. 在本地合并回 <base-branch>
2. Push 并创建一个 Pull Request
3. 保持 branch 原样（我稍后自己处理）

选哪个？
```

**Detached HEAD —— 只给这 2 个选项：**

```
实现完成。你现在处于 detached HEAD（外部托管的工作区）。

1. 作为新 branch push 并创建 Pull Request
2. 保持原样（我稍后自己处理）

选哪个？
```

按原文照给菜单 —— 简洁，每个选项都来自上面的清单。丢弃工作只在你搭档明确要求时才发生（见下面“如果搭档要求丢弃工作”）。等对方回答；整合的决定权在他。

## Step 5: 执行选择

### 选项 1：在本地合并

```bash
# Get main repo root for CWD safety
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"

# Merge first — verify success before removing anything
git checkout <base-branch>
git pull
git merge <feature-branch>

# Verify tests on merged result
<test command>
```

如果合并后的结果测试失败：停下，worktree 和 branch 都留在原地，去查 —— 什么都还没 push，所以这次合并是本地的，可以恢复。

合并结果一旦全绿：清理 worktree（Step 6），然后删 branch：

```bash
git branch -d <feature-branch>
```

### 选项 2：Push 并创建 PR

```bash
git push -u origin <feature-branch>
# From a detached HEAD, name the new branch on the remote:
# git push origin HEAD:refs/heads/<new-branch>
```

然后针对 <base-branch> 创建 pull/merge request，用代码托管平台的工具 —— 有 CLI 就用它，否则用大多数平台在 push 时打印出来的创建 URL —— 仓库里如果有 PR 模板和惯例就照着来，然后把 URL 汇报给搭档。

保留 worktree —— 你的搭档要在那里根据 PR 反馈迭代。

### 选项 3：保持原样

汇报：“保持 branch <name>。worktree 已保留在 <path>。”

### 如果搭档要求丢弃工作

这条路径只作为一个明确请求的回应而存在 —— 请求是把工作扔掉。先确认：

```
这会永久删除：
- Branch <name>
- 所有 commit：<commit-list>
- 位于 <path> 的 worktree

输入 'discard' 以确认。
```

等这个确切的确认。收到之后：

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
```

然后清理 worktree（Step 6），强删 branch：

```bash
git branch -D <feature-branch>
```

## Step 6: 清理工作区

**对选项 1 和已确认的丢弃执行。** 选项 2 和 3 永远保留 worktree。两个调用方都已经把目录切到主仓库根 —— 删除 worktree 必须从 worktree 外面执行 —— 并使用 Step 2 里、在切换目录之前捕获的 `GIT_DIR`/`GIT_COMMON`/`WORKTREE_PATH` 值。

**如果 `GIT_DIR == GIT_COMMON`：** 普通仓库，没有 worktree 要清理。结束。

**如果 `WORKTREE_PATH` 在 `.worktrees/` 或 `worktrees/` 下面：** 这个 worktree 是 Superpowers 创建的 —— 清理归我们管：

```bash
git worktree remove "$WORKTREE_PATH"
git worktree prune  # Self-healing: clean up any stale registrations
```

**如果删除被拒绝**（`contains modified or untracked files`）：worktree 里存着别处都没有的文件 —— 没提交的计划、笔记或草稿。绝不要自作主张 `--force`。把利害关系摆给搭档看，然后问：

```bash
git -C "$WORKTREE_PATH" status --porcelain -uall
```

```
Worktree 删除被拒绝 —— 这些文件从未提交过：

<文件列表>

1. 清理之前把它们提交到 <branch>
2. 把它们移到 <main repo root>
3. 删掉它们（无法恢复）

选哪个？
```

执行选择，然后删掉 worktree。

**其他情况：** 这个工作区归宿主环境所有 —— 保持原样。如果你的平台提供了退出工作区的工具，就用它。

## 速查

| 选项 | 合并 | Push | 保留 Worktree | 清理 Branch |
|--------|-------|------|---------------|----------------|
| 1. 本地合并 | 是 | - | - | 是 |
| 2. 创建 PR | - | 是 | 是 | - |
| 3. 保持原样 | - | - | 是 | - |
| 丢弃（仅限明确请求） | - | - | - | 是（强删） |

## 常见的自我开脱

| 借口 | 事实 |
|--------|---------|
| “这次会话里测试早就过了” | 在你即将整合的那棵树上再跑一遍套件。一次全绿只能证明它跑的那棵树。 |
| “他显然想合并” | 整合是你搭档的决定。给出菜单，然后等。 |
| “他好像不想要这个功能了 —— 我来提议丢弃” | 菜单照原文就是完整的。只有搭档明确开口要求时才丢弃。 |
| “‘行，把它去掉吧’ 也算确认” | 只有亲手敲下 `discard` 这个词才授权删除。 |
| “PR 都提了，worktree 现在就是垃圾” | PR 反馈要在那个 worktree 里改。工作落地之前它一直留着。 |
| “另一个 worktree 看着像废弃的 —— 我一起清了” | 只清理 `.worktrees/` 或 `worktrees/` 下面的 worktree。其他都归宿主管。 |
| “删除被拒绝 —— `--force` 只是把清理做完” | 拒绝意味着有文件只存在于那个 worktree 里。`--force` 会把它们永久毁掉。摆给搭档看再问。 |
| “合并结果失败大概是偶发抖动” | 合并结果失败会停掉一切。查清楚之前，branch 和 worktree 都原地不动。 |
| “base branch 显然是 main” | 确认分叉点，或者问。合错 base 想撤销代价很大。 |
| “push 被拒 —— force-push 能解决” | push 被拒说明远端动过了。去查；只有搭档明确要求才 force-push。 |

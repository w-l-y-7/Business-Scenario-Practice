# 可视化伴侣指南

跑在浏览器里的可视化头脑风暴伴侣，用来展示草图、示意图和选项。

## 什么时候用

逐个问题判断，而不是整场会话定一次。判断标准：**这个问题，用户看一眼会不会比读文字更容易懂？**

**内容本身就是视觉化的，用浏览器：**

- **UI 草图** —— 线框图、布局、导航结构、组件设计
- **架构示意图** —— 系统组件、数据流、关系图
- **并排视觉对比** —— 比较两种布局、两套配色、两个设计方向
- **设计打磨** —— 问题涉及观感、间距、视觉层次时
- **空间关系** —— 状态机、流程图、实体关系画成图

**内容是文字或表格的，用终端：**

- **需求和范围问题** —— “X 是什么意思？”“哪些功能在范围内？”
- **概念性的 A/B/C 选择** —— 在只用文字描述的方案之间挑
- **取舍清单** —— 优缺点、对比表
- **技术决策** —— API 设计、数据建模、架构方案选择
- **澄清问题** —— 凡是答案是文字、而非视觉偏好的

聊到 UI 话题的问题，不自动等于视觉问题。“你想要哪种向导？”是概念问题 —— 用终端。“这几种向导布局，哪种感觉对？”是视觉问题 —— 用浏览器。

## 工作原理

服务器盯着一个目录里的 HTML 文件，把最新的那个发给浏览器。你把 HTML 内容写进 `screen_dir`，用户在浏览器里看到它，可以点击选择选项。选择结果记录到 `state_dir/events`，你下一轮读这个文件。

**内容片段 vs 完整文档：** 如果你的 HTML 文件以 `<!DOCTYPE` 或 `<html` 开头，服务器就原样发出（只注入辅助脚本）。否则，服务器会自动把你的内容套进外框模板里 —— 加上页头、CSS 主题、连接状态和全套交互基础设施。**默认写内容片段。** 只有需要对页面完全掌控时，才写完整文档。

## 启动会话

```bash
# Start AFTER the user approves the companion. --open auto-opens their browser on
# the first screen; --project-dir persists mockups and enables same-port restart.
scripts/start-server.sh --project-dir /path/to/project --open

# Returns: {"type":"server-started","port":52341,
#           "url":"http://localhost:52341/?key=ab12…",
#           "screen_dir":"/path/to/project/.superpowers/brainstorm/12345-1706000000/content",
#           "state_dir":"/path/to/project/.superpowers/brainstorm/12345-1706000000/state"}
```

把返回结果里的 `screen_dir` 和 `state_dir` 存下来。用了 `--open` 之后，你推出第一个页面时浏览器会自己打开 —— 不用请用户去开，但还是把 URL 一并给他留个后手（无界面或远程环境下不会自动打开）。

**URL 里带一个会话密钥（`?key=…`）。** 任何不含它的请求，服务器都会拒绝。所以永远要把 `url` 字段里**完整**的 URL 给用户 —— 不要去掉查询字符串，也不要只给一个光秃秃的 `http://host:port`。这个密钥把守着 HTTP 和 WebSocket 访问，防止误开的浏览器标签页或网络上的其他机器读取页面内容或注入事件。首次加载后，浏览器会用 cookie 记住密钥，之后刷新和访问 `/files/*` 资源都不用再带上它。

**怎么找连接信息：** 服务器会把启动时的 JSON 写到 `$STATE_DIR/server-info`。如果你是后台启动的服务器、没抓到 stdout，就读这个文件拿 URL 和端口。用了 `--project-dir` 时，到 `<project>/.superpowers/brainstorm/` 里找会话目录。

**注意：** 把项目根目录作为 `--project-dir` 传进去，草图就能留在 `.superpowers/brainstorm/` 里，服务器重启后还在。不传的话，文件会落到 `/tmp` 并被清掉。提醒用户把 `.superpowers/` 加进 `.gitignore`（如果还没有的话）。

**按平台启动服务器：**

**Claude Code:**
```bash
# Default mode works — the script backgrounds the server itself.
scripts/start-server.sh --project-dir /path/to/project --open
```

在 Windows 上，脚本会自动检测并切到前台模式（这会一直占住当前工具调用）。请在 Bash 工具调用上加 `run_in_background: true`，让服务器跨对话轮次继续活着，下一轮再读 `$STATE_DIR/server-info` 拿到 URL 和端口。

**Codex:**
```bash
# Codex reaps background processes. The script auto-detects CODEX_CI and
# switches to foreground mode. Run it normally — no extra flags needed.
scripts/start-server.sh --project-dir /path/to/project --open
```

**Gemini CLI:**
```bash
# Use --foreground and set is_background: true on your shell tool call
# so the process survives across turns
scripts/start-server.sh --project-dir /path/to/project --open --foreground
```

**Copilot CLI:**
```bash
# Start it with Copilot CLI's non-blocking/background shell mechanism so the
# server survives across turns. Keep --foreground so the harness, not the
# script, owns backgrounding. The launcher is a .sh, so invoke it via bash
# (on Windows, call Git Bash's bash.exe from the PowerShell tool).
bash scripts/start-server.sh --project-dir /path/to/project --open --foreground
```

**其他环境：** 服务器必须在后台持续运行，跨过一轮轮对话。如果你的环境会回收游离进程，就用 `--foreground`，并借助你所处平台的后台执行机制来启动它。

如果浏览器打不开这个 URL（远程或容器环境里很常见），就绑定一个非回环地址：

```bash
scripts/start-server.sh \
  --project-dir /path/to/project \
  --host 0.0.0.0 \
  --url-host localhost
```

用 `--url-host` 控制返回的 URL JSON 里打印哪个主机名。

## 操作循环

1. **先确认服务器还活着**，然后**写 HTML** 到 `screen_dir` 里的一个新文件：
   - **必须做：提到 URL 或推出页面前，先确认服务器还活着。** 检查 `$STATE_DIR/server-info` 存在、`$STATE_DIR/server-stopped` 不存在。如果服务器已经停了，用**同样的 `--project-dir`** 重新跑 `start-server.sh` —— 它会复用同一个端口，用户开着的标签页会自己重连（服务器停着时它显示“已暂停”的浮层），你也不用再发一遍新 URL。服务器空闲 4 小时后会自动退出（可用 `--idle-timeout-minutes` 调整）。
   - 用能表意的文件名：`platform.html`、`visual-style.html`、`layout.html`
   - **绝不复用文件名** —— 每个页面都要新建文件
   - 用你的建文件工具 —— **绝不要用 cat/heredoc**（会把一堆噪声倒进终端）
   - 服务器会自动发出最新的文件

2. **告诉用户接下来会看到什么，然后结束本轮：**
   - 每一次都提醒一遍 URL（每一步都要，不只第一步）
   - 用一句话概括屏幕上有什么（比如“正在展示首页的 3 种布局方案”）
   - 请他们在终端里回复：“看一眼，告诉我你觉得怎么样。想选的话就点一下。”

3. **你下一轮** —— 用户在终端里回复之后：
   - 如果 `$STATE_DIR/events` 存在就读它 —— 这里装着用户在浏览器里的操作（点击、选择），每行一条 JSON
   - 结合用户在终端里的文字，拼出完整情况
   - 终端里的消息是主要反馈；`state_dir/events` 提供结构化的交互数据

4. **改还是往下走** —— 如果反馈意味着当前页面要改，就写一个新文件（比如 `layout-v2.html`）。当前这一步得到确认后，才进入下一个问题。

5. **回到终端时清空页面** —— 下一步用不着浏览器时（比如一个澄清问题、一次取舍讨论），推一个等待页，把过时的内容清掉：

   ```html
   <!-- filename: waiting.html (or waiting-2.html, etc.) -->
   <div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
     <p class="subtitle">Continuing in terminal...</p>
   </div>
   ```

   这样用户就不会在话题早就翻篇之后，还盯着一个已经选完的页面看。等下一个视觉问题出现，照常推一个新的内容文件。

6. 重复，直到做完。

## 写内容片段

只写页面内部的内容。服务器会自动把它套进外框模板（页头、主题 CSS、连接状态和全套交互基础设施）。

**最简示例：**

```html
<h2>Which layout works better?</h2>
<p class="subtitle">Consider readability and visual hierarchy</p>

<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>Single Column</h3>
      <p>Clean, focused reading experience</p>
    </div>
  </div>
  <div class="option" data-choice="b" onclick="toggleSelect(this)">
    <div class="letter">B</div>
    <div class="content">
      <h3>Two Column</h3>
      <p>Sidebar navigation with main content</p>
    </div>
  </div>
</div>
```

就这样。不用写 `<html>`、不用写 CSS、不用写 `<script>` 标签。这些服务器都提供了。

## 可用的 CSS 类

外框模板为你的内容提供了以下 CSS 类：

### 选项（A/B/C 选择）

```html
<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>Title</h3>
      <p>Description</p>
    </div>
  </div>
</div>
```

**多选：** 在容器上加 `data-multiselect`，用户就能选多项。每点一下切换该项的选中样式。

```html
<div class="options" data-multiselect>
  <!-- same option markup — users can select/deselect multiple -->
</div>
```

### 卡片（视觉设计）

```html
<div class="cards">
  <div class="card" data-choice="design1" onclick="toggleSelect(this)">
    <div class="card-image"><!-- mockup content --></div>
    <div class="card-body">
      <h3>Name</h3>
      <p>Description</p>
    </div>
  </div>
</div>
```

### 草图容器

```html
<div class="mockup">
  <div class="mockup-header">Preview: Dashboard Layout</div>
  <div class="mockup-body"><!-- your mockup HTML --></div>
</div>
```

### 分栏视图（并排）

```html
<div class="split">
  <div class="mockup"><!-- left --></div>
  <div class="mockup"><!-- right --></div>
</div>
```

### 优缺点

```html
<div class="pros-cons">
  <div class="pros"><h4>Pros</h4><ul><li>Benefit</li></ul></div>
  <div class="cons"><h4>Cons</h4><ul><li>Drawback</li></ul></div>
</div>
```

### 示意元素（线框图积木）

```html
<div class="mock-nav">Logo | Home | About | Contact</div>
<div style="display: flex;">
  <div class="mock-sidebar">Navigation</div>
  <div class="mock-content">Main content area</div>
</div>
<button class="mock-button">Action Button</button>
<input class="mock-input" placeholder="Input field">
<div class="placeholder">Placeholder area</div>
```

### 排版与分节

- `h2` —— 页面标题
- `h3` —— 小节标题
- `.subtitle` —— 标题下方的次级文字
- `.section` —— 带下边距的内容块
- `.label` —— 小号大写的标签文字

## 浏览器事件格式

用户在浏览器里点击选项时，这些操作会记录到 `$STATE_DIR/events`（每行一个 JSON 对象）。你推出新页面时，这个文件会自动清空。

```jsonl
{"type":"click","choice":"a","text":"Option A - Simple Layout","timestamp":1706000101}
{"type":"click","choice":"c","text":"Option C - Complex Grid","timestamp":1706000108}
{"type":"click","choice":"b","text":"Option B - Hybrid","timestamp":1706000115}
```

完整的事件流能看出用户的探索轨迹 —— 他们可能在定下来之前点好几个选项。最后一个 `choice` 事件通常就是最终选择，但点击的模式能透露出犹豫或偏好，值得再问一句。

如果 `$STATE_DIR/events` 不存在，说明用户没在浏览器里操作 —— 只看他们在终端里的文字就好。

## 设计建议

- **保真度随问题而定** —— 布局问题用线框图，打磨问题用精细稿
- **每个页面都写清问题** —— 写“哪种布局看着更专业？”，而不只是“选一个”
- **先改再进** —— 反馈要求改当前页面，就写一个新版本
- **每屏最多 2-4 个选项**
- **该用真实内容时就用** —— 做摄影作品集，就上真实图片（Unsplash）。占位内容会盖住设计问题。
- **草图保持简单** —— 重点在布局和结构，不做像素级精修

## 文件命名

- 用能表意的名字：`platform.html`、`visual-style.html`、`layout.html`
- 绝不复用文件名 —— 每个页面都必须是新文件
- 迭代时：加版本后缀，比如 `layout-v2.html`、`layout-v3.html`
- 服务器按修改时间发出最新的文件

## 清理

```bash
scripts/stop-server.sh $SESSION_DIR
```

如果会话用了 `--project-dir`，草图文件会留在 `.superpowers/brainstorm/` 里，方便以后查阅。只有落在 `/tmp` 的会话会在停止时被删掉。

## 参考

- 外框模板（CSS 参考）：`scripts/frame-template.html`
- 辅助脚本（客户端）：`scripts/helper.js`

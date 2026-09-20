# tools/pdf/ —— Markdown 出 PDF

**一句话：文稿用 Markdown 写，PDF 用 `build.ps1` 出，出完自动查版式。**

版式规则在 `.claude/rules/output-format.md` §一，这里只讲怎么用。

## 速查

```powershell
cd investment-research

# 出正式报告（产物落 build/，随后自动跑版式检查）
.\tools\pdf\build.ps1 -InputPath output\investment-report.md

# 出试排样张
.\tools\pdf\build.ps1 -InputPath tools\pdf\smoke\试排.md

# 只跑检查，不出片
python tools\pdf\check_layout.py build\试排.pdf --margin 17

# 单独重生成试排样图
python tools\pdf\make_smoke_figure.py
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `-InputPath` | 必填 | 要转换的 Markdown |
| `-OutputPath` | `build/{同名}.pdf` | 产物路径 |
| `-Margin` | `17mm` | 页边距；官方规则另有规定时覆盖它 |
| `-FontSize` | `10pt` | 只能填 10pt / 11pt / 12pt |
| `-SkipCheck` | 关 | 加它就只出片、不检查 |

## 目录里各文件管什么

| 文件 | 管什么 | 改了会怎样 |
| --- | --- | --- |
| `build.ps1` | 构建入口 | 路径、参数、调 pandoc 的顺序都在这 |
| `header.tex` | LaTeX 导言区 | 字体、断行、表格、图片、页码、封面封底环境全在这 |
| `divs-to-latex.lua` | 围栏 div → LaTeX 环境 | **删了样式全失效**，见下面「坑一」 |
| `check_layout.py` | 版式检查 | 五项：页数、溢出、页码、内容、图片 |
| `make_smoke_figure.py` | 生成试排样图 | 图上数字是编的，只为验证图片能不能排进去 |
| `smoke/试排.md` | 试排稿 | 版式的回归样本，改动 `header.tex` 后拿它验 |

## 四个坑（都实测踩过）

### 坑一：pandoc 会静默丢掉围栏 div

`::: {.source} ... :::` 在 LaTeX 输出里**只剩内容、外壳没了**。编译不报错、
样式却一直没生效 —— 这种错只会让成品悄悄不对，不会让流水线停下。

`divs-to-latex.lua` 就是补这个的，把下列类名转成同名 LaTeX 环境（定义在 `header.tex`）：

| 类名 | 排版效果 |
| --- | --- |
| `cover` | 单独一页、不出页码，**之后页码重置为 1** |
| `backcover` | 单独一页、不出页码，不重置页码 |
| `source` | 来源标注，8–9 pt |
| `placeholder` | 占位内容，一眼可辨、不伪装成真数 |

**删掉这个过滤器 = 上面四样全部失效。** 而且不会报错。

div 可以嵌套（封面里放占位块是常见写法），过滤器会递归处理。

### 坑二：pandoc 默认模板不加载 `graphicx`

不补这一行，文稿里的 `![](figures/x.png)` **根本编译不过**。已在 `header.tex` 里补上，
并同时限了宽高：

```latex
\setkeys{Gin}{width=\linewidth,height=\textheight,keepaspectratio}
```

横图按版心宽度缩、竖图按版心高度缩，都不变形、都不出血。实测一张 8:3.6 的横图
排出来正好卡在版心 48.2–547.1 pt，一格不差。

### 坑三：`build.ps1` 必须带 UTF-8 BOM

PowerShell 5.1 读 `.ps1` 时，**没有 BOM 就按系统 ANSI 码页解码**。脚本里全是中文，
一旦丢了 BOM，报错会长这样：

```
Unexpected token '鐢熸垚鎴愬姛锛?' in expression or statement.
```

**改完这个文件，确认前三个字节还是 `239,187,191`。** 用 Edit/Write 改完最好复核一次：

```powershell
[System.IO.File]::ReadAllBytes("tools\pdf\build.ps1")[0..2] -join ','
```

### 坑四：字体只在 `header.tex` 一处设

不要另外往 pandoc 传 `-V CJKmainfont`。pandoc 只认得到正文主字体、管不到 sans 与 mono，
两处各设一半必然对不上 —— 正文换了字体、代码块里的中文还是旧字体，很难一眼看出来。

**要不要把字体随项目保留？** 目前没有。本机 `C:\Windows\Fonts` 有 `Microsoft YaHei`、
`SimSun`、`SimHei`，直接按名引用即可。等这个项目要**在别的机器上重建**（或者走 Overleaf）时，
再把字体文件放进项目、在 `header.tex` 里改用相对路径引用。现在放进来只是白白增加十几 MB，
而仓库里连 43 MB 的财报 PDF 都不入库。

## 怎么加图

1. 按 `figures/README.md` 的规范把图放进 `figures/`
2. 文稿里写 `![图 1 中际旭创收入结构](figures/F01-收入结构.png)`
3. 图下面配一个来源块：

   ```
   ::: {.source}
   数据来源：2025 年年报，第 88 页，A 级。图由使用者按定稿数据绘制。
   :::
   ```

路径按**项目根**写（`figures/xxx.png`），`build.ps1` 已把项目根加进 `--resource-path`。
不用管文稿在哪个子目录。

## 试排

**别等写满 10 页才第一次出 PDF。** 改动 `header.tex` 后跑一遍：

```powershell
.\tools\pdf\build.ps1 -InputPath tools\pdf\smoke\试排.md
```

试排稿覆盖了几种最容易出事的版式：最宽的 7 列表、拆成上下两张的续表、
夹长英文与完整 URL 的中文来源、带圈数字标题、一张横图，以及封面封底的页码处理。

检查会打印实际页数和封面封底页码位置，对照一下：

```
  总页数：4
  封面封底（不计页码）：[1, 4]
试排检查五项全部通过。
```

正文应从 1 起排；如果封面之后是 2，说明 `cover` 环境没生效（回去看坑一）。

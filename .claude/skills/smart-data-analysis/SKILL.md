---
name: smart-data-analysis
allowed-tools: Read Write Edit Glob Bash
description: 当用户要分析经济/金融/业务数据（CSV、Excel、报表、DB，或要某只股票/指数的实时行情与历史对比）时使用。它会根据数据规模与形态自动选路：小文件直接本地分析出统计摘要+图表，大文件/多表关联/要 SQL 聚合走 sqlite，明确要"实时/最新/盘中"行情走 akshare 并做历史对比。凡出现：帮我看看这个 csv / 分析这份数据 / 这个表多大怎么处理 / 某股现价和近期走势 / 把这两张表关联起来统计 / 数据量很大怎么办，即使没说 skill，都用它。多步、需运行本地 python 脚本并依赖文件或网络，不是一两句能答完的即时问答。边界：要的是上市公司财报分析/财务比率/同业对比/年报中报解读时，交给 quarterly-financial-analysis；本技能处理"任意数据文件 + 实时行情/走势"。
---

# 上下文感知数据分析（三路路由）

核心是**先判后算**：不默认把任何数据都往一条管道里灌，而是先探测数据的规模、形态与用户意图，选一条最省、最合适的路径，并把"为什么走这条路"讲给用户。

## 约定（先读）

- `<skill_dir>` = 本 SKILL.md 所在目录（含 `scripts/`）。运行时产物一律放**当前会话工作目录**下的 `output/`（目录不存在先建），不要写进 skill 目录。
- 需要 Python + pandas/matplotlib（本机已装）；命令依次试 `python`、`py -3`。路径 C 另需 `akshare`（本机已装）。
- 脚本统一习惯：路径尽量给绝对或相对 cwd 的路径；图表存 PNG，报告存 Markdown，中文标题/图注可用（脚本已设 Microsoft YaHei/SimHei）。
- 编码：CSV 优先 utf-8/utf-8-sig，GBK 自动回退；**读中文数据别假定 UTF-8**。
- 行数阈值默认 **1000 行**；用户明确说"数据很大/要关联/要 SQL"时不必拘泥于行数，直接按判定走。

## 第 0 步：判定路径并向用户说明

按以下顺序判断（命中即止）：

| 信号 | 路径 |
| --- | --- |
| 用户要某标的/指数的**实时、最新、盘中、现价** | **C**（akshare） |
| 输入是 `.db/.sqlite` 库，或 **≥2 个文件要关联/join**，或用户要 **SQL 聚合/分组** | **B** |
| 给了**单个文件**（CSV/Excel/JSON），行数模糊或超常规 | 先跑 `local_analysis.py --inspect` 看实际行数；**≤1000 行** → **A**；否则 → **B** |
| 只给了主题没给数据，也不是实时 | 先问：数据在哪？要实时还是历史文件？ |

**做（Why：路由对不对决定这一步值不值。小文件硬塞 sqlite 是浪费，实时需求读本地旧文件是答非所问）：**
- 判定靠"意图 + 行数探测"，不要猜：文件行数不确定就先 `--inspect`（它只读前几行，很快）。
- **向用户复述选择**：`检测到数据为 <类型>（<N> 行 / 需实时获取），将采用路径 X（原因）。`
- 走到路径后若发现判断错了（如小文件其实想跨表算），停下来换路并说明，不硬撑。

## 路径 A：小文件本地分析（≤1000 行）

```bash
python "<skill_dir>/scripts/local_analysis.py" --inspect --input {file}     # 先探行/列
python "<skill_dir>/scripts/local_analysis.py" --input {file}               # 正式跑
```

产出：`output/summary_{file}.md`（各列类型/缺失/类别数 + 数值统计）+ `output/{chart,hist,bar}_*.png`。

**做（Why：单文件分析的价值在快、可视、人能一眼读）：**
- 读 `summary_*.md` 后向用户讲**要点**：数据规模、有无缺失/重复、哪些列值得看、图上有什么趋势/异常——别把整份表复读一遍。
- sanity check：统计里出现明显不合理值（负价格、±1000% 涨跌、NaN 占多数）要点出来，多半是单位或脏数据问题。
- 用户想要更多图（箱线、散点、对数轴）就按需补画，存同目录。

## 路径 B：大数据/多表/要 SQL（>1000 行或需关联聚合）

```bash
# 文件按顺序变成内存 sqlite 表 t0、t1、…
python "<skill_dir>/scripts/db_query.py" --source {a.csv} --query profile
python "<skill_dir>/scripts/db_query.py" --source {a.csv} --source {b.csv} --query join --on {key}
python "<skill_dir>/scripts/db_query.py" --source {a.csv} --query top --by {数值列} --n 10
python "<skill_dir>/scripts/db_query.py" --source {a.csv} --query custom --sql "SELECT 城市, SUM(金额) FROM t0 GROUP BY 城市"
# 已有 sqlite 库直接用库内真实表名
python "<skill_dir>/scripts/db_query.py" --db {data.db} --query profile
python "<skill_dir>/scripts/db_query.py" --db {data.db} --query custom --sql "SELECT * FROM {表} LIMIT 10"
```

产出：`output/db_{query}_{file}.md`。

**做（Why：走 B 不是为了跑通 demo，而是让几千上万行/多表操作发生在 SQL 里，内存可控、逻辑可复核）：**
- join 前先确认**关联列名两边一致**（不一致先问用户映射或 `custom` 改名），并看输出里的左右缺失行数，缺失很大说明关联键有问题。
- `custom` 是逃生舱：把列名列清楚再写 SQL，出错了按提示对可用表名（`t0…`）改。
- 报给用户的结论要给**数字出处**（哪张表/哪个 SQL 算出来的）。

## 路径 C：实时行情（akshare）

```bash
python "<skill_dir>/scripts/api_fetch.py" --symbol {6位代码} [--days 120]
```

产出：`output/realtime_{code}_{yyyymmdd}.md` + `output/realtime_{code}.png`。

**做（Why：实时分析 = 最新快照 + 历史参照，单看现价没意义）：**
- 输出会区分"实时接口成功"与"降级为最近收盘"（网络/休市/非交易时段）。降级不叫失败，把降级原因告诉用户。
- 报结论时讲：现价/日涨跌 + 窗口涨跌幅 + 高低点时间区间的**观察**，别下买卖建议。
- akshare 偶发网络拒连：重试一次；仍失败就明确"当前无法联网取数"，不拿历史糊弄成实时。

## 收尾自查

- 产物在 `output/`：A 有 `summary_*.md`+图；B 有 `db_*.md`；C 有 `realtime_*.md`+图。
- 已向用户说明走了哪条路径及原因。
- 报给用户的每个数字都能溯源到产物文件或 SQL；没有把降级/缺失说成完整成功。
- 编码/中文图正常；没把 1000 行死板当规矩而忽略用户真实诉求。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| CSV 中文乱码 | 脚本已自动回退 GBK；手动读时用 Read 可能乱码，就靠脚本 |
| matplotlib 中文豆腐块 | 脚本已设 YaHei/SimHei；若换机器，按缺字体提示处理 |
| akshare 函数不存在 | 版本旧：`pip install -U akshare`；或用 `hasattr(ak, 'stock_zh_a_hist')` 内省现名 |
| 实时取数网络拒连 | 重试一次；仍失败明确告知，用历史降级并标注 |
| 判断成 A 后发现其实要跨表 | 停，改用 B（join）并说明 |
| 单文件 10 万行硬算很慢 | 走 B：入库后 SQL 聚合，别让 pandas 全量读 |
| 用户没给数据却说"分析一下" | 先问清数据位置与意图，不瞎猜 |

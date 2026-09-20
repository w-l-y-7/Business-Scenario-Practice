# 行情数据技能迁移审计：gs-stock-market-query

> **审计对象**：`D:\git仓库\investment project\.claude\skills\gs-stock-market-query\`
> **迁移去向**：本项目 `investment-research`（估值标的：中际旭创 300308.SZ / 3308.HK）
> **审计日期**：2026-09-20
> **审计性质**：只读。本次不复制、不移动、不修改源项目任何文件。
> **结论**：**不迁移**（关键项 1、2、3、4 未通过）

---

## 一、审计对象构成

源技能包只有三个文件，**不含任何 schema 或 config**：

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 技能说明、接口清单、参数表、鉴权流程 |
| `scripts/get_data.py` | 唯一脚本，六个 HTTP 封装函数 |
| `scripts/test_get_data.py` | 单元测试，全程 mock，不碰真实网络 |

脚本本体（`scripts/get_data.py`，共 334 行）只做两件事：按参数拼 URL、发 GET 请求、把原始 JSON 打印出来。它**不做字段映射、不做复权、不打币种、不记抓取时点、不落盘**。这一点决定了后面多数条目的结论。

---

## 二、结论速览

| # | 检查项 | 结论 | 依据 |
| --- | --- | --- | --- |
| 1 | 支持指定历史交易日 | **部分通过** | `SKILL.md` L156-170；`get_data.py` L244-271 |
| 2 | 返回 `actual_trade_date` | **不通过** | `SKILL.md` L269-281；全包无该字段 |
| 3 | 返回 `unadjusted_close` | **不通过** | 全包无复权概念 |
| 4 | 明确 `adjustment=none` | **不通过** | 全包无复权概念 |
| 5 | 返回 `currency` | **不通过** | 全包无币种字段 |
| 6 | 返回 `source` / `provider` | **部分通过** | `SKILL.md` L12；`get_data.py` L22 |
| 7 | 保留 `retrieved_at` | **不通过** | `get_data.py` L274-333 |
| 8 | 处理停牌、休市、非交易日 | **部分通过** | `SKILL.md` L38-40 |
| 9 | 支持 300308.SZ 与 3308.HK | **通过** | `SKILL.md` L289-293；`get_data.py` L104-110 |
| 10 | 不依赖账号 / Cookie / API key / 许可证 | **不通过** | `SKILL.md` L15-18、L193-212；`get_data.py` L17-20 |
| 11 | 缓存与原始响应留存 | **部分通过** | `get_data.py` L56-75、L329 |
| 12 | 稳定的异常处理 | **部分通过** | `get_data.py` L24、L78-101 |

关键项（1、2、3、4、9）中，第 9 项通过，**第 1、2、3、4 项不通过**，故结论为「不迁移」。

---

## 三、逐项审计

### 1. 是否支持指定历史交易日 —— 部分通过

历史行情走 `past_hq`（接口 `GET /gsnews/market/agentbot/queryPastHQInfo/1.0`），参数表只有一项与时间有关：`wantNums`，含义是「近 n 个交易日」（`SKILL.md` L162-169）。脚本侧对应 `query_past_hq(code, set_code, want_nums, target=0, mas=None)`（`get_data.py` L244），参数拼接见 L258-266。

**全包没有任何 `date` / `start_date` / `end_date` / `trade_date` 参数**，无法直接点名「取 2026-09-18 这天」。

有一处文档与参数表打架：`SKILL.md` L50 的示例写「查询 300750 从 2025 年 1 月 1 日到 3 月 15 日的历史行情」，但参数表（L162-169）和脚本（L244-271）都不支持区间。**以参数表为准，这条示例不成立。**

**卡在哪**：只能按「近 n 个交易日」取数，再由调用方在返回的多日线里自行挑出目标日期。本项目要的是**指定交易日**（首轮 2026-09-18，且必须取提交截止日之前最后一个已收盘交易日），这个能力源技能不直接提供。若强行用「拉 N 天再筛」，还要先解决第 2 条——返回记录里的日期字段叫什么，本包没有文档化。

### 2. 是否返回 actual_trade_date —— 不通过

本包对返回字段的唯一说明是「各接口返回字段请参考接口文档」，随后只给了一层外壳 `{"result": {"code", "msg"}, "data": {...}}`（`SKILL.md` L269-281）。`data` 内部字段**没有任何定义**，包内也没有 schema 文件。

全包（`SKILL.md`、`get_data.py`、`test_get_data.py`）搜索不到 `actual_trade_date`、`trade_date`、`tradingdate` 之类的字段名。唯一沾边的是 `SKILL.md` L38 的一句行为描述：「非交易时段返回上一交易日收盘价」——这是隐式回退，**不附带任何标明「实际是哪一天」的字段**。

**卡在哪**：哪怕多日线记录里自带日期，字段名未知，无法可靠映射到本项目 `actual_trade_date`；实时接口更是只有「上一交易日收盘价」这个行为，没有任何字段让你把实际交易日读出来。本项目 `data-standard.md` §2.3（L103）硬性要求「行情日期遇休市，取前一个交易日，并把实际交易日如实写出来」，此条是刚需。

### 3. 是否返回 unadjusted_close —— 不通过

全包不出现「复权 / 除权 / adjust / adj」任何字样。脚本把接口返回的原始 JSON 直接打印（`get_data.py` L329），中间不做口径标注。

因此**无法确认接口返回的收盘价是未复权、前复权还是后复权**。这不是「字段缺失」这么简单——即便字段名叫 `close`，也不知道它的口径。

**卡在哪**：本项目现存的行情材料（`raw_data\market\中际旭创-行情数据.md` L22）明确写「所有价格**未复权**」并注明来源口径 `adjust=""`。源技能给不出这个保证，属于口径不可控。

### 4. 是否明确 adjustment=none —— 不通过

同上，全包没有 `adjustment` 参数或字段，没有 `none` / `none_adj` 之类取值（`SKILL.md` L158-170 的 `past_hq` 参数表；`get_data.py` L244-271）。**这一项完全未涉及。**

### 5. 是否返回 currency —— 不通过

全包无 `currency`、`币种`、`CNY`、`HKD` 字段。有一处相近但不等价：`setCode` 用市场代码区分地域（`SKILL.md` L289-293：深圳 0 / 上海 1 / 北交所 2 / 港股 -1 / 美股 74；脚本侧 `SET_CODE_MAP` 见 `get_data.py` L104-110）。**市场 ≠ 币种**，返回数据里没有币种字段。

本项目对 3308.HK 尤其敏感——港股是 HKD，A 股是 CNY，估值模型 `model\inputs\historical.yaml` L18 的 `currency` 字段必须填对，不能靠猜。

### 6. 是否返回 source / provider —— 部分通过

数据提供方是**固定且可辨识**的：服务地址 `https://dgzt.guosen.com.cn/skills`（`SKILL.md` L12；`get_data.py` L22），另带固定标识 `softName=agent_skills`（`get_data.py` L23）。所以「是谁供的数」是清楚的。

**但它是写死在代码里的常量，不是返回数据里的字段。** 适配器需要自己把 provider 名硬编码进 schema。此外本项目 `data-standard.md` §4.1（L128-137）要求给来源定可信度等级，国信属于数据终端，按 `data-collector.md` L42 应记 **B 级**——这一层也要适配器自己补。

### 7. 是否保留 retrieved_at —— 不通过

`get_data.py` 的 `main()`（L274-333）流程是：解析参数 → 调对应查询函数 → `print(json.dumps(result, ...))`（L329）。**全程不记录当前时间，不落盘，不留抓取时点。** 定时/缓存/重放所需的 `retrieved_at` 完全缺失。

本项目 `data-standard.md` §1.2（L49）要求原始材料写「采集日期」，即实际抓取那天，与发布时间分开。源技能没有这个能力，适配器必须自己打时间戳。

### 8. 是否能处理停牌、休市、非交易日 —— 部分通过

`SKILL.md` L37-40「行情数据时效性说明」给了三条行为描述：

- 实时行情：非交易时段返回上一交易日收盘价（L38）；
- 历史行情：数据截止至最近已收盘的交易日（L39）；
- 北向/南向资金：收盘后约 30 分钟更新（L40）。

也就是说**休市有隐式回退**（自动落到上一交易日），但：

- **没有显式标记**。调用方拿到的还是一个「价格」，无法从数据本身判断这是当天收盘还是回退价，`actual_trade_date` 也无从读出（回到第 2 条）。
- **停牌完全不涉及**。个股停牌当日无成交，包内没有任何停牌识别或失败语义。
- **非交易日的「明确失败」也不存在**。空数据怎么表现，本包未写；从兄弟技能 `gs-smart-stock-picking\SKILL.md` L123-133 可推知国信网关的失败形态是 `code=-1`、`msg="查询失败:no data."`、`data=null`，但**本技能包并未据此做任何处理**，`_make_request`（`get_data.py` L78-101）只管把 JSON 原样返回。

**卡在哪**：休市有隐式回退但不可观测；停牌、空数据没有明确失败路径。本项目要的是「回退要写明实际交易日，取不到要明确失败」（`data-standard.md` L103；`data-collector.md` L42），源技能两者都给不了。

### 9. 是否支持 300308.SZ 与 3308.HK —— 通过

市场映射齐备：深圳 `setCode=0`、港股 `setCode=-1`（`SKILL.md` L289-293；`get_data.py` L104-110）。实时接口 `querySingleHQ` 的 `target` 参数取 3 表示港股美股（`SKILL.md` L84；`get_data.py` L122-143），示例里也直接给了「查询腾讯控股（港股）现在的最新价」（`SKILL.md` L46）。历史接口 `query_past_hq` 的 `set_code` 文档同样列了 `-1-港股`（`get_data.py` L250）。两个市场都覆盖。

**两点需注意**（不改变「通过」判定，但适配器要处理）：

- 代码格式不同。本项目用 `300308.SZ` / `3308.HK`，源技能收的是不带后缀的裸代码（`300308` / `03308`）+ 单独的 `setCode`。需要一层后缀映射。
- 3308.HK 在源技能里是港股，走 `setCode=-1` + `target=3`，与 A 股调用方式不同，须分别测试。

### 10. 是否依赖账号、Cookie、API key 或不可迁移许可证 —— 不通过

**这一项细看。**

- **凭据种类**：单一的 `GS_API_KEY`，由国信证券接口服务签发（`SKILL.md` L15-18、L296-299；`get_data.py` L17）。
- **读取位置**：环境变量 `GS_API_KEY`（`get_data.py` L17）。技能约定由智能体先从**项目根的 `./memory.md`** 读出该字段，再设成环境变量喂给脚本（`SKILL.md` L193、L204-212）。
- **传递方式**：作为 URL 查询参数 `apiKey=` 明文拼进请求（`get_data.py` L140，实时；L164、L188、L214、L238、L265 各处同理）。
- **获取门槛**：需到 `https://www.guosen.com.cn/gs/xxskills/index.html` **注册 / 登录账号**后，从账号弹窗一键复制（`SKILL.md` L196-201）。
- **迁移后别人能不能用**：**不能。** 这是**绑定个人国信账号**的密钥，属于不可迁移许可——本项目要独立使用，必须由本项目自己注册国信账号、自行申领一把 key。别人手里的 key 不能共享，也不该硬编码进本项目任何文件。`SKILL.md` L308、L313 也自述「禁止硬编码账号 ID 或 token」。
- **硬编码凭据检查**：**未发现**任何硬编码的 key / token 值。`get_data.py` 全文只从环境变量取 key（L17），测试用假 key（`test_get_data.py` L8）。
  - 需要单列一条：兄弟技能 `gs-etf-filter\SKILL.md`（L93、L111、L148）里出现的是一个**环境变量名** `COZE_GUOSEN_API_KEY_7627056463827140634`，被写死不可更改。**那是变量名，不是密钥值**，不构成凭据泄露；但它说明这套技能的鉴权约定是「按技能固定的环境变量名」。迁移时不要照抄这个命名。
- **附带的安全隐患**（迁不迁都要知道）：
  - `get_data.py` L27-53 `_create_ssl_context()` 主动**关闭证书校验**（`check_hostname=False`、`verify_mode=CERT_NONE`），并为兼容旧服务器降到 `SECLEVEL=0`；
  - key 走 URL 查询串，易被日志、代理、Referer 记录；
  - 脚本 `try/except Exception` 兜底到本地 `curl -k`（L56-75、L93-101），同样跳过证书校验。

**卡在哪**：整条链路依赖一把**账号绑定、不可转让**的国信密钥，且以不安全方式传输与校验。这与本项目「密钥只从环境变量或 `memory.md` 取、不入库、不明文出现」的红线（仓库根 `CLAUDE.md`「红线」节）兼容度低；迁移等于把本项目的行情取数绑死在一个外部账号体系上。

### 11. 是否有缓存和原始响应留存 —— 部分通过

- **缓存**：无。写操作只有 `print`（`get_data.py` L329），没有写文件、没有本地缓存层。
- **原始响应留存**：几乎没有。唯一的留存点在 `_curl_request` 里——当 curl 拿到内容但 JSON 解析失败时，返回 `{"error": "Invalid JSON response", "raw": result.stdout[:500]}`（`get_data.py` L71）。**只在出错时留，且硬截断到 500 字符。** 正常返回的完整原始报文一律不落盘。

本项目要「留痕归档」（`data-standard.md` §1.2 来源块要求能顺着找回去），源技能提供不了可追溯的原始报文。适配器必须自己把原始 JSON 写进 `raw_data/`。

### 12. 是否有稳定的异常处理（超时、限流、空数据）—— 部分通过

**已有的**：

- 超时 15 秒（`get_data.py` L24）。
- 请求失败回退到本地 `curl`（L93-101），curl 侧超时 30 秒（L63）。
- 失败时返回 `{"error": ...}` 字典而不抛异常（L71-75）。
- 缺 key 时给出明确报错：`RuntimeError("缺少必要的凭证配置，请检查环境变量 GS_API_KEY")`（L19-20）。

**缺的**：

- **无重试**，无退避。
- **无限流识别**。HTTP 429 / 频控消息不会单独处理，直接进 `except` 走 curl 兜底。
- **空数据无识别**。`data=null` 或 `code=-1` 会当作一次「成功返回」原样打印，脚本层面判断不出「没取到数」。
- **异常吞噬过宽**。`except Exception`（L99、L36、L74）把包括作者自己的 bug 在内的所有异常都导向 curl 兜底或静默忽略，掩盖真实故障。
- **SSL 语境下的兜底本身不可靠**。`_curl_request` 依赖本机有 `curl`；本机（Windows）环境未必具备，兜底路径可能根本走不通。

---

## 四、不迁移范围（明确点名）

以下内容**不进入**本项目，与行情数据本身无关：券商研报提示词、触发语、角色定义、人格设定、写死的合规话术与风险提示文案。

具体在本包及其兄弟技能里，这些属于「不迁移」：

| 内容 | 位置 | 为什么不迁 |
| --- | --- | --- |
| 技能触发描述（`description:` 里「Invoke when user asks ...」） | `SKILL.md` L3 | 提示词脚手架，本项目有自己的 agent / skill 体系 |
| 强制输出的风险提示文案 | `gs-smart-stock-picking\SKILL.md` L354-355 | 合规话术，非数据能力 |
| 「请牢记！」这类语气指令与输出格式强制 | 同上 L365、`gs-etf-filter\SKILL.md` L154-167 | 人格 / 输出风格设定 |
| API Key 自动写入 `./memory.md` 的流程 | `SKILL.md` L202-212；`gs-etf-filter\SKILL.md` L82-107 | 密钥落盘流程，与本项目密钥红线冲突，且本项目密钥从仓库根 `memory.md` 取 |
| 全包自带的「返回数据仅供参考，不作为投资建议」 | `SKILL.md` L310、L316 | 免责话术 |
| 兄弟技能整包（财务、选股、经济、ETF、基金对比） | 同目录其余目录 | 本次审计只需行情；其余不在迁移范围 |

**可考虑复用的仅限**：`get_data.py` 里那两个 HTTP 传输辅助函数（`_make_request` L78-101 / `_curl_request` L56-75，**但必须补回证书校验**）与 `SET_CODE_MAP`（L104-110）这份市场代码表。其余为不可迁移。

---

## 五、建议的行情输入 schema

无论最终是否迁移，本项目行情输入都应是下面这个形状。字段名与 `model\inputs\historical.yaml` 的 `meta` 块（L15-27）对齐，并覆盖 `data-standard.md` §2.3（L90-105）的「四个日期」纪律。

```yaml
market_quote:
  ticker: "300308.SZ"           # 本项目统一带后缀；adapter 负责拆成裸代码 + setCode
  exchange: "SZ"                # SZ / SH / HK / US
  requested_date: "2026-09-18"  # 请求的是哪一天，原样记下
  actual_trade_date: "2026-09-17" # 实际取到行情的交易日，可能 ≠ requested_date
  price_type: "close"           # close / open / high / low / vwap / realtime
  adjustment: "none"            # none / forward / backward，本目录估值只用 none
  close: 896.00                 # 未复权收盘价，单位见 currency
  currency: "CNY"               # CNY / HKD，不靠 exchange 猜
  source: "国信证券 / gs-stock-market-query"  # provider，含技能名
  source_grade: "B"             # 按 data-standard.md §4.1 定级
  retrieved_at: "2026-09-20T14:31+08:00"      # 抓取时点，含时区
  raw_record_path: "raw_data/market/raw/300308.SZ-2026-09-17.json"  # 原始报文落盘位置
  status: "fallback"            # 见下
```

### `status` 应当能表达什么

`status` 是**机器可读**的状态位，用于把「取到了好数据」和「退而求其次」分开，**绝不允许把后几种静默当成正常价**：

| 取值 | 含义 | 能否进 `meta.latest_price` |
| --- | --- | --- |
| `ok` | 请求日即交易日，取到该日收盘 | 可以 |
| `fallback` | 请求日休市 / 非交易日，回退到此前最近交易日（`actual_trade_date` < `requested_date`） | 可以，但**必须带提示**并在报告里写明实际交易日 |
| `suspended` | 标的当日停牌、无成交 | 否，明确失败 |
| `no_data` | 接口返回空（`code=-1` / `data=null`） | 否，明确失败 |
| `unavailable` | 接口不可达 / 超时 / 限流，未取得数据 | 否，明确失败 |

规则：`status != ok` 时，`actual_trade_date` 与 `requested_date` 不一致这一事实必须一路透传到成品报告，写法照 `data-standard.md` L103 的 `as of 2026-09-18（实际交易日 2026-09-17）`。**只有 `actual_trade_date` 真正等于或早于截止日、且早于提交时刻的已收盘交易日，才允许作为正式价格。**

### 同时要守住的两条口径纪律（本项目既有约束）

1. **前复权价不得进现价。** `adjustment` 必须是 `none` 才允许写进 `meta.latest_price`；`forward` / `backward` 只能用于收益率类区间统计，且要在文件里点明。
2. **缺失不得默认为零。** 对应 `model\README.md` L67 与 `engine.py` 的 `req_*` 取值纪律（`engine.py` L52-72）：取不到数就报错，不许填 0 或填个「看起来对」的数。

---

## 六、任何适配器合并前必须存在的测试用例

以下六条为**必测**，缺一条不得合并：

| # | 用例 | 期望 |
| --- | --- | --- |
| 1 | **300308.SZ 指定交易日**（如 2026-09-17） | `status=ok`，`close` 为当日未复权收盘价，`currency=CNY`，`actual_trade_date=requested_date` |
| 2 | **3308.HK 指定交易日** | 走 `setCode=-1` + `target=3`，`currency=HKD`，代码后缀正确映射为裸代码 |
| 3 | **非交易日回退**（请求一个休市日，如周末） | `status=fallback`，`actual_trade_date` < `requested_date`，且**返回提示**说明发生了回退 |
| 4 | **无数据时明确失败** | 接口返回 `data=null` / `code=-1` 时，`status=no_data` 并**报错**，绝不产出一个看似正常的价 |
| 5 | **禁止前复权价格进入 current price** | 传入/接口返回前复权价时，不得写入 `price_type=close`+`adjustment=none`；应被拒绝或降级为区间统计专用 |
| 6 | **`requested_date` 与 `actual_trade_date` 不一致时给出提示** | 两者不等即触发提示，并原样保留两个字段，不得偷偷把 `actual_trade_date` 改成 `requested_date` |

建议追加（非阻塞，但对应本包已暴露的缺陷）：

- **凭据缺失**：未设密钥时给出可读报错，且**不打印密钥值**（源包 `get_data.py` L19-20 只报变量名，这点可以照做）。
- **原始报文留存**：每次成功调用都把完整响应写入 `raw_record_path`，可复核。
- **超时 / 限流**：15 秒超时与 429 时返回 `status=unavailable`，不静默。
- **schema 校验**：字段缺失（如缺 `currency`）时拒绝入库，呼应 `engine.py` 的 `req_*` 纪律。

---

## 七、最终结论

**不迁移。**

**卡住的关键项**：

- **第 1 项（指定历史交易日）部分通过**：源技能只有「近 n 个交易日」参数（`SKILL.md` L162-169；`get_data.py` L244-271），没有日期参数，无法点名某一天。本项目首轮需锁定 2026-09-18 之前的最后一个已收盘交易日，这条是刚需。
- **第 2 项（`actual_trade_date`）不通过**：全包无此字段，返回结构未文档化（`SKILL.md` L269-281），且明确说明是「隐式回退」（L38）。
- **第 3 项（`unadjusted_close`）不通过**：无复权概念，无法确认返回价的口径。
- **第 4 项（`adjustment=none`）不通过**：完全没有复权字段。

**叠加的两道非关键但棘手的坎**：第 10 项需绑定一把不可迁移的国信账号密钥（`SKILL.md` L196-201；`get_data.py` L17、L140），且传输层关闭证书校验（`get_data.py` L27-53）；第 11、12 项在留存与空数据/停牌处理上都不达标。

**可复用的部分极薄**：只有 HTTP 传输辅助（需补回证书校验）与市场代码映射表（`get_data.py` L78-110）。行情取值本身——指定交易日、实际交易日回退、未复权口径、币种、抓取时点、原始报文留存、明确失败——**全部需要本项目自建**，不能靠这个技能包补齐。建议转向本项目已在用的路径（`raw_data\market\中际旭创-行情数据.md` 所记的新浪财经 `stock_zh_a_daily`，`adjust=""` 未复权），按本报告第五节 schema 与第六节用例自建一层薄的行情适配。

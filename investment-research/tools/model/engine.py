"""统一估值模型的计算内核。

九个模块（valuation 技能 §4.1）：

  1. 收入驱动     销量 × ASP
  2. 利润表       毛利与期间费用
  3. 营运资本     DIO / DSO / DPO
  4. 资本开支与折旧
  5. 债务与现金
  6. 股本
  7. FCFE         主估值
  8. FCFF         一致性核验（含 WACC 与债务现金桥）
  9. 远期可比     交叉检验

外加：三情景（基准 / 乐观 / 悲观）、两组敏感性（Ke × g、毛利率 × DIO）、
两个预留项（反向估值求根、券商预测差异归因）。

口径约定，全模型统一：
- 金额单位 **亿元**，股本单位 **亿股**，每股价值单位 **元**
- 利润与现金流一律**归母口径**；`net_income_attributable` 是归母净利润
- 债务是**有息债务**，不是全部负债；现金单列，在 EV → 股权价值的桥里处理
"""

from __future__ import annotations

import calendar
import copy
import re
from datetime import date as _date

from . import schema
from .errors import MissingInputError, AssumptionNotApprovedError, BridgeError, SchemaError

DAYS = 365

# 勾稽容差。股数以亿股计，1 股 = 1e-8 亿股；来源里的整数换成亿股是精确的，
# 留 1e-6（约 100 股）只为了吸收书写舍入，不是给「差一点也算过」开口子。
TOL = 1e-6

# 允许出现在假设文件顶层的状态值
APPROVED = "approved"
CANDIDATE = "candidate"
DEPRECATED = "deprecated"
SUPERSEDED = "superseded"

# 四个日期字段，一个都不能少、不能合并
DATE_FIELDS = ("info_cutoff", "price_date", "valuation_date", "target_date")

# 目标期限。统一 12 个月，见 output-format.md §1.2
HORIZON_MONTHS = 12

# 模型算得下去的最低要求。缺一个就报错 —— 缺失数据不得默认为零。
# `operating_cash_flow` 在这里是因为 FCFE 要走两条路，CFO 路径少不了它。
REQUIRED_PERIOD_FIELDS = (
    "revenue", "cogs", "operating_expenses",
    "depreciation_amortization", "capex",
    "inventory", "accounts_receivable", "accounts_payable",
    "interest_bearing_debt", "cash", "interest_expense",
    "net_income_attributable", "shares_outstanding",
    "operating_cash_flow",
)

# 三表勾稽用的字段。缺了不阻塞模型，但对应检查记为「未检索」，不按 0 算。
# `ebit` 与 `net_income` 在这里是因为勾稽检查要拿它们跟算式的结果比 ——
# 不列进来，缺了就会**悄悄跳过**检查，而不是报出来。
ARTICULATION_PERIOD_FIELDS = (
    "ebit", "net_income",
    "ppe_net", "total_assets", "total_liabilities", "equity_attributable",
    "income_tax", "prepayments", "ebitda", "minority_interest",
    "taxes_and_surcharges", "selling_expenses", "admin_expenses", "rnd_expenses",
)

# 四种股数口径。同一个「股本」在四个地方含义不同，混用必然出错。
SHARE_CALIBERS = ("basic_shares", "issued_shares", "potential_awards", "projected_diluted_shares")


# --------------------------------------------------------------------------
# 取值：所有数字都必须经过这里，缺失就报错，绝不返回 0
# --------------------------------------------------------------------------

def req(mapping, key, where):
    """取一个必须存在的值。缺失或为 None → MissingInputError。"""
    if mapping is None:
        raise MissingInputError(where, key, "整块不存在")
    if key not in mapping or mapping[key] is None:
        raise MissingInputError(where, key)
    return mapping[key]


def req_num(mapping, key, where):
    """取一个必须是数字的值。字符串占比写成 '15%' 也接受。"""
    value = req(mapping, key, where)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            value = float(text[:-1]) / 100.0
        else:
            value = float(text)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MissingInputError(where, key, f"取值 {value!r} 不是数字")
    return float(value)


def req_list(mapping, key, where, length=None, what="假设"):
    """取一个必须是数字列表的值，可校验长度。"""
    values = req(mapping, key, where)
    if not isinstance(values, (list, tuple)):
        raise MissingInputError(where, key, "应为列表")
    result = []
    for index, item in enumerate(values):
        if item is None:
            raise MissingInputError(where, f"{key}[{index}]", f"{what}第 {index + 1} 年留空")
        if isinstance(item, str):
            item = float(item[:-1]) / 100.0 if item.strip().endswith("%") else float(item)
        result.append(float(item))
    if length is not None and len(result) != length:
        raise MissingInputError(where, key, f"应有 {length} 期，实际 {len(result)} 期")
    return result


def req_list_raw(mapping, key, where):
    """取一个必须存在的列表，**不转数字** —— 元素是 dict（股本桥的各笔、激励计划）。"""
    values = req(mapping, key, where)
    if not isinstance(values, (list, tuple)) or not values:
        raise MissingInputError(where, key, "应为非空列表")
    return list(values)


def optional_num(mapping, key, default=None):
    """取一个可以没有的值。**仅用于真正可选项**，不用于业务输入。"""
    if not mapping or mapping.get(key) is None:
        return default
    value = mapping[key]
    if isinstance(value, str):
        value = value.strip()
        if value.endswith("%"):
            return float(value[:-1]) / 100.0
        return float(value)
    return float(value)


# --------------------------------------------------------------------------
# 载入与校验
# --------------------------------------------------------------------------

def _add_months(iso_date, months):
    """在 YYYY-MM-DD 上加若干自然月，日不存在时退到当月最后一天。"""
    year, month, day = (int(part) for part in iso_date.split("-"))
    total = (year * 12 + month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(day, calendar.monthrange(year, month)[1])
    return _date(year, month, day).isoformat()


def _norm_date(value, where):
    """把日期统一成 YYYY-MM-DD 字符串。

    YAML 里没加引号的 `2026-06-18` 会被 PyYAML 解析成 datetime.date；
    带引号的则是字符串。两种写法都得能用，所以在这里归一。
    """
    if value is None or isinstance(value, bool):
        raise MissingInputError(where, "日期", f"取值 {value!r} 不是日期")
    text = value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        # 有值但格式不对，不是「缺失」—— 报 MissingInputError 会让人去补一个已经填过的字段。
        raise SchemaError(
            f"{where} 的日期 `{text}` 不是 YYYY-MM-DD 格式。"
            "四个日期都要能定位到具体一天，模糊写法会让期限与口径都没法核。"
        )
    return text


def _fiscal_calendar(actual, periods):
    """从历史报告期里读出会计年历：上一个完整财年、财年结束月份。

    这是**数据事实**，不是假设 —— 所以从报告期推导，不问假设文件要。
    放进 assumptions 里会变成一条需要团队确认的「假设」，而它根本没有可争的地方；
    放进假设文件还多一个和数据对不上的机会。

    只认 12 个月的完整期：半年报的期末是 6 月 30 日，拿它当财年末会错。
    """
    annual = []
    for period in periods:
        row = actual[period]
        start, end = row.get("period_start"), row.get("period_end")
        if start is None or end is None:
            continue
        start, end = _norm_date(start, f"actual.{period}.period_start"), \
            _norm_date(end, f"actual.{period}.period_end")
        if _months_between(start, end) == 12:
            annual.append(end)

    if not annual:
        return {"base_year": None, "year_end_month": None,
                "reason": "历史期里没有 12 个月的完整年度，无法确定财年结束日"}
    last = max(annual)
    year, month = (int(part) for part in last.split("-")[:2])
    return {"base_year": year, "year_end_month": month,
            "basis": f"取最近一个完整财年 {last}"}


def load_inputs(raw, register=None, mode="formal"):
    """校验历史输入，返回规范化后的 dict。

    `register` 是 `schema.load_source_register()` 的结果。传了它就做来源引用完整性检查
    （引用了没登记的 id 直接报错）；不传则只要求每个报告期填了 `source_id`，跳过查表。
    正式运行必须传 —— 见 `run_model.py validate`。
    """
    meta = raw.get("meta") or {}
    actual = raw.get("actual") or {}
    if not actual:
        raise MissingInputError("historical.yaml", "actual", "一个报告期都没有")

    # 报告期的键在 YAML 里可能是裸年份（`2023:` → int）或裸日期（→ date），
    # 统一成字符串，免得后面排序、写 JSON、跟 meta 对不上
    actual = {
        (key.strftime("%Y-%m-%d") if hasattr(key, "strftime") else str(key)): row
        for key, row in actual.items()
    }
    periods = sorted(actual.keys())

    meta_out = {
        "company": req(meta, "company", "meta"),
        "ticker": req(meta, "ticker", "meta"),
        "unit": req(meta, "unit", "meta"),
        "currency": req(meta, "currency", "meta"),
        "source": req(meta, "source", "meta"),
        "periods": periods,
        "latest_price": req_num(meta, "latest_price", "meta"),
    }
    for field in DATE_FIELDS:
        meta_out[field] = _norm_date(req(meta, field, "meta"), f"meta.{field}")

    # 行情块：提供了就校验口径 —— 未复权收盘价、实际交易日、失败状态不留正数价。
    # 还要核对它与 `latest_price` 说的是同一个价：两个字段都自称现价却对不上，
    # 报告里就会出现两个市价，而「预期回报」算的是哪一个没人说得清。
    quote = meta.get("market_quote")
    if quote is not None:
        try:
            parsed_quote = schema.MarketQuote(**quote)
        except Exception as error:  # noqa: BLE001
            raise SchemaError(
                "meta.market_quote 不合格：" + " ".join(str(error).split())[:400]
            ) from error
        if parsed_quote.currency != meta_out["currency"]:
            raise SchemaError(
                f"meta.market_quote 的币种是 `{parsed_quote.currency}`，"
                f"输入口径是 `{meta_out['currency']}`。现价与财报必须同币种，"
                "否则每股价值和市价不是一把尺子量出来的。"
            )
        if parsed_quote.status in ("suspended", "no_data", "unavailable"):
            raise SchemaError(
                f"meta.market_quote 状态是 `{parsed_quote.status}` —— 该交易日没有可用收盘价。"
                "估值要拿现价做对照，没有现价就不该出数。补齐行情再跑。"
            )
        if abs(parsed_quote.close - meta_out["latest_price"]) > TOL:
            raise SchemaError(
                f"meta.market_quote.close 是 {parsed_quote.close}，"
                f"meta.latest_price 是 {meta_out['latest_price']} —— "
                "两个字段都代表现价，取值必须一致。对不上说明其中一个没跟着改。"
            )
        meta_out["market_quote"] = parsed_quote.model_dump()
        meta_out["price_note"] = parsed_quote.price_note()

    # 目标期限的起算点是**估值基准日**，不是行情日期。
    # 两者通常同一天，但逻辑上分开：行情日期是「现价取哪一天的收盘」，
    # 估值基准日是「这套假设站在哪一天」。目标价 12 个月后的价值锚在前者会错位。
    expected_target = _add_months(meta_out["valuation_date"], HORIZON_MONTHS)
    if meta_out["target_date"] != expected_target:
        raise MissingInputError(
            "meta.target_date", "target_date",
            f"目标日期是 {meta_out['target_date']}，但估值基准日 {meta_out['valuation_date']} "
            f"加 {HORIZON_MONTHS} 个月应为 {expected_target}。目标期限统一 12 个月，"
            "期限不同目标价就不可比。",
        )

    # 三表的元信息走 schema 校验（最小字段集 + source_id 引用完整性）
    for period in periods:
        schema.validate_period(period, actual[period], register, mode)

    # 算得下去的最低要求 —— 缺一个就报错，不静默按 0
    for period in periods:
        row = actual[period]
        for key in REQUIRED_PERIOD_FIELDS:
            req_num(row, key, f"actual.{period}")

    # 三表勾稽用的字段。缺了不阻塞模型，但对应的检查记为「未检索」并写进结果。
    articulation_gaps = []
    for period in periods:
        row = actual[period]
        for key in ARTICULATION_PERIOD_FIELDS:
            if row.get(key) is None:
                articulation_gaps.append({
                    "period": period,
                    "field": key,
                    "status": "未检索" if register is None else "未披露/未检索",
                    "reason": f"{period} 的 `{key}` 在 historical.yaml 里没有取值，"
                              "对应的勾稽检查跳过，不按 0 参与计算",
                })

    # H 股募集资金现金桥的起点是「最近报告期的货币资金」。
    # 这个数只能来自最新一个报告期，不能由调用方随手给 —— 给错了桥就假装闭合。
    capital = load_capital_structure(
        raw.get("capital_structure"), register, mode,
        latest_cash=actual[periods[-1]]["cash"],
    )

    return {
        "meta": meta_out,
        "actual": actual,
        "periods": periods,
        "fiscal": _fiscal_calendar(actual, periods),
        "capital": capital,
        "articulation_gaps": articulation_gaps,
    }


# --------------------------------------------------------------------------
# 资本结构：股本桥、限制性股票、H 股募集资金现金桥
# --------------------------------------------------------------------------

def _bridge_leg(block, where, register):
    """股本桥的一段：一个标签 + 一个股数 + 一个来源。"""
    shares = req_num(block, "shares", where)
    source_id = req(block, "source_id", where)
    if register is not None:
        schema.check_source_ref(register, source_id, where)
    return {
        "label": req(block, "label", where),
        "shares": shares,
        "source_id": source_id,
    }


def _load_share_bridge(block, where, register):
    """股本桥：期初 + 各笔变动 = 期末。**左右不等就报错**，不许带病往下算。"""
    opening = _bridge_leg(req(block, "opening", where), f"{where}.opening", register)
    closing = _bridge_leg(req(block, "closing", where), f"{where}.closing", register)
    items = [
        _bridge_leg(item, f"{where}.items[{index}]", register)
        for index, item in enumerate(req_list_raw(block, "items", where))
    ]

    total = opening["shares"] + sum(item["shares"] for item in items)
    if abs(total - closing["shares"]) > TOL:
        raise BridgeError(
            "股本桥（期初 + 各笔变动 = 期末）",
            total, closing["shares"],
            "差数说明有一笔股本变动漏记或重复计入。"
            f"期初 {opening['shares']:.8f}，各笔合计 {sum(i['shares'] for i in items):.8f}，"
            f"期末 {closing['shares']:.8f}（单位亿股）",
        )
    return {"opening": opening, "items": items, "closing": closing, "balanced": True}


def _load_restricted_stock(block, where, register):
    """限制性股票归属计划。

    两个勾稽都要过：
      单期：授予 = 已归属 + 已作废 + 未归属
      合计：各计划未归属之和 = 总未归属
    第二道是防重复计入 —— 同一批股票出现在两个计划里，会凭空多出潜在的稀释。
    """
    if block is None:
        return {"plans": [], "total_unvested": 0.0, "reconciled": True,
                "note": "未提供限制性股票计划，潜在奖励按 0 计"}

    plans = []
    for index, raw_plan in enumerate(req_list_raw(block, "plans", where)):
        at = f"{where}.plans[{index}]"
        granted = req_num(raw_plan, "granted", at)
        vested = req_num(raw_plan, "vested", at)
        cancelled = req_num(raw_plan, "cancelled", at)
        unvested = req_num(raw_plan, "unvested", at)
        source_id = req(raw_plan, "source_id", at)
        if register is not None:
            schema.check_source_ref(register, source_id, at)

        if abs(granted - (vested + cancelled + unvested)) > TOL:
            raise BridgeError(
                f"限制性股票 {raw_plan.get('name', index)} 的授予数拆分",
                granted, vested + cancelled + unvested,
                "授予 = 已归属 + 已作废 + 未归属，三者对不上说明数字有重复或遗漏",
            )
        plans.append({
            "name": req(raw_plan, "name", at),
            "granted": granted, "vested": vested,
            "cancelled": cancelled, "unvested": unvested,
            "source_id": source_id,
        })

    total_unvested = req_num(block, "total_unvested", where)
    summed = sum(plan["unvested"] for plan in plans)
    if abs(summed - total_unvested) > TOL:
        raise BridgeError(
            "各计划未归属合计 = 总未归属",
            summed, total_unvested,
            "对不上说明同一批股票被计入了两个计划，潜在奖励会凭空翻倍",
        )
    return {"plans": plans, "total_unvested": total_unvested, "reconciled": True}


def _load_h_share_proceeds(block, where, register, latest_cash):
    """H 股募集资金现金桥。

    `最近报表日现金 + 最终净募集资金 − 已知募集资金使用 = 估值日 pro forma 现金`

    **最终净募集资金缺可靠公告时，不许拿发行总额代替。** 发行总额扣掉承销费、
    发行费用之后才是能进公司账上的钱，两者差额可观；用总额顶替会把现金算多，
    进而把估值抬高。缺就是缺 —— 状态标 `未完成`，桥不闭合，写清缺哪份材料。
    """
    if block is None:
        return {"status": "未检索", "reason": "未提供 H 股募集资金材料", "balanced": False}

    gross = req_num(block, "gross_proceeds", where)
    net = block.get("net_proceeds")
    uses = req_list_raw(block, "uses", where) if block.get("uses") else []
    source_id = req(block, "source_id", where)
    if register is not None:
        schema.check_source_ref(register, source_id, where)

    use_total = 0.0
    for index, use in enumerate(uses):
        use_total += req_num(use, "amount", f"{where}.uses[{index}]")

    if net is None:
        return {
            "status": "未完成",
            "reason": "最终净募集资金缺少可靠公告。**不得拿发行总额代替** —— "
                      "发行总额未扣承销费与发行费用，用它会把 pro forma 现金算多。",
            "gross_proceeds": gross,
            "net_proceeds": None,
            "uses": uses,
            "use_total": use_total,
            "reported_cash": latest_cash,
            "proforma_cash": None,
            "balanced": False,
            "source_id": source_id,
        }

    proforma = latest_cash + net - use_total
    return {
        "status": "完成",
        "gross_proceeds": gross,
        "net_proceeds": net,
        "implicit_fees": gross - net,
        "uses": uses,
        "use_total": use_total,
        "reported_cash": latest_cash,
        "proforma_cash": proforma,
        "balanced": True,
        "source_id": source_id,
    }


def load_capital_structure(raw, register, mode, latest_cash):
    """股本桥、限制性股票、H 股募集资金现金桥，以及四种股数口径。"""
    if raw is None:
        return {"status": "未检索", "reason": "historical.yaml 里没有 capital_structure 块"}

    where = "capital_structure"
    as_of = _norm_date(req(raw, "as_of", where), f"{where}.as_of")

    share_bridge = _load_share_bridge(req(raw, "share_bridge", where),
                                      f"{where}.share_bridge", register)
    restricted = _load_restricted_stock(raw.get("restricted_stock"),
                                        f"{where}.restricted_stock", register)
    proceeds = _load_h_share_proceeds(raw.get("h_share_proceeds"),
                                      f"{where}.h_share_proceeds", register, latest_cash)

    # 四种口径。同一个「股本」在四个地方含义不同，混用必然出错。
    bridge_items = share_bridge["items"]
    h_shares = sum(item["shares"] for item in bridge_items if "H 股" in item["label"])
    issued = share_bridge["closing"]["shares"]
    potential = restricted["total_unvested"]
    declared = raw.get("calibers") or {}

    calibers = {
        "basic_shares": {
            "value": optional_num(declared, "basic_shares")
            or share_bridge["opening"]["shares"],
            "basis": "基本股本（加权平均口径；未提供时退到股本桥期初）",
        },
        "issued_shares": {
            "value": issued,
            "basis": f"已发行股本（{as_of} 期末，含 A 股与 H 股）",
        },
        "potential_awards": {
            "value": potential,
            "basis": "潜在奖励 —— 已授予未归属的限制性股票，尚未成为实收股本",
        },
        "projected_diluted_shares": {
            "value": issued + potential,
            "basis": "预测稀释股本 = 已发行 + 潜在奖励（未归属部分全部归属的上限口径）",
        },
    }
    # `issued_shares` 是股本桥期末，必须与最新报告期的 shares_outstanding 分得清：
    # 前者是 2026-08-31 的时点数，后者是半年报期末的时点数，两者相差 H 股与后续归属。
    calibers["h_shares"] = {"value": h_shares, "basis": "股本桥里标注为 H 股的各笔之和"}
    calibers["restricted_reconciled"] = restricted["reconciled"]

    return {
        "status": "完成",
        "as_of": as_of,
        "share_bridge": share_bridge,
        "restricted_stock": restricted,
        "h_share_proceeds": proceeds,
        "calibers": calibers,
        "source_id": req(raw, "source_id", where),
    }


def load_assumptions(raw, mode="formal", register=None):
    """校验假设文件，并执行审批门禁。

    mode='formal'  —— 出正式结果。要求 `status: approved` 且确认人、确认日期、版本都齐。
    mode='test'    —— 合成数据测试。只要求结构完整，不要求审批。
    """
    status = raw.get("status")
    if status not in (APPROVED, CANDIDATE, DEPRECATED, SUPERSEDED):
        raise MissingInputError("assumptions", "status", f"取值 {status!r} 不在允许范围内")

    if mode == "formal":
        if status != APPROVED:
            raise AssumptionNotApprovedError(
                f"假设文件状态是 `{status}`，不是 `{APPROVED}`。"
                "审批前只能用合成数据跑测试（--mode test）；"
                "未经确认的预测假设不得用于输出正式估值、评级与目标价。"
            )
        for field in ("confirmed_by", "confirmed_on", "version"):
            if not raw.get(field):
                raise MissingInputError(
                    "assumptions", field,
                    "确认记录必须由分析师填写，AI 不代签、不预填",
                )
    else:
        if not raw.get("version"):
            raise MissingInputError("assumptions", "version")

    forecast = raw.get("forecast") or {}
    years = int(req(forecast, "years", "forecast"))
    discount = raw.get("discount") or {}
    terminal = raw.get("terminal") or {}
    comparables = raw.get("comparables") or {}

    assumptions = {
        "status": status,
        "version": raw.get("version"),
        "confirmed_by": raw.get("confirmed_by"),
        "confirmed_on": raw.get("confirmed_on"),
        "forecast": {
            "years": years,
            "volume_growth": req_list(forecast, "volume_growth", "forecast", years, "销量增速"),
            "asp_growth": req_list(forecast, "asp_growth", "forecast", years, "ASP 增速"),
            "gross_margin": req_list(forecast, "gross_margin", "forecast", years, "毛利率"),
            "opex_ratio": req_list(forecast, "opex_ratio", "forecast", years, "期间费用率"),
            "dio_days": req_list(forecast, "dio_days", "forecast", years, "DIO"),
            "dso_days": req_list(forecast, "dso_days", "forecast", years, "DSO"),
            "dpo_days": req_list(forecast, "dpo_days", "forecast", years, "DPO"),
            "capex_ratio": req_list(forecast, "capex_ratio", "forecast", years, "资本开支率"),
            "depreciation": req_list(forecast, "depreciation", "forecast", years, "折旧摊销"),
            "net_borrowing": req_list(forecast, "net_borrowing", "forecast", years, "净借款"),
            "tax_rate": req_num(forecast, "tax_rate", "forecast"),
            "share_issuance": req_list(forecast, "share_issuance", "forecast", years, "股本变动"),
            # 三类之外的营运资本变动（预付、其他应收、合同负债等）。
            # 单独一条是为了让 FCFE 的两条路有各自的驱动 —— 塞进周转天数里两条路就恒等了。
            "other_working_capital_change": req_list(
                forecast, "other_working_capital_change", "forecast", years, "三类之外的营运资本变动"),
            # 非现金项（股份支付、减值、公允价值变动、递延所得税等）
            "non_cash_items": req_list(forecast, "non_cash_items", "forecast", years, "非现金项"),
            # 分红率 —— 目标价那一步要用：付出去的钱不再留在公司里
            "dividend_payout_ratio": req_list(forecast, "dividend_payout_ratio", "forecast", years, "分红率"),
        },
        "discount": {
            "ke": req_num(discount, "ke", "discount"),
            "wacc": req_num(discount, "wacc", "discount"),
            "kd": req_num(discount, "kd", "discount"),
            # 无风险利率是可选项：只在反向估值里用来拆「隐含股权风险溢价」。
            # 没登记就不拆 —— 不能自己编一个无风险利率去减。
            "risk_free": optional_num(discount, "risk_free"),
        },
        "terminal": {
            "growth": req_num(terminal, "growth", "terminal"),
            "reinvestment_rate": req_num(terminal, "reinvestment_rate", "terminal"),
        },
        "scenarios": raw.get("scenarios") or {},
        "comparables": {
            # 三层（直接同业 / 海外光通信 / 混合业务），每层给远期 P/E 与 EV/EBITDA
            "as_of": req(comparables, "as_of", "comparables"),
            "tiers": req(comparables, "tiers", "comparables"),
            "aggregate": req(comparables, "aggregate", "comparables"),
            "consensus_eps": optional_num(comparables, "consensus_eps"),
            "consensus_ebitda": optional_num(comparables, "consensus_ebitda"),
        },
        "discount_for_differences": optional_num(raw, "discount_for_differences"),
        "buy_threshold": optional_num(raw, "buy_threshold"),
        "reserved": raw.get("reserved") or {},
    }

    # Ke 必须大于终值增长率，否则戈登终值没有意义
    if assumptions["discount"]["ke"] <= assumptions["terminal"]["growth"]:
        raise MissingInputError(
            "assumptions", "discount.ke",
            f"Ke ({assumptions['discount']['ke']:.4f}) 必须大于终值增长率 "
            f"g ({assumptions['terminal']['growth']:.4f})",
        )
    # FCFF 走 WACC 折现，同理要求 WACC > g
    if assumptions["discount"]["wacc"] <= assumptions["terminal"]["growth"]:
        raise MissingInputError(
            "assumptions", "discount.wacc",
            f"WACC ({assumptions['discount']['wacc']:.4f}) 必须大于终值增长率 "
            f"g ({assumptions['terminal']['growth']:.4f})，否则 FCFF 的终值为负或无穷",
        )
    # 假设登记：每个假设都要说清凭什么取这个值，且登记的取值要与文件一致
    assumptions["register"] = schema.load_assumption_register(
        raw.get("assumptions_register"), raw, register, mode)
    return assumptions


# --------------------------------------------------------------------------
# 一 ~ 六：从历史值向前推
# --------------------------------------------------------------------------

def _months_between(start, end):
    """两个 YYYY-MM-DD 之间跨几个自然月（含首尾月）。"""
    y1, m1, _ = (int(part) for part in start.split("-"))
    y2, m2, _ = (int(part) for part in end.split("-"))
    return (y2 - y1) * 12 + (m2 - m1) + 1


def build_forecast(inputs, assumptions, override=None):
    """按年份推演利润表、营运资本、资本开支、债务与股本。

    `override` 是情景或敏感性叠加的一层偏置，形如
    `{"volume_growth_delta": -0.10, "gross_margin_delta": -0.03, "dio_days_delta": 20}`。

    **基期年化**：最新报告期可能是半年报（2026H1）。半年收入直接当年收入的起点，
    会把整个预测期低估一半。所以流量项按 `12 / 期间月数` 年化，存量项（存货、应收、
    现金、债务、股数）是时点数，**不年化**。
    """
    override = override or {}
    forecast = assumptions["forecast"]
    years = forecast["years"]
    periods = inputs["periods"]
    latest = inputs["actual"][periods[-1]]

    volume_growth = [v + override.get("volume_growth_delta", 0.0) for v in forecast["volume_growth"]]
    asp_growth = [v + override.get("asp_growth_delta", 0.0) for v in forecast["asp_growth"]]
    gross_margin = [v + override.get("gross_margin_delta", 0.0) for v in forecast["gross_margin"]]
    dio_days = [v + override.get("dio_days_delta", 0.0) for v in forecast["dio_days"]]
    dso_days = list(forecast["dso_days"])
    dpo_days = list(forecast["dpo_days"])

    # 基期年化：流量项按期间长度放大，存量项不放大
    months = _months_between(latest["period_start"], latest["period_end"])
    annualize = 12.0 / months
    base_revenue = float(latest["revenue"]) * annualize

    base_shares = float(latest["shares_outstanding"])
    debt = float(latest["interest_bearing_debt"])
    cash = float(latest["cash"])
    payout = forecast["dividend_payout_ratio"]
    tax_rate = forecast["tax_rate"]

    rows = []
    prev_revenue = base_revenue
    prev_nwc = (
        float(latest["inventory"])
        + float(latest["accounts_receivable"])
        - float(latest["accounts_payable"])
    )
    shares = base_shares

    for i in range(years):
        # 1. 收入驱动：销量 × ASP
        revenue = prev_revenue * (1 + volume_growth[i]) * (1 + asp_growth[i])

        # 2. 利润表
        cogs = revenue * (1 - gross_margin[i])
        gross_profit = revenue - cogs
        operating_expenses = revenue * forecast["opex_ratio"][i]
        ebit = gross_profit - operating_expenses

        # 3. 营运资本。三类（存货 / 应收 / 应付）按周转天数推，
        #    三类之外（预付、其他应收、合同负债等）单独给一条，不塞进天数里。
        inventory = cogs * dio_days[i] / DAYS
        accounts_receivable = revenue * dso_days[i] / DAYS
        accounts_payable = cogs * dpo_days[i] / DAYS
        nwc = inventory + accounts_receivable - accounts_payable
        delta_nwc = nwc - prev_nwc
        delta_nwc_other = forecast["other_working_capital_change"][i]

        # 4. 资本开支与折旧
        capex = revenue * forecast["capex_ratio"][i]
        depreciation = forecast["depreciation"][i]

        # 5. 债务与现金
        interest = debt * assumptions["discount"]["kd"]
        net_borrowing = forecast["net_borrowing"][i]
        debt = debt + net_borrowing

        # 6. 股本（归属与新发分开记，见假设登记的 share_issuance / vesting）
        shares = shares + forecast["share_issuance"][i]

        # 利息与税
        ebt = ebit - interest
        tax = max(ebt, 0.0) * tax_rate
        net_income = ebt - tax

        # 非现金项（股份支付、减值、公允价值变动、递延所得税等）——
        # 它不进净利润的现金部分，但 CFO 里要加回。
        non_cash = forecast["non_cash_items"][i]

        # --- 经营活动现金流 ---
        cfo = net_income + depreciation - delta_nwc - delta_nwc_other + non_cash

        # --- FCFE 两条路 ---
        # 净利润路径：从净利润出发逐项调整
        fcfe_ni = net_income + depreciation - capex - delta_nwc + net_borrowing
        # 经营现金流路径：从 CFO 出发，CFO 已经含了非现金项与三类之外的营运资本变动
        fcfe_cfo = cfo - capex + net_borrowing
        # 差额桥 —— 两条路的差只有这两项，对不上说明哪里漏了
        fcfe_bridge = non_cash - delta_nwc_other

        # --- FCFF 两条路 ---
        fcff_ni = ebit * (1 - tax_rate) + depreciation - capex - delta_nwc
        fcff_cfo = cfo + interest * (1 - tax_rate) - capex
        fcff_bridge = non_cash - delta_nwc_other

        # 分红 —— 目标价那一步要用它，因为付出去的钱不再留在公司里
        dividend = net_income * payout[i]

        rows.append({
            "year": i + 1,
            "volume_growth": volume_growth[i],
            "asp_growth": asp_growth[i],
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin": gross_margin[i],
            "operating_expenses": operating_expenses,
            "ebit": ebit,
            "interest": interest,
            "ebt": ebt,
            "tax": tax,
            "net_income": net_income,
            "non_cash_items": non_cash,
            "depreciation_amortization": depreciation,
            "capex": capex,
            "inventory": inventory,
            "accounts_receivable": accounts_receivable,
            "accounts_payable": accounts_payable,
            "delta_nwc": delta_nwc,
            "delta_nwc_other": delta_nwc_other,
            "operating_cash_flow": cfo,
            "net_borrowing": net_borrowing,
            "debt": debt,
            "shares": shares,
            "dividend": dividend,
            "fcfe": fcfe_ni,               # 主口径 = 净利润路径
            "fcfe_ni_path": fcfe_ni,
            "fcfe_cfo_path": fcfe_cfo,
            "fcfe_bridge": fcfe_bridge,
            "fcff": fcff_ni,               # 主口径 = EBIT 路径
            "fcff_ni_path": fcff_ni,
            "fcff_cfo_path": fcff_cfo,
            "fcff_bridge": fcff_bridge,
        })
        prev_revenue = revenue
        prev_nwc = nwc

    return {
        "rows": rows,
        "debt_end": debt,
        "cash_end": cash,
        "shares_end": shares,
        "base": {
            "period": periods[-1],
            "months": months,
            "annualize": annualize,
            "revenue_as_reported": float(latest["revenue"]),
            "revenue_annualized": base_revenue,
        },
    }


# --------------------------------------------------------------------------
# 七、八：两路折现
# --------------------------------------------------------------------------

def _pv(flows, rate):
    return sum(flow / (1 + rate) ** (i + 1) for i, flow in enumerate(flows))


def _terminal(flow_final, rate, growth):
    if growth >= rate:
        raise MissingInputError(
            "terminal", "growth",
            f"g ({growth:.4f}) 必须小于折现率 ({rate:.4f})，否则终值没有意义",
        )
    return flow_final * (1 + growth) / (rate - growth)


def value_fcfe(projection, assumptions):
    """FCFE 折现 → 直接得到股权价值。主估值。

    两条路各算一遍，**差额桥单列**。两条路的差只来自「非现金项」与「三类之外的
    营运资本变动」，不是 0 就说明这两项有实质影响，要写进报告。
    """
    rows = projection["rows"]
    ke = assumptions["discount"]["ke"]
    growth = assumptions["terminal"]["growth"]

    flows = [r["fcfe_ni_path"] for r in rows]
    flows_cfo = [r["fcfe_cfo_path"] for r in rows]

    pv_explicit = _pv(flows, ke)
    tv = _terminal(flows[-1], ke, growth)
    pv_terminal = tv / (1 + ke) ** len(flows)
    equity_value = pv_explicit + pv_terminal

    pv_explicit_cfo = _pv(flows_cfo, ke)
    tv_cfo = _terminal(flows_cfo[-1], ke, growth)
    pv_terminal_cfo = tv_cfo / (1 + ke) ** len(flows_cfo)
    equity_value_cfo = pv_explicit_cfo + pv_terminal_cfo

    shares = rows[-1]["shares"]
    per_share = equity_value / shares
    per_share_cfo = equity_value_cfo / shares

    return {
        "method": "FCFE",
        "role": "主估值",
        "discount_rate": ke,
        "pv_explicit": pv_explicit,
        "terminal_value": tv,
        "pv_terminal": pv_terminal,
        "terminal_share": pv_terminal / equity_value if equity_value else None,
        "equity_value": equity_value,
        "shares": shares,
        "per_share": per_share,
        "cfo_path": {
            "per_share": per_share_cfo,
            "equity_value": equity_value_cfo,
            "pv_explicit": pv_explicit_cfo,
            "terminal_share": pv_terminal_cfo / equity_value_cfo if equity_value_cfo else None,
        },
        # 差额桥：两条路逐年的差，加上终值口径下折现后的总差
        "bridge": {
            "yearly": [r["fcfe_bridge"] for r in rows],
            "per_share_gap": per_share_cfo - per_share,
            "gap_ratio": (per_share_cfo - per_share) / per_share if per_share else None,
            "driver": "非现金项 − 三类之外的营运资本变动（ΔNWC_other）",
            "note": "两条路恒等时差为 0；不为 0 说明股份支付 / 减值 / 预付款等项有实质金额，"
                    "须在报告中说明取值依据",
        },
        # 净利润路径与 CFO 路径的年度对照，便于审计
        "paths": {
            "net_income_path": flows,
            "cfo_path": flows_cfo,
        },
    }


def value_fcff(projection, assumptions, inputs):
    """FCFF 折现 → 企业价值 → 桥接到股权价值。一致性核验。同样两条路。"""
    rows = projection["rows"]
    wacc = assumptions["discount"]["wacc"]
    kd = assumptions["discount"]["kd"]
    ke = assumptions["discount"]["ke"]
    growth = assumptions["terminal"]["growth"]
    tax = assumptions["forecast"]["tax_rate"]
    shares = rows[-1]["shares"]
    price = inputs["meta"]["latest_price"]

    # WACC 用**股权与有息债务的市场价值**加权。
    # 现金不是负债务 —— 它不在权重里，在下面的桥里处理。
    equity_mv = shares * price
    debt_mv = projection["debt_end"]
    total = equity_mv + debt_mv
    if total <= 0:
        raise MissingInputError("discount", "wacc", "股权与债务市值之和不为正，无法加权")
    weight_equity = equity_mv / total
    weight_debt = debt_mv / total
    wacc_check = weight_equity * ke + weight_debt * kd * (1 - tax)

    def _ev(flows):
        pv = _pv(flows, wacc)
        tv_inner = _terminal(flows[-1], wacc, growth)
        pv_tv = tv_inner / (1 + wacc) ** len(flows)
        return pv, tv_inner, pv_tv, pv + pv_tv

    flows = [r["fcff_ni_path"] for r in rows]
    flows_cfo = [r["fcff_cfo_path"] for r in rows]
    pv_explicit, tv, pv_terminal, enterprise_value = _ev(flows)
    _, _, _, enterprise_value_cfo = _ev(flows_cfo)

    net_debt = projection["debt_end"] - projection["cash_end"]
    equity_value = enterprise_value - net_debt

    return {
        "method": "FCFF",
        "role": "一致性核验",
        "discount_rate": wacc,
        "wacc_check": wacc_check,
        "wacc_gap": wacc - wacc_check,
        "weight_equity": weight_equity,
        "weight_debt": weight_debt,
        "debt_basis": "有息债务市场价值（现金单列，在桥里处理）",
        "cash_basis": "现金按最近一期实际数持有，不滚存 —— 若预测期有大额融资未动用，桥接会低估股权价值",
        "pv_explicit": pv_explicit,
        "terminal_value": tv,
        "pv_terminal": pv_terminal,
        "terminal_share": pv_terminal / enterprise_value if enterprise_value else None,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "equity_value": equity_value,
        "per_share": equity_value / shares,
        "cfo_path": {
            "enterprise_value": enterprise_value_cfo,
            "equity_value": enterprise_value_cfo - net_debt,
            "per_share": (enterprise_value_cfo - net_debt) / shares,
        },
        "bridge": {
            "yearly": [r["fcff_bridge"] for r in rows],
            "per_share_gap": (enterprise_value_cfo - enterprise_value) / shares,
            "driver": "非现金项 − 三类之外的营运资本变动（ΔNWC_other）",
        },
    }


# --------------------------------------------------------------------------
# 九：远期可比
# --------------------------------------------------------------------------

def _aggregate(values, how):
    values = sorted(values)
    count = len(values)
    if how == "median":
        return values[count // 2] if count % 2 else (values[count // 2 - 1] + values[count // 2]) / 2
    if how == "mean":
        return sum(values) / count
    raise MissingInputError("comparables", "aggregate", f"不支持 {how!r}")


def value_comparables(assumptions, inputs, projection):
    """远期可比倍数 → 隐含每股价值。交叉检验。

    **分三层**（直接同业 / 海外光通信 / 混合业务），每层各算远期 P/E 与 EV/EBITDA
    两个口径。三层不合并成一个数、两个口径也不加权 —— 报的是一组隐含价值，
    看的是它们落在什么区间、层与层之间差多少。

    所有倍数必须是**同一日期**的前瞻口径。日期不同，倍数之间不可比。
    """
    block = assumptions["comparables"]
    tiers = block["tiers"]
    if not tiers:
        raise MissingInputError("comparables", "tiers", "可比公司一层都没有")

    as_of = _norm_date(req(block, "as_of", "comparables"), "comparables.as_of")
    how = block["aggregate"]
    rows = projection["rows"]
    final = rows[-1]

    # 统一口径的前瞻分母。有券商一致预期时用 consensus 覆盖，没有就用模型自己的预测。
    eps = optional_num(block, "consensus_eps") or (final["net_income"] / final["shares"])
    ebitda = optional_num(block, "consensus_ebitda") or (
        final["ebit"] + final["depreciation_amortization"])
    net_debt = projection["debt_end"] - projection["cash_end"]
    shares = final["shares"]

    def _per_share_pe(multiple):
        return multiple * eps

    def _per_share_ev_ebitda(multiple):
        return (multiple * ebitda - net_debt) / shares

    detail = []
    values = []
    for index, tier in enumerate(tiers):
        at = f"comparables.tiers[{index}]"
        name = req(tier, "name", at)
        peers = req(tier, "peers", at)
        if not peers:
            raise MissingInputError(at, "peers", f"分层「{name}」一家公司都没有")

        pe_list, ev_list = [], []
        for peer in peers:
            where = f"{at}.peers.{peer.get('name', '?')}"
            pe_list.append(req_num(peer, "forward_pe", where))
            ev_list.append(req_num(peer, "ev_ebitda", where))

        pe_agg = _aggregate(pe_list, how)
        ev_agg = _aggregate(ev_list, how)
        pe_value = _per_share_pe(pe_agg)
        ev_value = _per_share_ev_ebitda(ev_agg)
        values += [pe_value, ev_value]

        detail.append({
            "tier": name,
            "as_of": as_of,
            "peer_count": len(peers),
            "peers": [peer.get("name") for peer in peers],
            "forward_pe": {"multiples": sorted(pe_list), "aggregate": pe_agg, "per_share": pe_value},
            "ev_ebitda": {"multiples": sorted(ev_list), "aggregate": ev_agg, "per_share": ev_value},
        })

    discount = assumptions["discount_for_differences"]
    if discount:
        for item in detail:
            item["forward_pe"]["per_share"] *= (1 - discount)
            item["ev_ebitda"]["per_share"] *= (1 - discount)
        values = [v * (1 - discount) for v in values]

    return {
        "method": "远期可比",
        "role": "交叉检验",
        "as_of": as_of,
        "aggregate": how,
        "tiers": detail,
        "tier_count": len(detail),
        "observation_count": len(values),
        "range": {"low": min(values), "high": max(values)},
        "median_of_observations": _aggregate(values, "median"),
        "inputs": {
            "consensus_eps": eps,
            "consensus_ebitda": ebitda,
            "net_debt": net_debt,
            "shares": shares,
            "basis": "前瞻分母优先用券商一致预期；未提供时用模型预测期最后一年的值",
        },
        "discount_applied": discount,
        "note": "三层不合并、两个口径不加权 —— 报隐含价值区间。"
                "同一只标的的 H 股价格是**同一家公司的跨市场观察**，不构成第四个独立估值。",
    }


# --------------------------------------------------------------------------
# 三个价格：市价 / 即期公允价值 / 12 个月目标价
# --------------------------------------------------------------------------

def value_prices(inputs, assumptions, projection, fcfe):
    """三个价格分开算，**不混为一谈**。

      - `market_price` —— 市场现价，取自行情输入
      - `spot_fair_value` —— 即期公允价值，FCFE 折现直接得到
      - `twelve_month_target_price` —— 目标日的股权价值 ÷ 目标日预测稀释股本

    目标价**不是** `即期价值 × (1 + Ke)`。那个写法只有在「第一年一分钱都不分出去」
    时才成立 —— 分掉的钱不再留在公司里，不能再按 Ke 增值。本函数用显式重估：
    把目标日之后剩余的 FCFE 重新折现，再把留存下来没分的部分加回去。
    两个口径的结果都给出，让人看出差在哪。
    """
    rows = projection["rows"]
    ke = assumptions["discount"]["ke"]
    growth = assumptions["terminal"]["growth"]
    n = len(rows)
    market = inputs["meta"]["latest_price"]

    v0 = fcfe["equity_value"]
    f1 = rows[0]["fcfe_ni_path"]
    dividend1 = rows[0]["dividend"]

    # 目标日之后剩余的 FCFE（第 2 年起）在目标日的价值
    pv_remaining = sum(
        row["fcfe_ni_path"] / (1 + ke) ** (index + 1)
        for index, row in enumerate(rows[1:])
    )
    tv = _terminal(rows[-1]["fcfe_ni_path"], ke, growth)
    pv_terminal_at_target = tv / (1 + ke) ** (n - 1)
    v1_explicit = pv_remaining + pv_terminal_at_target

    # 交叉核验：V1 = V0 × (1 + Ke) − FCFE₁。两条算法必须一致。
    v1_closed_form = v0 * (1 + ke) - f1

    retained = f1 - dividend1
    equity_at_target = v1_explicit + retained
    shares_at_target = rows[0]["shares"]

    target_price = equity_at_target / shares_at_target
    naive_price = v0 * (1 + ke) / shares_at_target   # 只在 dividend1 = 0 时才对
    expected_dividend = dividend1 / shares_at_target

    return {
        "market_price": market,
        "spot_fair_value": fcfe["per_share"],
        "twelve_month_target_price": target_price,
        "expected_dividend": expected_dividend,
        "expected_total_return": (target_price + expected_dividend) / market - 1.0,
        "expected_price_return": target_price / market - 1.0,
        "shares_at_target": shares_at_target,
        "shares_basis": "目标日的预测稀释股本 —— 分子与分母必须同一口径",
        "revaluation": {
            "v0_equity": v0,
            "v1_explicit": v1_explicit,
            "v1_closed_form": v1_closed_form,
            "reconciliation_gap": v1_explicit - v1_closed_form,
            "pv_remaining_fcfe": pv_remaining,
            "pv_terminal_at_target": pv_terminal_at_target,
            "retained_after_dividend": retained,
            "equity_at_target": equity_at_target,
        },
        "naive_check": {
            "naive_price": naive_price,
            "gap": naive_price - target_price,
            "valid_when": "第一年分红为 0 时两个口径相等；本例第一年分红 "
                          f"{dividend1:,.2f} 亿元，故不相等的部分正来自这笔分掉的钱",
            "valid": abs(dividend1) < TOL,
        },
        "alignment": _target_alignment(inputs, assumptions, n),
    }


def _target_alignment(inputs, assumptions, years):
    """目标日与预测期第一年年度末对不对得齐。

    目标价是把预测期**第一年**的 FCFE 分掉之后，对剩余部分重估。所以对齐的参照
    是「第一年年度末」，不是最后一年。只有估值基准日恰好落在会计年度末时，
    基准日 + 12 个月才与第一年年度末重合。对不齐时如实报出偏差 —— **不假装对齐**。
    """
    meta = inputs["meta"]
    target = meta["target_date"]
    fiscal = inputs.get("fiscal") or {}
    year_end_month = fiscal.get("year_end_month")
    base_year = fiscal.get("base_year")
    if base_year is None:
        return {
            "aligned": None,
            "target_date": target,
            "reason": fiscal.get("reason", "无法从历史报告期推出财年结束日"),
        }

    last_day = 28 if year_end_month == 2 else (30 if year_end_month in (4, 6, 9, 11) else 31)
    year_end = f"{int(base_year) + 1}-{year_end_month:02d}-{last_day:02d}"

    if target == year_end:
        return {
            "aligned": True,
            "target_date": target,
            "first_forecast_year_end": year_end,
            "reason": None,
        }

    def _days(iso):
        y, m, d = (int(part) for part in iso.split("-"))
        return _date(y, m, d).toordinal()

    offset = _days(year_end) - _days(target)
    direction = "早于" if offset < 0 else "晚于"
    return {
        "aligned": False,
        "target_date": target,
        "first_forecast_year_end": year_end,
        "offset_days": offset,
        "reason": (
            f"预测期第一年年度末 {year_end} {direction}目标日 {target} "
            f"约 {abs(offset) / 30.44:.1f} 个月（{abs(offset)} 天）。"
            "目标价按「估值基准日起满 12 个月」对预测期第一年的剩余 FCFE 重估，"
            "此处存在跨期错配。"
            "**这一项需要团队确认**：是把估值基准日挪到会计年度末，"
            "还是接受该近似并在报告中写明。未经确认不擅自改假设。"
        ),
    }


# --------------------------------------------------------------------------
# 情景与敏感性
# --------------------------------------------------------------------------

def run_scenarios(inputs, assumptions):
    """基准 / 乐观 / 悲观三情景。**不预设概率、不给加权期望值。**"""
    scenarios = {"base": {}}
    for name in ("bull", "bear"):
        override = assumptions["scenarios"].get(name)
        if override is None:
            raise MissingInputError("assumptions", f"scenarios.{name}", "情景参数缺失")
        scenarios[name] = override

    results = {}
    for name, override in scenarios.items():
        projection = build_forecast(inputs, assumptions, override)
        fcfe = value_fcfe(projection, assumptions)
        results[name] = {
            "override": override,
            "per_share": fcfe["per_share"],
            "fcfe": fcfe,
        }

    base = results["base"]["per_share"]
    for name in ("bull", "bear"):
        results[name]["delta_vs_base"] = (
            (results[name]["per_share"] - base) / base if base else None
        )
    return results


def sensitivity_ke_g(inputs, assumptions, ke_range, g_range):
    """敏感性一：Ke × g（资本成本）。"""
    table = []
    for ke in ke_range:
        row = []
        for g in g_range:
            if g >= ke:
                row.append(None)  # 不满足 Ke > g 的格子留空，不硬算一个数
                continue
            trial = copy.deepcopy(assumptions)
            trial["discount"]["ke"] = ke
            trial["terminal"]["growth"] = g
            projection = build_forecast(inputs, trial)
            row.append(value_fcfe(projection, trial)["per_share"])
        table.append(row)
    return {"ke_range": list(ke_range), "g_range": list(g_range), "table": table}


def sensitivity_gm_dio(inputs, assumptions, gm_range, dio_range):
    """敏感性二：毛利率 × DIO（经营）。"""
    table = []
    base_gm = assumptions["forecast"]["gross_margin"][0]
    base_dio = assumptions["forecast"]["dio_days"][0]
    for gm in gm_range:
        row = []
        for dio in dio_range:
            projection = build_forecast(inputs, assumptions, {
                "gross_margin_delta": gm - base_gm,
                "dio_days_delta": dio - base_dio,
            })
            row.append(value_fcfe(projection, assumptions)["per_share"])
        table.append(row)
    return {"gm_range": list(gm_range), "dio_range": list(dio_range), "table": table}


def broker_attribution(*_args, **_kwargs):
    """预留：券商预测差异归因 —— 拆解本模型与券商预测的差异来源。

    **未实现。** 标为「预留」，不写成已完成（valuation 技能 §5.3）。
    """
    raise NotImplementedError("券商预测差异归因为预留项，尚未实现。")


# --------------------------------------------------------------------------
# 总入口
# --------------------------------------------------------------------------

def articulation(inputs, projection):
    """三表勾稽：能查的查，查不了的如实记为「未检索」，不按 0 算。

    查的是**历史期**（已经发生的事），不是预测期 —— 预测期的勾稽由公式本身保证。
    """
    checks = []
    actual = inputs["actual"]

    for period in inputs["periods"]:
        row = actual[period]
        # 1. 利润表：收入 − 成本 − 期间费用 = EBIT
        if row.get("operating_expenses") is not None:
            revenue = float(row["revenue"])
            ebit_calc = revenue - float(row["cogs"]) - float(row["operating_expenses"])
            reported = row.get("ebit")
            checks.append({
                "period": period,
                "check": "收入 − 成本 − 期间费用 = EBIT",
                "calculated": ebit_calc,
                "recorded": reported,
                "status": "通过" if reported is not None and abs(ebit_calc - float(reported)) < 1e-4
                          else ("不一致" if reported is not None else "未检索"),
                "note": "" if reported is not None else "该期缺期间费用明细，EBIT 未计算",
            })

        # 2. 资产负债表恒等式：资产 = 负债 + 权益
        if row.get("total_assets") is not None and row.get("total_liabilities") is not None \
                and row.get("equity_attributable") is not None:
            lhs = float(row["total_assets"])
            rhs = float(row["total_liabilities"]) + float(row["equity_attributable"]) \
                + float(row.get("minority_interest") or 0.0)
            checks.append({
                "period": period,
                "check": "资产 = 负债 + 归母权益 + 少数股东权益",
                "calculated": rhs,
                "recorded": lhs,
                "status": "通过" if abs(lhs - rhs) < 0.05 else "不一致",
                "note": "差额在 0.05 亿元内视为舍入",
            })

        # 3. 现金流量：CFO 与净利润 + 折旧 − 营运资本变动的关系（历史期）
        if row.get("operating_cash_flow") is not None and row.get("net_income") is not None:
            cfo = float(row["operating_cash_flow"])
            ni = float(row["net_income"])
            da = float(row["depreciation_amortization"])
            checks.append({
                "period": period,
                "check": "经营活动现金流净额 对照 净利润 + 折旧摊销",
                "calculated": ni + da,
                "recorded": cfo,
                "status": "参考",
                "note": "差额 = 营运资本变动 + 非现金项 + 其他。历史期不强行归因，"
                        "只记录差额供预测期标定参考",
                "gap": cfo - (ni + da),
            })

    # 4. 固定资产滚动：上年末 + 本年资本开支 − 本年折旧摊销 = 本年末
    #    差额通常来自处置、汇率折算或合并范围变动。不默认它是 0，
    #    但差额大到一定量级就说明有一笔变动没记进来。
    for previous, current in zip(inputs["periods"], inputs["periods"][1:]):
        begin = actual[previous].get("ppe_net")
        end = actual[current].get("ppe_net")
        capex = actual[current].get("capex")
        depreciation = actual[current].get("depreciation_amortization")
        if None in (begin, end, capex, depreciation):
            continue          # 缺项已在 articulation_gaps 里记过，不重复报
        calculated = float(begin) + float(capex) - float(depreciation)
        gap = float(end) - calculated
        checks.append({
            "period": f"{previous} → {current}",
            "check": "固定资产：上年末 + 资本开支 − 折旧摊销 = 本年末",
            "calculated": calculated,
            "recorded": float(end),
            "status": "通过" if abs(gap) < 0.05 else "不一致",
            "note": "差额来自处置、汇率折算或合并范围变动的可能都有；"
                    "对不上要说清是哪一类，不能默认它是 0",
            "gap": gap,
        })

    return {
        "checks": checks,
        "gaps": inputs.get("articulation_gaps") or [],
        "note": "缺口记为「未检索」而不是填入估算值 —— 缺失数据不得默认为零。",
    }


def _provenance(inputs, assumptions):
    """每个正式数字的出处清单。

    门禁 `gates.check_sources` 靠它来查「每个正式数字都有 source_id 或 approved
    assumption_id」。清单直接落在结果文件里，不靠人去翻输入文件核对。
    """
    periods = []
    for period in inputs["periods"]:
        row = inputs["actual"][period]
        periods.append({
            "period": period,
            "source_id": row.get("source_id"),
            "source_file": row.get("source_file"),
            "page": row.get("page"),
            "source_tier": row.get("source_tier"),
            "status": row.get("status"),
            "field_overrides": sorted((row.get("field_meta") or {}).keys()),
        })

    assumptions_out = []
    for entry in (assumptions.get("register") or {}).values():
        assumptions_out.append({
            "id": entry.id,
            "item": entry.item,
            "source_id": entry.source_id,
            "status": entry.status,
            "owner": entry.owner,
        })

    capital = inputs.get("capital") or {}
    return {
        "periods": periods,
        "assumptions": assumptions_out,
        "capital_source_id": capital.get("source_id"),
        "note": "历史数字引 `source_id`，假设引 `approved assumption_id`。"
                "引用未登记或状态不允许的来源，`load_inputs` 已经报错，到不了这一步。",
    }


def run_model(inputs, assumptions, mode="formal", sensitivity_spec=None):
    """跑完整模型，返回可直接落盘的结果 dict。"""
    from . import reverse as reverse_module

    projection = build_forecast(inputs, assumptions)
    fcfe = value_fcfe(projection, assumptions)
    fcff = value_fcff(projection, assumptions, inputs)
    comparables = value_comparables(assumptions, inputs, projection)
    scenarios = run_scenarios(inputs, assumptions)
    prices = value_prices(inputs, assumptions, projection, fcfe)
    reverse_result = reverse_module.reverse_valuation(inputs, assumptions)

    spec = sensitivity_spec or {}
    ke = assumptions["discount"]["ke"]
    g = assumptions["terminal"]["growth"]
    gm = assumptions["forecast"]["gross_margin"][0]
    dio = assumptions["forecast"]["dio_days"][0]

    sensitivities = {
        "ke_g": sensitivity_ke_g(
            inputs, assumptions,
            spec.get("ke_range") or [ke - 0.01, ke - 0.005, ke, ke + 0.005, ke + 0.01],
            spec.get("g_range") or [g - 0.01, g - 0.005, g, g + 0.005, g + 0.01],
        ),
        "gm_dio": sensitivity_gm_dio(
            inputs, assumptions,
            spec.get("gm_range") or [gm - 0.03, gm - 0.015, gm, gm + 0.015, gm + 0.03],
            spec.get("dio_range") or [dio - 20, dio - 10, dio, dio + 10, dio + 20],
        ),
    }

    return {
        "meta": {
            **inputs["meta"],
            "mode": mode,
            "assumption_status": assumptions["status"],
            "assumption_version": assumptions["version"],
            "confirmed_by": assumptions["confirmed_by"],
            "confirmed_on": assumptions["confirmed_on"],
            "model_version": "v2",
            "forecast_base": projection["base"],
            "fiscal_calendar": inputs.get("fiscal"),
        },
        "forecast": projection["rows"],
        "prices": prices,
        "valuation": {
            "primary": fcfe,
            "cross_check": comparables,
            "consistency": fcff,
        },
        "provenance": _provenance(inputs, assumptions),
        "capital": inputs.get("capital"),
        "scenarios": scenarios,
        "sensitivities": sensitivities,
        "reverse": reverse_result,
        "articulation": articulation(inputs, projection),
        "reserved": {
            "broker_attribution": "预留，未实现 —— 券商预测差异归因",
        },
    }

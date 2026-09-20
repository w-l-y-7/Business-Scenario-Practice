"""输入的 schema 校验层。

三件事在这里做，做完才轮到 `engine.py` 算数：

  1. **最小字段集**（`investment-research/CLAUDE.md` §八）——
     `model/inputs/` 下每一条原始输入至少带 12 个字段，缺一个就不许进模型。
  2. **来源引用**——只能引用 `source_register.csv` 里存在、且状态允许的 `source_id`。
  3. **行情口径**——复权口径、币种、实际交易日必须显式给出，不能靠猜。

`engine.py` 的 `req_*` 管的是「缺了报错」，这一层管的是「字段本身齐不齐、来源能不能引」。
两层都要过。
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from .errors import SchemaError

# --------------------------------------------------------------------------
# 基础类型
# --------------------------------------------------------------------------

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _to_iso(value):
    """YAML 里没加引号的 `2026-06-18` 会被解析成 datetime.date，两种写法都得能用。"""
    if value is None or isinstance(value, bool):
        raise ValueError(f"取值 {value!r} 不是日期")
    text = value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value).strip()
    if not _ISO.match(text):
        raise ValueError(f"`{text}` 不是 YYYY-MM-DD 格式")
    return text


IsoDate = Annotated[str, BeforeValidator(_to_iso)]

# 模型输入的 status 取值（CLAUDE.md §八）
InputStatus = Literal["reported", "derived", "candidate", "approved", "deprecated", "missing"]

# 来源等级（data-standard.md §4.1）
SourceTier = Literal["A", "B", "C", "D"]

# 审计 / 鉴证状态（CLAUDE.md §七）
AssuranceStatus = Literal["经审计", "未经审计", "经审阅", "不适用"]

# 事实或观点（CLAUDE.md §七）
ClaimType = Literal["事实", "观点"]

# 交叉核验（CLAUDE.md §七）—— 写法放开，但必须是这两类之一
_CROSS_OK = re.compile(r"^(单一来源|已交叉核验（\d+ 路）)$")

# 来源登记表里**承载已发生事实**的状态。`candidate` 是尚未确认的材料，不进正式模型输入。
FACT_STATUS = frozenset({"reported", "derived"})

# 线索类来源：只作线索，不是证据。雪球 / 今日头条 / 财富号一类。
# 见 CLAUDE.md §八「资金面来源的用法限定」。
LEAD_SOURCE_TYPES = frozenset({"social_media", "link_record"})

# D 级只作线索。
LEAD_TIERS = frozenset({"D"})

# 最小字段集（CLAUDE.md §八）。别改这里，改规范。
MIN_FIELD_SET = (
    "value", "unit", "currency", "period_start", "period_end",
    "publication_date", "source_file", "page", "source_tier",
    "assurance_status", "status", "notes",
)


# --------------------------------------------------------------------------
# 一、来源登记表的一行（model/inputs/source_register.csv）
# --------------------------------------------------------------------------

class SourceRegisterRow(BaseModel):
    """`source_register.csv` 的一行。这是**证据索引**，不是可选台账。"""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_file: str
    title: str
    issuer: str = ""
    publication_date: str = ""
    page: str = "不适用"
    source_type: str
    source_tier: SourceTier
    assurance_status: AssuranceStatus
    claim_type: ClaimType
    retrieval_date: IsoDate
    status: str
    notes: str = ""

    @model_validator(mode="after")
    def _status_known(self):
        known = FACT_STATUS | {"candidate", "unverified", "secondary_lead", "deprecated"}
        if self.status not in known:
            raise ValueError(
                f"`status` 取值 `{self.status}` 不在允许范围内（{sorted(known)}）"
            )
        return self

    def blocking_reason(self):
        """能不能进正式模型。能引用返回 None，不能引用返回原因。

        三条各管一件事，互相独立：
          - `status` 说明这份材料承载的是**已发生的事实**还是尚未确认的东西；
          - `source_type` 说明它是**证据**还是**线索**；
          - `source_tier` 是可信度分级。

        **线索类不等于不能用** —— 线索可以用来找方向，但要形成关键结论必须回溯到
        官方原文（USTR / BIS / CBP、公司公告、基金报告）。回溯到之前，不进正式模型。
        """
        if self.status == "deprecated":
            return "该来源已作废"
        if self.status not in FACT_STATUS:
            return (f"status=`{self.status}``——不是已发生的事实，"
                    "未经确认的材料不进正式模型输入")
        if self.source_type in LEAD_SOURCE_TYPES:
            return (f"source_type=`{self.source_type}`——线索类来源，只作线索。"
                    "其中的关税、清单、税率、禁令说法必须回溯到官方原文才能形成关键结论")
        if self.source_tier in LEAD_TIERS:
            return f"source_tier=`{self.source_tier}`——D 级只作线索"
        return None


def load_source_register(rows, mode="formal"):
    """把 CSV 行列表变成 `{source_id: SourceRegisterRow}`，并算出哪些能在本模式下被引用。"""
    register = {}
    for index, row in enumerate(rows or []):
        try:
            parsed = SourceRegisterRow(**(row if isinstance(row, dict) else row.__dict__))
        except Exception as error:  # noqa: BLE001 —— pydantic 的 ValidationError 信息很长，压成一行
            raise SchemaError(
                f"source_register.csv 第 {index + 2} 行不合格：{_squash(error)}"
            ) from error
        if parsed.source_id in register:
            raise SchemaError(f"source_register.csv 里 `{parsed.source_id}` 出现了两次，id 必须唯一")
        register[parsed.source_id] = parsed

    # 正式模式只认能引用的；test 模式放开线索类，但仍拒绝 deprecated 与 candidate。
    allowed = {
        sid for sid, row in register.items()
        if row.blocking_reason() is None
        or (mode != "formal" and row.status not in ("deprecated", "candidate")
            and row.source_type not in LEAD_SOURCE_TYPES)
    }
    return {"rows": register, "allowed": allowed, "mode": mode}


def check_source_ref(register, source_id, where):
    """校验一个 `source_id` 能不能在本模式下被引用。"""
    if register is None:
        raise SchemaError(f"{where} 想引用 `{source_id}`，但本次运行没有提供 source_register.csv")
    row = register["rows"].get(source_id)
    if row is None:
        raise SchemaError(
            f"{where} 引用了 `{source_id}`，但 source_register.csv 里没有这个 id。"
            "引用未登记的来源必须报错，不许算下去 —— 那是没有出处的数。"
        )
    if source_id not in register["allowed"]:
        raise SchemaError(
            f"{where} 引用的 `{source_id}` 不能在本模式（{register['mode']}）下引用："
            f"{row.blocking_reason()}。"
        )
    return row


# --------------------------------------------------------------------------
# 二、历史输入的单个报告期
# --------------------------------------------------------------------------

class FieldMeta(BaseModel):
    """字段级覆盖。块级元信息够用时不用写；某几个数口径特殊时才写。"""

    model_config = ConfigDict(extra="forbid")

    unit: str | None = None
    currency: str | None = None
    page: str | None = None
    source_tier: SourceTier | None = None
    assurance_status: AssuranceStatus | None = None
    status: InputStatus | None = None
    source_id: str | None = None
    notes: str = ""


class PeriodInput(BaseModel):
    """一个报告期的历史输入。

    块级带一套最小字段集，期内每个数字共享；个别数字口径不同就用 `field_meta` 覆盖。
    这样既满足「每条原始输入都带 12 个字段」，又不至于把一个数写成 12 行。
    """

    model_config = ConfigDict(extra="forbid")

    # —— 最小字段集（块级）——
    unit: str
    currency: str
    period_start: IsoDate
    period_end: IsoDate
    publication_date: IsoDate
    source_file: str
    source_id: str
    page: str = "不适用"
    source_tier: SourceTier
    assurance_status: AssuranceStatus
    status: InputStatus
    notes: str = ""

    field_meta: dict[str, FieldMeta] = Field(default_factory=dict)
    source_pages: str = ""

    @model_validator(mode="after")
    def _period_order(self):
        if self.period_end < self.period_start:
            raise ValueError(f"period_end ({self.period_end}) 早于 period_start ({self.period_start})")
        return self

    @model_validator(mode="after")
    def _deprecated_block_is_marked(self):
        if self.status == "deprecated" and not self.notes:
            raise ValueError("整个报告期被标 `deprecated`，必须在 `notes` 里写清作废原因")
        return self


PERIOD_META_FIELDS = tuple(PeriodInput.model_fields)


def validate_period(period_key, block, register, mode="formal"):
    """校验单个报告期的**元信息**，返回规范化后的结果。数字本身留给 engine 取。

    一个报告期块里既有元信息（单位、来源、期间）又有几十个数字。这里只挑元信息去校验，
    数字由 `engine.load_inputs` 按必需 / 勾稽两类分别处理。
    """
    meta = {name: block[name] for name in PERIOD_META_FIELDS if name in block}
    meta.setdefault("field_meta", block.get("field_meta") or {})
    try:
        parsed = PeriodInput(**meta)
    except Exception as error:  # noqa: BLE001
        raise SchemaError(f"actual.{period_key} 的元信息不合格：{_squash(error)}") from error

    if register is not None:
        check_source_ref(register, parsed.source_id, f"actual.{period_key}")

    for name, meta in parsed.field_meta.items():
        if meta.source_id and register is not None:
            check_source_ref(register, meta.source_id, f"actual.{period_key}.{name}")
        if meta.status == "deprecated":
            raise SchemaError(
                f"actual.{period_key}.{name} 被标 `deprecated` —— 作废的输入不该留在模型输入里，"
                "请移到核验记录，或改成正确的值。"
            )
    return parsed


# --------------------------------------------------------------------------
# 三、假设登记（每条假设的 9 个字段）
# --------------------------------------------------------------------------

ASSUMPTION_FIELDS = ("value", "unit", "scenario", "evidence", "source_id",
                     "rationale", "owner", "status", "review_note")


class AssumptionEntry(BaseModel):
    """候选假设的一条登记。

    数字本身写在 `candidate.yaml` 的 `forecast` / `discount` / `terminal` 里（机器要算），
    这一块记的是**每条假设凭什么取这个值**（人要审）。两边用 `item` 这个点号路径对应。
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    item: str                      # 例：forecast.volume_growth / discount.ke / terminal.growth
    value: Any
    unit: str
    scenario: Literal["base", "bull", "bear"]
    evidence: str
    source_id: str
    rationale: str
    owner: str
    status: InputStatus
    review_note: str = ""

    @model_validator(mode="after")
    def _candidate_or_approved(self):
        if self.status not in ("candidate", "approved", "derived", "reported"):
            raise ValueError(
                f"假设登记 `{self.id}` 的 status 是 `{self.status}`；"
                "假设只能是 candidate / approved / derived / reported"
            )
        return self

    @model_validator(mode="after")
    def _candidate_needs_review_note(self):
        if self.status == "candidate" and not self.review_note:
            raise ValueError(f"候选假设 `{self.id}` 必须写 `review_note`，说明等谁确认什么")
        return self


def load_assumption_register(raw_entries, raw, register, mode="formal"):
    """校验假设登记：**每条都要登记过**，且登记的取值与文件里的取值一致。

    第二道检查防的是「登记表还停在上一版」：有人把 `candidate.yaml` 里的
    毛利率从 40% 改成 42%，登记表没跟着改，于是模型用着没被审过的数、
    却指着一份写着 40% 的确认记录。两道一比对就露出来了。
    """
    entries = {}
    for index, item in enumerate(raw_entries or []):
        try:
            parsed = AssumptionEntry(**item)
        except Exception as error:  # noqa: BLE001
            raise SchemaError(f"assumptions_register[{index}] 不合格：{_squash(error)}") from error
        if parsed.id in entries:
            raise SchemaError(f"假设登记里 `{parsed.id}` 出现了两次，id 必须唯一")
        entries[parsed.id] = parsed

    covered = {entry.item for entry in entries.values()}

    # 覆盖检查对着**文件里实际出现的键**做，缺省的可选键（如 discount.risk_free）
    # 不写就不必登记；`forecast.years` 是结构性字段，不是假设。
    missing = [item for item in declared_items(raw) if item not in covered]
    if missing:
        raise SchemaError(
            "这些假设在假设文件里有数、但 assumptions_register 里没有登记："
            + "、".join(missing)
            + "。每个数字都要说清凭什么取这个值，没登记的不许进模型。"
        )

    stale = []
    for entry in entries.values():
        if entry.scenario != "base":
            continue          # 情景条目的取值本就是相对基准的偏置，不与文件直接比对
        actual = file_value(raw, entry.item)
        if actual is None:
            continue
        if not _same_value(entry.value, actual):
            stale.append(f"`{entry.id}`（{entry.item}）登记 {entry.value!r}，文件里是 {actual!r}")
    if stale:
        raise SchemaError(
            "假设登记表与假设文件的取值对不上：\n  - " + "\n  - ".join(stale)
            + "\n登记表记录的是「被审过的是什么值」。改数必须同步改登记，"
            "否则模型用着没审过的数、却指着一份写着旧值的记录。"
        )

    if register is not None:
        for entry in entries.values():
            if entry.source_id and entry.source_id != "assumption":
                check_source_ref(register, entry.source_id, f"assumptions_register.{entry.id}")
    return entries


STRUCTURAL_ITEMS = frozenset({"forecast.years"})
REGISTERED_BLOCKS = ("forecast", "discount", "terminal")


def declared_items(raw):
    """假设文件里出现的、需要登记的假设（点号路径）。"""
    items = []
    for block in REGISTERED_BLOCKS:
        for key in (raw.get(block) or {}):
            item = f"{block}.{key}"
            if item not in STRUCTURAL_ITEMS:
                items.append(item)
    return items


def file_value(raw, item):
    """按 `forecast.volume_growth` 这样的路径取值。"""
    block, _, key = item.partition(".")
    return (raw.get(block) or {}).get(key)


def _same_value(left, right):
    """登记值与文件值是否一致。列表逐项比，数值按浮点容差比。"""
    left_is_seq = isinstance(left, (list, tuple))
    right_is_seq = isinstance(right, (list, tuple))
    if left_is_seq or right_is_seq:
        if not (left_is_seq and right_is_seq) or len(left) != len(right):
            return False
        return all(_same_value(a, b) for a, b in zip(left, right))
    try:
        return abs(float(left) - float(right)) <= 1e-9
    except (TypeError, ValueError):
        return left == right


# --------------------------------------------------------------------------
# 四、行情输入（P5 审计建议的 schema）
# --------------------------------------------------------------------------

class MarketQuote(BaseModel):
    """一条行情记录。字段取自 `tools/model/market-data-skill-audit.md` §五。"""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    exchange: Literal["SZ", "SH", "HK", "US"]
    requested_date: IsoDate
    actual_trade_date: IsoDate
    price_type: Literal["close", "open", "high", "low", "vwap", "realtime"]
    adjustment: Literal["none", "forward", "backward"]
    close: float
    currency: Literal["CNY", "HKD", "USD"]
    source: str
    source_grade: SourceTier
    retrieved_at: str
    raw_record_path: str
    status: Literal["ok", "fallback", "suspended", "no_data", "unavailable"]

    @model_validator(mode="after")
    def _no_forward_adj_in_current_price(self):
        # 前复权价不得进现价 —— 它会把历史除权日的价格改掉，与「现价」不是一回事。
        if self.adjustment != "none":
            raise ValueError(
                f"复权口径是 `{self.adjustment}`。估值用的现价必须是**未复权**收盘价"
                "（adjustment=none）；复权价只能用于收益率类区间统计。"
            )
        return self

    @model_validator(mode="after")
    def _fallback_must_be_earlier(self):
        if self.status == "fallback" and self.actual_trade_date >= self.requested_date:
            raise ValueError(
                f"status=fallback 表示请求日不是交易日，实际交易日 {self.actual_trade_date} "
                f"应当早于请求日 {self.requested_date}"
            )
        if self.status != "fallback" and self.actual_trade_date != self.requested_date:
            raise ValueError(
                f"status={self.status} 时实际交易日与请求日不一致（"
                f"{self.actual_trade_date} ≠ {self.requested_date}）—— "
                "两者不等就必须标成 fallback，不许偷偷把实际交易日改成请求日"
            )
        return self

    @model_validator(mode="after")
    def _failures_carry_no_price(self):
        if self.status in ("suspended", "no_data", "unavailable") and self.close > 0:
            raise ValueError(
                f"status={self.status} 表示没取到可用价格，`close` 不该是个正数"
                "——静默把一个看似正常的价当成功，比报错危险得多"
            )
        return self

    def price_note(self):
        """写进报告的行情标注。两者不等时一路透传。"""
        if self.actual_trade_date == self.requested_date:
            return f"as of {self.actual_trade_date}"
        return f"as of {self.requested_date}（实际交易日 {self.actual_trade_date}）"


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def _squash(error):
    """把 pydantic 的多行报错压成一行，便于塞进 ModelError。"""
    text = re.sub(r"\s+", " ", str(error)).strip()
    return text[:400] + ("…" if len(text) > 400 else "")

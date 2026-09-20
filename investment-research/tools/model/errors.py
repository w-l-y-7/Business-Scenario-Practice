"""统一模型的异常类型。

四个异常对应四条硬规矩：
- `MissingInputError` —— 缺失数据不得默认为零（valuation 技能 §4.1）
- `SchemaError` —— 输入必须带齐最小字段集（CLAUDE.md §八），且只能引用已登记的 source_id
- `ReverseSolveError` —— 反向估值在给定区间内无解，如实报无解，不硬凑一个数
- `GateError` —— 输出门禁不通过就不导出（output-format.md §2.5）
"""


class ModelError(Exception):
    """本模型所有异常的基类。"""


class MissingInputError(ModelError):
    """输入缺失或为空。

    这是**故意的**：缺失数据不得默认为零，也不许拿一个「看起来合理」的数顶替。
    缺什么就报什么，让人去补，而不是静默算出一个错的结果。
    """

    def __init__(self, where, key, hint=""):
        self.where = where
        self.key = key
        self.hint = hint
        msg = f"缺失输入：{where} 下的 `{key}` 没有取值"
        if hint:
            msg += f"（{hint}）"
        msg += "。缺失数据不得默认为零 —— 请补全后重跑，不要填一个占位数。"
        super().__init__(msg)


class AssumptionNotApprovedError(ModelError):
    """用未经确认的预测假设产出正式结果。

    审批前可以做历史指标计算、口径核验、模型搭建和合成数据测试；
    但**不许用未经确认的预测假设输出正式估值、评级或目标价**。
    测试请走 `--mode test`（需显式给出 `--synthetic` 数据）。
    """


class SchemaError(ModelError):
    """输入不符合最小字段集，或引用了未登记 / 状态不允许的来源。

    依据 `investment-research/CLAUDE.md` §八：每个原始输入至少带 12 个字段，
    且**只能引用 `source_register.csv` 里存在、且 `status` 允许的 `source_id`**。
    引用一个没登记过的 id，或引用状态不允许的条目，模型报错而不是算下去。
    """


class BridgeError(ModelError):
    """勾稽不成立。

    H 股募集资金现金桥、股本桥、固定资产滚动、资产负债表恒等式——
    任何一处左右不等，都说明有数字被重复计入或漏计，**不许带病往下算**。
    """

    def __init__(self, label, left, right, hint=""):
        self.label = label
        self.left = left
        self.right = right
        self.hint = hint
        msg = f"勾稽不成立：{label} 左 {left:,.4f} ≠ 右 {right:,.4f}（差 {left - right:,.4f}）"
        if hint:
            msg += f"。{hint}"
        super().__init__(msg)


class ReverseSolveError(ModelError):
    """反向估值在给定区间内无解。

    求根区间两端同号，说明市场现价超出了这组假设能达到的范围。
    **如实报「无解」，不硬凑一个数** —— 凑出来的隐含增长率会误导判断。
    """

"""测试夹具。

夹具走的都是**正式代码路径**（`engine.load_inputs` / `engine.load_assumptions`），
不是手工拼的 dict —— 手工拼的 dict 绕过了输入层，而输入层恰恰是最该测的地方。

用合成数据（`tools/model/synthetic/`）只是为了数字方便看，代码路径与真实数据完全一致。
合成数字本身没有意义，**不得引用**。
"""

from __future__ import annotations

import copy
import csv
import sys
from pathlib import Path

import pytest
import yaml

# 测试文件在 tools/model/tests/，包在 tools/model/。把 tools/ 放进路径才能 `from model import ...`，
# 与 run_model.py 的做法一致 —— 测的就是它跑的那份代码。
TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from model import engine, schema  # noqa: E402

SYNTHETIC = Path(__file__).resolve().parents[1] / "synthetic"
MODE = "test"


def load_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_register(path=None, mode=MODE):
    """读 source_register.csv，与 run_model.py 同一条路径（含 BOM 处理）。"""
    path = Path(path or SYNTHETIC / "source_register.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return schema.load_source_register(list(csv.DictReader(handle)), mode=mode)


@pytest.fixture
def raw_inputs():
    return load_yaml(SYNTHETIC / "historical.yaml")


@pytest.fixture
def raw_assumptions():
    return load_yaml(SYNTHETIC / "assumptions_candidate.yaml")


@pytest.fixture
def register():
    return load_register()


@pytest.fixture
def inputs(raw_inputs, register):
    return engine.load_inputs(copy.deepcopy(raw_inputs), register, MODE)


@pytest.fixture
def assumptions(raw_assumptions, register):
    return engine.load_assumptions(copy.deepcopy(raw_assumptions), MODE, register)


@pytest.fixture
def projection(inputs, assumptions):
    return engine.build_forecast(inputs, assumptions)


@pytest.fixture
def results(inputs, assumptions):
    return engine.run_model(inputs, assumptions, mode=MODE)


@pytest.fixture
def half_year_inputs(raw_inputs, register):
    """最新报告期是半年报。

    用来测基期年化：半年收入不年化会把整个预测期低估一半。
    这里 2026H1 收入 60.00 亿元、期间 6 个月 → 年化后 120.00 亿元；
    存货 20.00 亿元是**时点数**，不年化。
    """
    raw = copy.deepcopy(raw_inputs)
    rows = raw["actual"]
    latest = dict(rows["2025A"])
    latest.update({
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "publication_date": "2026-08-20",
        "revenue": 60.00,
    })
    raw["actual"] = {"2023A": rows["2023A"], "2024A": rows["2024A"], "2026H1": latest}
    return engine.load_inputs(raw, register, MODE)

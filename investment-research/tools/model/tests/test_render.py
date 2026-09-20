"""渲染：结果 → Markdown 表格。

报告里的模型表格全部由这里生成，**不手工维护** —— 手工维护的表和模型会各走各的，
过几版就对不上，而且没人知道哪一版是真的。

对应 P6 清单里「报告版本与模型/假设版本一致」在**表格这一层**的落点：
渲染出来的片段必须自带版本与状态标记，粘贴到报告里时差异看得见。
"""

from __future__ import annotations

import pytest

from model import render


def test_全部小节都渲染出来(results):
    text = render.render_all(results)
    for header in ("逐年预测", "FCFE 两条路", "三个价格", "估值总表",
                   "远期可比", "情景", "敏感性", "反向估值",
                   "资本结构", "三表勾稽", "预留项"):
        assert header in text, f"渲染结果里缺「{header}」"


def test_渲染片段自带版本与状态标记(results):
    text = render.render_all(results)
    assert "不手工维护" in text
    assert results["meta"]["assumption_version"] in text
    assert results["meta"]["model_version"] in text
    assert results["meta"]["assumption_status"] in text


def test_test模式的渲染片段写明不得引用(results):
    text = render.render_all(results)
    assert "test" in text
    assert "不得" in text or "未经" in text


def test_版本标记不会顶替报告的版本块(results):
    # 门禁用 `**模型结果版本**：v2` 这样的粗体块比对版本。
    # 渲染片段若也用这个写法，粘到报告里会抢先匹配，把后面写错的版本盖住。
    text = render.render_all(results)
    assert "**模型结果版本**" not in text
    assert "**假设版本**" not in text


def test_渲染不出现None或nan(results):
    text = render.render_all(results)
    assert "None" not in text
    assert "nan" not in text.lower()
    assert "inf" not in text.lower()


def test_敏感性表空格子渲染成破折号(results):
    # Ke ≤ g 的格子是 None（终值没有意义），渲染时不能空着，也不能写成 0。
    # 这里手工造一个含空格子的表，因为基准假设下 ke_range 的每个值都大于 g_range。
    table = {"ke_range": [0.02, 0.10], "g_range": [0.025, 0.03],
             "table": [[None, None], [33.42, 32.10]]}
    text = render.render_sensitivity(table, results["sensitivities"]["gm_dio"])
    assert "| 2.00% | — | — |" in text          # 两个空格子都渲染成破折号，没写成 0
    assert "| 10.00% | 33.42 | 32.10 |" in text  # 有值的格子照常出数
    assert "Ke ≤ g" in text


def test_敏感性表把空格子标成无意义(results):
    table = {"ke_range": [0.02], "g_range": [0.025],
             "table": [[None]]}
    text = render.render_sensitivity(table, results["sensitivities"]["gm_dio"])
    assert "不硬算" in text


def test_三个价格在渲染里分开列示(results):
    text = render.render_prices(results)
    assert "市价" in text
    assert "即期" in text
    assert "目标" in text


def test_估值表保留三个口径不合并(results):
    text = render.render_valuation_table(results)
    assert "主估值" in text
    assert "交叉检验" in text
    assert "一致性核验" in text


def test_情景表不给概率也不给加权期望(results):
    text = render.render_scenario_table(results)
    header = text.splitlines()[0]
    # 表头只有「情景 / 改变的假设 / 每股价值 / 相对基准」四列，
    # 没有概率列、也没有加权后的期望值列。正文里说明「不给」是应该的。
    for banned in ("概率", "权重", "加权", "期望"):
        assert banned not in header
    assert "不预设情景概率" in text


def test_资本结构表列出四种口径(results):
    text = render.render_capital(results)
    for caliber in ("基本股本", "已发行", "潜在奖励", "稀释"):
        assert caliber in text


def test_反向估值表在无解时写无解不编数(inputs, assumptions):
    from model import reverse
    blocked = reverse.reverse_valuation(inputs, assumptions, market_price=0.01)
    text = render.render_reverse({"reverse": blocked})
    assert "无解" in text

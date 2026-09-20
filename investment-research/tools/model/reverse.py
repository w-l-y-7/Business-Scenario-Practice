"""反向估值：从市场现价倒推隐含的假设。

正向估值问「这组假设值多少钱」，反向估值问「市场现价隐含了什么假设」。
两者用同一个内核（`engine.build_forecast` + `engine.value_fcfe`），只是求解方向相反。

三个未知量**一次只解一个**，其余全部固定：
  1. 隐含收入增速 —— 把各年销量增速整体平移一个 δ
  2. 隐含稳态毛利率 —— 把各年毛利率整体平移一个 δ
  3. 隐含 Ke —— 直接解折现率

**为什么一次只解一个**：三个未知量一起解，方程只有一个，解不唯一。
能解出无穷多组组合，报告里给哪一组都是任意的 —— 那不是分析，是凑数。
一次一个，解出来的是「在别的假设都不动的前提下，市场对这一个变量的要求」。

用 `scipy.optimize.brentq`，区间两端必须异号。同号说明现价超出了这组假设
能达到的范围，**如实报无解**，不硬凑一个数。
"""

from __future__ import annotations

import copy

from scipy.optimize import brentq

from .errors import ReverseSolveError
from . import engine

# 求根区间。放宽一些，但两端都要有经济意义。
GROWTH_SHIFT_BRACKET = (-0.60, 3.00)
MARGIN_SHIFT_BRACKET = (-0.45, 0.53)
KE_BRACKET = (0.02, 0.80)


def _solve(objective, lo, hi, label, market_price, base=None, steps=400):
    """在 [lo, hi] 上求根，返回 (解, 求解信息)。

    **不能假定目标函数单调。** 隐含收入增速的区间上端就是个反例：增速越高，
    营运资本占用涨得越快，自由现金流反而塌下去 —— 每股价值先升后降，
    区间两端同号，中间却有解。只看两端就报「无解」，是把有解说成无解。

    所以两端同号时先在区间里扫一遍，找到符号变化的那一小段再收敛。
    扫完仍无符号变化，才是真的无解。

    多个解时取**离基准假设最近**的那个：反向估值问的是「假设要挪多远」，
    最近的那个解才是这个问题的最小回答。
    """
    flo = objective(lo)
    fhi = objective(hi)
    if flo == 0.0:
        return lo, {"bracket": [lo, lo], "roots_found": 1, "scanned": False}
    if fhi == 0.0:
        return hi, {"bracket": [hi, hi], "roots_found": 1, "scanned": False}
    if flo * fhi < 0:
        root = brentq(objective, lo, hi, xtol=1e-12, rtol=1e-14, maxiter=200)
        return root, {"bracket": [lo, hi], "roots_found": 1, "scanned": False}

    brackets = []
    previous_x, previous_f = lo, flo
    for index in range(1, steps + 1):
        x = lo + (hi - lo) * index / steps
        f = objective(x)
        if f == 0.0:
            brackets.append((x, x))
        elif previous_f * f < 0:
            brackets.append((previous_x, x))
        previous_x, previous_f = x, f

    if not brackets:
        side = "高于" if flo > 0 else "低于"
        raise ReverseSolveError(
            f"反向估值无解：{label}。在区间 [{lo:,.4f}, {hi:,.4f}] 上，"
            f"模型每股价值始终{side}市场现价 {market_price:,.2f} 元"
            f"（区间下端的差 {flo:,.2f}，上端的差 {fhi:,.2f}）。"
            f"这说明市场现价超出了这组假设在合理范围内能达到的水平 —— "
            "要么别的假设需要调整，要么现价确实偏离模型。**不硬凑一个解。**"
        )

    if base is not None:
        # 离基准假设最近的那一段排在最前
        brackets.sort(key=lambda pair: min(abs(pair[0] - base), abs(pair[1] - base)))
    left, right = brackets[0]
    root = left if left == right else brentq(
        objective, left, right, xtol=1e-12, rtol=1e-14, maxiter=200)
    return root, {"bracket": [left, right], "roots_found": len(brackets), "scanned": True}


def _per_share(inputs, assumptions):
    return engine.value_fcfe(engine.build_forecast(inputs, assumptions), assumptions)["per_share"]


def _revenue_cagr(rows):
    """从预测期收入序列算复合年增速。"""
    first, last = rows[0]["revenue"], rows[-1]["revenue"]
    years = len(rows)
    if first <= 0 or years < 1:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def implied_revenue_growth(inputs, assumptions, market_price):
    """市场中隐含的收入增速：各年销量增速整体平移 δ，求使每股价值 = 现价的 δ。"""
    base = list(assumptions["forecast"]["volume_growth"])

    def objective(delta):
        trial = copy.deepcopy(assumptions)
        trial["forecast"]["volume_growth"] = [v + delta for v in base]
        return _per_share(inputs, trial) - market_price

    delta, info = _solve(objective, *GROWTH_SHIFT_BRACKET, label="隐含收入增速",
                         market_price=market_price, base=0.0)

    trial = copy.deepcopy(assumptions)
    trial["forecast"]["volume_growth"] = [v + delta for v in base]
    rows = engine.build_forecast(inputs, trial)["rows"]
    return {
        "unknown": "收入增速",
        "shift_delta": delta,
        "implied_volume_growth": trial["forecast"]["volume_growth"],
        "implied_revenue_cagr": _revenue_cagr(rows),
        "base_revenue_cagr": _revenue_cagr(engine.build_forecast(inputs, assumptions)["rows"]),
        "market_price": market_price,
        "solve": info,
        "note": "δ 是相对基准假设的整体平移量；隐含收入 CAGR 是按平移后的收入序列算的复合增速。"
                + multiple_root_note(info),
    }


def implied_steady_state_margin(inputs, assumptions, market_price):
    """市场中隐含的稳态毛利率：各年毛利率整体平移 δ。"""
    base = list(assumptions["forecast"]["gross_margin"])

    def objective(delta):
        trial = copy.deepcopy(assumptions)
        trial["forecast"]["gross_margin"] = [v + delta for v in base]
        return _per_share(inputs, trial) - market_price

    delta, info = _solve(objective, *MARGIN_SHIFT_BRACKET, label="隐含稳态毛利率",
                         market_price=market_price, base=0.0)

    trial = copy.deepcopy(assumptions)
    trial["forecast"]["gross_margin"] = [v + delta for v in base]
    implied = trial["forecast"]["gross_margin"]
    return {
        "unknown": "稳态毛利率",
        "shift_delta": delta,
        "implied_gross_margin": implied,
        "implied_steady_state": implied[-1],
        "base_steady_state": base[-1],
        "market_price": market_price,
        "solve": info,
        "note": "稳态取预测期最后一年；δ 是相对基准假设的整体平移量。"
                + multiple_root_note(info),
    }


def implied_ke(inputs, assumptions, market_price):
    """市场中隐含的股权成本 Ke。"""
    g = assumptions["terminal"]["growth"]
    lo = max(KE_BRACKET[0], g + 1e-4)   # 必须满足 Ke > g，否则终值没有意义
    hi = KE_BRACKET[1]

    def objective(ke):
        trial = copy.deepcopy(assumptions)
        trial["discount"]["ke"] = ke
        return _per_share(inputs, trial) - market_price

    ke, info = _solve(objective, lo, hi, label="隐含 Ke", market_price=market_price,
                      base=assumptions["discount"]["ke"])

    # 无风险利率没登记就不拆溢价 —— 自己编一个去减，等于把结论建在假数上。
    risk_free = _risk_free_rate(assumptions)
    if risk_free is None:
        premium, premium_note = None, "假设里未登记 `discount.risk_free`，不拆隐含股权风险溢价"
    else:
        premium, premium_note = ke - risk_free, f"隐含 Ke − 无风险利率 {risk_free:.2%}"

    return {
        "unknown": "股权成本 Ke",
        "implied_ke": ke,
        "base_ke": assumptions["discount"]["ke"],
        "risk_free": risk_free,
        "implied_equity_risk_premium": premium,
        "premium_note": premium_note,
        "terminal_growth": g,
        "market_price": market_price,
        "solve": info,
        "note": f"求根区间下界取 max({KE_BRACKET[0]}, g + 1e-4)，保证 Ke > g。"
                + multiple_root_note(info),
    }


def multiple_root_note(info):
    """目标函数非单调、区间里有多个解时，说清解出的是哪一个。

    不说的话，读者会以为这是唯一解 —— 而实际上「假设要挪多远」这个问题
    在非单调的区间上可能有两个答案。
    """
    if not info or not info.get("scanned") or info.get("roots_found", 1) <= 1:
        return ""
    bracket = info["bracket"]
    return (f"该区间上共有 {info['roots_found']} 个解（目标函数非单调，"
            f"每股价值先升后降），这里报的是离基准假设最近的那个，"
            f"落在 [{bracket[0]:,.4f}, {bracket[1]:,.4f}]。"
            "其余解同属数学上的解，但离基准更远。")


def _risk_free_rate(assumptions):
    """无风险利率取假设里登记的 `discount.risk_free`，没登记就返回 None。"""
    return assumptions.get("discount", {}).get("risk_free")


def reverse_valuation(inputs, assumptions, market_price=None):
    """三个未知量各解一次。任何一个无解都不影响其余两个 —— 分别报，不合并。"""
    price = market_price if market_price is not None else inputs["meta"]["latest_price"]
    results = {}
    for name, func in (
        ("revenue_growth", implied_revenue_growth),
        ("steady_state_margin", implied_steady_state_margin),
        ("ke", implied_ke),
    ):
        try:
            results[name] = {"status": "已解出", **func(inputs, assumptions, price)}
        except ReverseSolveError as error:
            results[name] = {"status": "无解", "reason": str(error), "market_price": price}
    return {
        "market_price": price,
        "unknowns": results,
        "method": "scipy.optimize.brentq，一次固定其余假设只解一个未知量",
        "note": "反向估值解出的是「市场现价隐含了什么」，不是「我们认为应该是什么」。"
                "它不构成评级或目标价。",
    }

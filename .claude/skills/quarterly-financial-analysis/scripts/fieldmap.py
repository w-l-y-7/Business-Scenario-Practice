# -*- coding: utf-8 -*-
"""EM(东财)三大报表英文列名 -> 规范化字段名 的映射。

akshare 的 stock_*_by_report_em / *_by_quarterly_em 系列返回宽表，
科目列是 EM 接口的英文键。这里统一成 fetch_statements.py 写入 JSON、
compute_ratios.py 消费的字段名，屏蔽底层列名随 akshare/EM 变化的影响。

数值单位一律为「元」（人民币原始口径），无单位列不进映射。
"""

# 利润表（按报告期 = 年初至报告期末累计；按单季度 = 单季值）
PROFIT_FIELDS = {
    "revenue_total":      "TOTAL_OPERATE_INCOME",     # 营业总收入
    "revenue":            "OPERATE_INCOME",           # 营业收入
    "operate_cost":       "OPERATE_COST",             # 营业成本
    "gross_profit":       None,                        # 派生：营业收入-营业成本
    "operate_cost_total": "TOTAL_OPERATE_COST",
    "tax_surcharges":     "OPERATE_TAX_ADD",
    "sell_expense":       "SALE_EXPENSE",
    "admin_expense":      "MANAGE_EXPENSE",
    "rd_expense":         "RESEARCH_EXPENSE",
    "finance_expense":    "FINANCE_EXPENSE",
    "asset_impair":       "ASSET_IMPAIRMENT_LOSS",
    "credit_impair":      "CREDIT_IMPAIRMENT_LOSS",
    "fairvalue_gain":     "FAIRVALUE_CHANGE_INCOME",
    "invest_income":      "INVEST_INCOME",
    "net_profit":         "NETPROFIT",                # 净利润（含少数股东）
    "net_profit_parent":  "PARENT_NETPROFIT",         # 归母净利润
    "net_profit_deduct":  "DEDUCT_PARENT_NETPROFIT",  # 扣非归母净利润
}

# 资产负债表（期末时点数）
BALANCE_FIELDS = {
    "total_assets":      "TOTAL_ASSETS",           # 资产总计
    "total_liabilities": "TOTAL_LIABILITIES",      # 负债合计
    "total_equity":      "TOTAL_EQUITY",           # 所有者权益合计
    "equity_parent":     "TOTAL_PARENT_EQUITY",    # 归母所有者权益
    "equity_minority":   "MINORITY_EQUITY",
    "liab_equity_total": "TOTAL_LIAB_EQUITY",
    "current_assets":    "TOTAL_CURRENT_ASSETS",   # 流动资产合计
    "current_liab":      "TOTAL_CURRENT_LIAB",     # 流动负债合计
    "noncurrent_assets": "TOTAL_NONCURRENT_ASSETS",
    "noncurrent_liab":   "TOTAL_NONCURRENT_LIAB",
    "cash":              "MONETARYFUNDS",          # 货币资金
    "receivables":       "NOTE_ACCOUNTS_RECE",     # 应收票据及应收账款
    "receivables_net":   "ACCOUNTS_RECE",          # 应收账款
    "inventory":         "INVENTORY",              # 存货
    "contract_liab":     "CONTRACT_LIAB",          # 合同负债
    "short_loan":        "SHORT_LOAN",             # 短期借款
    "fixed_assets":      "FIXED_ASSET",
    "intangible":        "INTANGIBLE_ASSET",
    "goodwill":          "GOODWILL",
}

# 现金流量表（按报告期 = 年初至今累计；按单季度 = 单季值）
CASHFLOW_FIELDS = {
    "ocf":    "NETCASH_OPERATE",  # 经营活动产生的现金流量净额
    "icf":    "NETCASH_INVEST",   # 投资活动产生的现金流量净额
    "fcf":    "NETCASH_FINANCE",  # 筹资活动产生的现金流量净额
    "end_cash": "END_CASH",
    "begin_cash": "BEGIN_CASH",
}

FIELD_LABELS = {
    # profit
    "revenue_total": "营业总收入",
    "revenue": "营业收入",
    "operate_cost": "营业成本",
    "gross_profit": "毛利润(营业收入-营业成本)",
    "net_profit": "净利润",
    "net_profit_parent": "归母净利润",
    "net_profit_deduct": "扣非归母净利润",
    "sell_expense": "销售费用",
    "admin_expense": "管理费用",
    "rd_expense": "研发费用",
    "finance_expense": "财务费用",
    # balance
    "total_assets": "资产总计",
    "total_liabilities": "负债合计",
    "total_equity": "所有者权益合计",
    "equity_parent": "归母所有者权益",
    "equity_minority": "少数股东权益",
    "current_assets": "流动资产合计",
    "current_liab": "流动负债合计",
    "cash": "货币资金",
    "receivables": "应收票据及应收账款",
    "inventory": "存货",
    "contract_liab": "合同负债",
    # cashflow
    "ocf": "经营活动现金流量净额",
    "icf": "投资活动现金流量净额",
    "fcf": "筹资活动现金流量净额",
    "end_cash": "期末现金及现金等价物余额",
}

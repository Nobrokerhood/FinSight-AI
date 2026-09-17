import math
import re


def _amount(value):
    if value in (None, "", "-"):
        return 0.0
    if isinstance(value, (int, float)):
        return 0.0 if isinstance(value, float) and math.isnan(value) else float(value)
    cleaned = re.sub(r"[^0-9().-]", "", str(value))
    if not cleaned:
        return 0.0
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).rstrip(":")


BALANCING_ACCOUNTS = {
    "gross profit c/o",
    "gross loss c/o",
    "gross profit",
    "gross loss",
    "net profit",
    "net loss",
    "total",
}

GROUP_ACCOUNTS = {
    "sales accounts",
    "purchase accounts",
    "direct incomes",
    "indirect incomes",
    "direct expenses",
    "indirect expenses",
}


def _row_amount(row):
    raw = row.get("raw_row", {})
    if "amount" in raw:
        return _amount(raw.get("amount"))
    return _amount(row.get("closing_balance"))


def _side(row):
    raw = row.get("raw_row", {})
    hint = _norm(raw.get("statement_side") or raw.get("section_hint"))
    if hint in ("income", "revenue"):
        return "income"
    if hint in ("expenses", "expense", "direct_expenses", "indirect_expenses"):
        return "expenses"
    return ""


def _rows_by_side(rows, side):
    return [row for row in rows or [] if _side(row) == side]


def _max_account(rows, *names):
    targets = {_norm(name) for name in names}
    matches = [
        _row_amount(row)
        for row in rows or []
        if _norm(row.get("account")) in targets
    ]
    return round(max(matches), 2) if matches else 0.0


def _find_account(rows, *names):
    targets = {_norm(name) for name in names}
    for row in rows or []:
        if _norm(row.get("account")) in targets:
            return row
    return None


def _total_row(rows):
    totals = [
        _row_amount(row)
        for row in rows or []
        if _norm(row.get("account")) == "total"
    ]
    return round(totals[-1], 2) if totals else None


def _metric(title, formula, lines, value, accounts=None, unit=None):
    return {
        "value": round(value, 2),
        "unit": unit,
        "accounts": accounts or [title],
        "calculation": {
            "title": title,
            "formula": formula,
            "lines": lines,
            "result": {"label": title, "value": round(value, 2)},
            "unit": unit,
        },
    }


def _line(label, calculation, value):
    return {
        "label": label,
        "calculation": calculation,
        "inputs": [{"label": "Amount", "value": round(value, 2)}],
        "value": round(value, 2),
    }


def summarize_profit_loss(rows):
    income_rows = _rows_by_side(rows, "income")
    expense_rows = _rows_by_side(rows, "expenses")

    income_total = _total_row(income_rows)
    sales = _max_account(income_rows, "Sales Accounts")
    direct_income = _max_account(income_rows, "Direct Incomes", "Direct Income")
    indirect_income = _max_account(income_rows, "Indirect Incomes", "Indirect Income")
    component_income = round(sales + direct_income + indirect_income, 2)
    if income_total is None:
        income_total = component_income

    explicit_net_profit = _max_account(expense_rows, "Net Profit")
    explicit_net_loss = _max_account(income_rows, "Net Loss")
    purchase = _max_account(expense_rows, "Purchase Accounts")
    direct_expense = _max_account(expense_rows, "Direct Expenses", "Direct Expense")
    indirect_expense = _max_account(expense_rows, "Indirect Expenses", "Indirect Expense")
    component_expenses = round(purchase + direct_expense + indirect_expense, 2)

    if explicit_net_profit:
        net_profit = explicit_net_profit
        total_expenses = round(income_total - net_profit, 2)
    elif explicit_net_loss:
        net_profit = -explicit_net_loss
        total_expenses = round(income_total + explicit_net_loss, 2)
    else:
        total_expenses = component_expenses
        net_profit = round(income_total - total_expenses, 2)

    return {
        "total_income": round(income_total, 2),
        "total_expenses": round(total_expenses, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin": None if income_total == 0 else round(net_profit / income_total * 100, 2),
        "expense_ratio": None if income_total == 0 else round(total_expenses / income_total * 100, 2),
        "sales_accounts": round(sales, 2),
        "direct_income": round(direct_income, 2),
        "indirect_income": round(indirect_income, 2),
        "purchase_accounts": round(purchase, 2),
        "direct_expenses": round(direct_expense, 2),
        "indirect_expenses": round(indirect_expense, 2),
        "total_assets": None,
        "total_liabilities": None,
        "equity": None,
    }


def _ranking(rows):
    ranked = []
    seen = set()
    for row in rows:
        account = str(row.get("account", "")).strip()
        norm = _norm(account)
        value = round(_row_amount(row), 2)
        if not account or value <= 0 or norm in BALANCING_ACCOUNTS or norm in GROUP_ACCOUNTS:
            continue
        key = (norm, value)
        if key in seen:
            continue
        seen.add(key)
        ranked.append({"account": account, "value": value})
    return sorted(ranked, key=lambda item: item["value"], reverse=True)[:10]


def compute_profit_loss_analytics(rows):
    summary = summarize_profit_loss(rows)

    income_lines = [
        _line("Sales Accounts", "Sales Accounts", summary["sales_accounts"]),
        _line("Direct Incomes", "Direct Incomes", summary["direct_income"]),
        _line("Indirect Incomes", "Indirect Incomes", summary["indirect_income"]),
    ]
    expense_lines = [
        _line("Purchase Accounts", "Purchase Accounts", summary["purchase_accounts"]),
        _line("Direct Expenses", "Direct Expenses", summary["direct_expenses"]),
        _line("Indirect Expenses", "Indirect Expenses", summary["indirect_expenses"]),
    ]

    total_income = summary["total_income"]
    total_expenses = summary["total_expenses"]
    net_profit = summary["net_profit"]
    profit_margin = summary["profit_margin"]
    expense_ratio = summary["expense_ratio"]

    return {
        "total_income": _metric(
            "Total Income",
            "Sales Accounts + Direct Incomes + Indirect Incomes",
            income_lines,
            total_income,
        ),
        "total_expenses": _metric(
            "Total Expenses",
            "Purchase Accounts + Direct Expenses + Indirect Expenses",
            expense_lines,
            total_expenses,
        ),
        "net_profit": _metric(
            "Net Profit",
            "Total Income - Total Expenses",
            [
                _line("Total Income", "Income total", total_income),
                _line("Total Expenses", "Expense total", total_expenses),
            ],
            net_profit,
        ),
        "profit_margin": _metric(
            "Profit Margin",
            "Net Profit / Total Income x 100",
            [
                _line("Net Profit", "Net Profit", net_profit),
                _line("Total Income", "Total Income", total_income),
            ],
            profit_margin or 0.0,
            unit="%",
        ),
        "expense_ratio": _metric(
            "Expense Ratio",
            "Total Expenses / Total Income x 100",
            [
                _line("Total Expenses", "Total Expenses", total_expenses),
                _line("Total Income", "Total Income", total_income),
            ],
            expense_ratio or 0.0,
            unit="%",
        ),
        "sales_accounts": _metric("Sales Accounts", "Sales Accounts", [income_lines[0]], summary["sales_accounts"]),
        "direct_income": _metric("Direct Income", "Direct Incomes", [income_lines[1]], summary["direct_income"]),
        "indirect_income": _metric("Indirect Income", "Indirect Incomes", [income_lines[2]], summary["indirect_income"]),
        "direct_expenses": _metric("Direct Expenses", "Direct Expenses", [expense_lines[1]], summary["direct_expenses"]),
        "indirect_expenses": _metric("Indirect Expenses", "Indirect Expenses", [expense_lines[2]], summary["indirect_expenses"]),
        "largest_income_accounts": _ranking(_rows_by_side(rows, "income")),
        "largest_expense_accounts": _ranking(_rows_by_side(rows, "expenses")),
        "largest_assets": [],
        "largest_liabilities": [],
    }

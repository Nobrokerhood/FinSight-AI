import json
import os
import re

import google.generativeai as genai


FOCUS = {
    "balance_sheet": "assets, liabilities, equity, liquidity, debt position, and financial stability",
    "trial_balance": "debit and credit balances, large balances, unusual accounts, expense concentration, and income concentration",
    "profit_and_loss": "revenue, expenses, profitability, cost increases, margin, and net profit or loss",
    "income_expense": "income sources, expense heads, surplus or deficit, cost control, and sustainability",
}

PROFIT_LOSS_TYPES = {"profit_and_loss", "income_expense"}


def _fmt(val):
    if val is None:
        return "N/A"
    try:
        return f"{float(val):,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _movement(metric):
    if not isinstance(metric, dict) or "previous_value" not in metric:
        return ""
    amount = metric.get("display_change_amount", metric.get("variance_amount"))
    percentage = metric.get("display_change_percentage", metric.get("variance_percentage"))
    label = metric.get("display_change_label")
    favorable = metric.get("is_favorable")
    if amount is None:
        return ""
    if amount == 0:
        return " It remained unchanged from the previous period."
    direction = (label or ("increased" if amount > 0 else "decreased")).lower()
    percent_text = f" ({percentage:.2f}%)" if percentage is not None else ""
    note = " This is favorable." if favorable is True else " This needs attention." if favorable is False else ""
    return f" It {direction} by {_fmt(abs(amount))}{percent_text} from the previous period.{note}"


def _top_item(analytics, key):
    items = analytics.get(key) or []
    return items[0] if items else None


def _metric_value(analytics, summary, metric_key, summary_key=None):
    metric = analytics.get(metric_key, {})
    if isinstance(metric, dict) and metric.get("value") is not None:
        return metric.get("value"), metric
    if summary_key:
        return summary.get(summary_key), {}
    return None, {}


def _profit_loss_fallback(statement_type, summary, analytics):
    income, income_metric = _metric_value(analytics, summary, "total_income", "total_income")
    expenses, expense_metric = _metric_value(analytics, summary, "total_expenses", "total_expenses")
    net_profit, profit_metric = _metric_value(analytics, summary, "net_profit", "net_profit")
    margin, margin_metric = _metric_value(analytics, summary, "profit_margin", "profit_margin")
    ratio, ratio_metric = _metric_value(analytics, summary, "expense_ratio", "expense_ratio")
    top_income = _top_item(analytics, "largest_income_accounts")
    top_expense = _top_item(analytics, "largest_expense_accounts")
    profit_label = "profit" if (net_profit or 0) >= 0 else "loss"

    return [
        f"**Executive Summary**: This is a {statement_type.replace('_', ' ')} statement. Total income is {_fmt(income)}, total expenses are {_fmt(expenses)}, and net {profit_label} is {_fmt(abs(net_profit or 0))}.",
        f"**Income Analysis**: Total income is {_fmt(income)}.{_movement(income_metric)}",
        f"**Expense Analysis**: Total expenses are {_fmt(expenses)}.{_movement(expense_metric)}",
        f"**Net Profit/Loss**: Net {profit_label} is {_fmt(abs(net_profit or 0))}.{_movement(profit_metric)}",
        f"**Profit Margin**: Profit margin is {_fmt(margin)}%.{_movement(margin_metric)} This shows how much income remains after expenses.",
        (
            f"**Highest Income Source**: The biggest income source is \"{top_income['account']}\", contributing {_fmt(top_income['value'])}."
            if top_income else "**Highest Income Source**: No income accounts found."
        ),
        (
            f"**Highest Expense**: The biggest expense is \"{top_expense['account']}\", costing {_fmt(top_expense['value'])}."
            if top_expense else "**Highest Expense**: No expense accounts found."
        ),
        f"**Expense Ratio**: Expenses are {_fmt(ratio)}% of income.{_movement(ratio_metric)}",
        "**Risk Observations**: Review expense heads with large balances and any income source that depends on one large category.",
        "**Business Recommendations**: Track major expense heads against budget and keep income collection steady for the next period.",
    ]


def _balance_fallback(statement_type, summary, analytics):
    cb_metric = analytics.get("cash_and_bank", {})
    wc_metric = analytics.get("working_capital", {})
    rec_metric = analytics.get("receivables", {})
    pay_metric = analytics.get("payables", {})
    top_income = _top_item(analytics, "largest_income_accounts")
    top_expense = _top_item(analytics, "largest_expense_accounts")

    return [
        f"**Executive Summary**: This is a {statement_type.replace('_', ' ')} statement. Total assets are {_fmt(summary.get('total_assets'))} and total equity (society's share) is {_fmt(summary.get('equity'))}.",
        f"**Liquidity Analysis**: Cash and bank balance is {_fmt(cb_metric.get('value'))}.{_movement(cb_metric)} Money owed to the society is {_fmt(rec_metric.get('value'))}.{_movement(rec_metric)} Money the society owes is {_fmt(pay_metric.get('value'))}.",
        f"**Asset Analysis**: Fixed assets are {_fmt(analytics.get('fixed_assets', {}).get('value'))}, and long-term investments are {_fmt(analytics.get('investments', {}).get('value'))}.",
        f"**Income Analysis**: Total income earned in this period is {_fmt(summary.get('total_income', 0) or 0)}.",
        f"**Expense Analysis**: Total expenses spent in this period are {_fmt(summary.get('total_expenses', 0) or 0)}.",
        (
            f"**Highest Income Source**: The biggest source of income is \"{top_income['account']}\", contributing {_fmt(top_income['value'])}."
            if top_income else "**Highest Income Source**: No income accounts found."
        ),
        (
            f"**Highest Expense**: The biggest expense is \"{top_expense['account']}\", costing {_fmt(top_expense['value'])}."
            if top_expense else "**Highest Expense**: No expense accounts found."
        ),
        f"**Risk Observations**: Net working capital is {_fmt(wc_metric.get('value'))}.{_movement(wc_metric)} Watch this to ensure day-to-day bills can be paid on time.",
        f"**Business Recommendations**: Keep an eye on payables of {_fmt(pay_metric.get('value'))} and collect receivables of {_fmt(rec_metric.get('value'))} faster to keep enough cash on hand.",
    ]


def _fallback_insights(statement_type, data):
    summary = data.get("summary", {})
    analytics = data.get("analytics", {})
    if statement_type in PROFIT_LOSS_TYPES:
        return _profit_loss_fallback(statement_type, summary, analytics)
    return _balance_fallback(statement_type, summary, analytics)


def _parse_bullets(text):
    points = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            points.append(cleaned)
    return points


MIN_VALID_POINTS = 7


def _prompt_sections(statement_type):
    if statement_type in PROFIT_LOSS_TYPES:
        return [
            "Executive Summary",
            "Income Analysis",
            "Expense Analysis",
            "Net Profit/Loss",
            "Profit Margin",
            "Highest Income Source",
            "Highest Expense",
            "Expense Ratio",
            "Risk Observations",
            "Business Recommendations",
        ], """
- Focus on income, expense control, net profit or loss, margin, and expense ratio.
- Do not mention liquidity, cash and bank, receivables, payables, assets, liabilities, or working capital unless those values are explicitly supplied for this statement type.
- For Net Profit/Loss, use only the supplied net_profit value.
- For Profit Margin and Expense Ratio, use only the supplied profit_margin and expense_ratio values.
"""
    return [
        "Executive Summary",
        "Liquidity Analysis",
        "Asset Analysis",
        "Income Analysis",
        "Expense Analysis",
        "Highest Income Source",
        "Highest Expense",
        "Risk Observations",
        "Business Recommendations",
    ], """
- Focus on liquidity, assets, liabilities, income, expenses, and working capital.
- Do not mention or evaluate Net Result.
"""


def generate_financial_insights(statement_type, financial_data):
    """Return Gemini insights; use local statement-specific fallback if Gemini is unavailable."""
    fallback = _fallback_insights(statement_type, financial_data)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Gemini generation skipped: GEMINI_API_KEY is not set")
        return fallback[:10]

    filtered_data = {
        "summary": financial_data.get("summary", {}),
        "previous_summary": financial_data.get("previous_summary", {}),
        "analytics": financial_data.get("analytics", {}),
        "previous_analytics": financial_data.get("previous_analytics", {}),
        "top_increases": financial_data.get("top_increases", []),
        "top_decreases": financial_data.get("top_decreases", []),
    }
    sections, extra_guidance = _prompt_sections(statement_type)
    section_lines = "\n".join(f"- **{section}**" for section in sections)

    prompt = f"""
You are an accountant explaining this {statement_type.replace('_', ' ')} financial statement to the
committee members of a housing society who have no accounting background. This statement belongs
to the society, not to a private business. Always refer to it as "the society" or "the society's".
Write in plain, everyday language. Avoid technical jargon, and where a technical term is unavoidable,
briefly explain it in simple words in the same sentence.

Provide exactly one bullet point for each of the following sections, in order:
{section_lines}

Guidelines:
- Return exactly 9-10 concise bullet points in total, using prefix format: '- **[Section Name]**: [Insight]'.
- Use the actual numbers from the data below wherever relevant so the reader can see the figures.
- If any analytics metric includes previous_value, variance_amount, or variance_percentage, explain the current period and the change from the previous period.
- For Highest Income Source and Highest Expense, name the specific account with the largest value from the largest_income_accounts / largest_expense_accounts lists and state its amount.
- Do not perform any mathematical calculations of your own. Use only the supplied pre-calculated values.
- Do not make assumptions or invent numbers.
- Do not include intro/outro text or markdown headers outside the bullet points.
- Keep sentences short and simple, like explaining to a friend, not writing a formal audit report.
{extra_guidance}

Pre-calculated financial data:
{json.dumps(filtered_data, default=str, indent=2)}
"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt, request_options={"timeout": 30})
        points = _parse_bullets(response.text)
        if len(points) < MIN_VALID_POINTS:
            print(f"Gemini returned too few points ({len(points)}), using fallback")
            return fallback[:10]
        return points[:10]
    except Exception as exc:
        print("Gemini generation failed, using fallback:", exc)
        return fallback[:10]

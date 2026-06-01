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


def _fallback_insights(statement_type, data):
    summary = data.get("summary", {})
    top = data.get("top_accounts", [])
    unusual = data.get("unusual_balances", [])
    largest = top[0] if top else {}
    return [
        f"Statement analyzed as {statement_type.replace('_', ' ')}.",
        f"Total income is {summary.get('total_income', 0):,.2f}.",
        f"Total expenses are {summary.get('total_expenses', 0):,.2f}.",
        f"Net result is {summary.get('net_result', 0):,.2f}.",
        f"Total assets are {summary.get('total_assets', 0):,.2f}.",
        f"Total liabilities are {summary.get('total_liabilities', 0):,.2f}.",
        (
            f"The largest mapped account is {largest.get('account')} at "
            f"{largest.get('current_value', 0):,.2f}."
            if largest
            else "No non-total account balance was available for ranking."
        ),
        f"{len(unusual)} unusual negative balance(s) were identified for review.",
        "Review the largest account movements and verify supporting ledger entries.",
        "Use a previous-period upload to add variance analysis and trend context.",
    ]


def _parse_bullets(text):
    points = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            points.append(cleaned)
    return points


def generate_financial_insights(statement_type, financial_data):
    """Return exactly ten insights, with a local fallback when Gemini is unavailable."""
    fallback = _fallback_insights(statement_type, financial_data)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback

    prompt = f"""
Analyze this {statement_type.replace('_', ' ')} financial statement.
Return exactly 10 concise bullet points and no heading.
Focus on {FOCUS.get(statement_type, 'financial performance and risks')}.
Use only the supplied data. Mention practical observations and recommendations.

Financial data:
{json.dumps(financial_data, default=str)}
"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-pro")
        points = _parse_bullets(model.generate_content(prompt).text)
        return (points + fallback)[:10]
    except Exception as exc:
        print("Gemini generation failed:", exc)
        return fallback

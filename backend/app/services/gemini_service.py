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
    analytics = data.get("analytics", {})
    
    def fmt(val):
        if val is None:
            return "N/A"
        try:
            return f"{float(val):,.2f}"
        except (ValueError, TypeError):
            return str(val)

    cb = analytics.get("cash_and_bank", {}).get("value")
    wc = analytics.get("working_capital", {}).get("value")
    rec = analytics.get("receivables", {}).get("value")
    pay = analytics.get("payables", {}).get("value")
    fa = analytics.get("fixed_assets", {}).get("value")
    inv = analytics.get("investments", {}).get("value")
    
    inc_val = summary.get("total_income", 0) or 0
    exp_val = summary.get("total_expenses", 0) or 0
    
    return [
        f"**Executive Summary**: Statement analyzed as {statement_type.replace('_', ' ').upper()} with total assets of {fmt(summary.get('total_assets'))} and total equity of {fmt(summary.get('equity'))}.",
        f"**Liquidity Analysis**: Cash & bank balance stands at {fmt(cb)} with receivables of {fmt(rec)} against payables of {fmt(pay)}.",
        f"**Asset Analysis**: Fixed assets are valued at {fmt(fa)} and long-term investments at {fmt(inv)}.",
        f"**Income Analysis**: Total recognized income of {fmt(inc_val)} is recorded during the current reporting period.",
        f"**Expense Analysis**: Total operational expenses of {fmt(exp_val)} are recognized during the period.",
        f"**Risk Observations**: The net working capital position of {fmt(wc)} should be monitored to ensure short-term solvency.",
        f"**Business Recommendations**: Monitor payables of {fmt(pay)} and optimize collection on receivables of {fmt(rec)} to secure liquidity."
    ]


def _parse_bullets(text):
    points = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            points.append(cleaned)
    return points


def generate_financial_insights(statement_type, financial_data):
    """Return exactly 7-8 insights, with a local fallback when Gemini is unavailable."""
    fallback = _fallback_insights(statement_type, financial_data)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback[:8]

    filtered_data = {
        "summary": financial_data.get("summary", {}),
        "analytics": financial_data.get("analytics", {})
    }

    prompt = f"""
You are a Chartered Accountant. Analyze this {statement_type.replace('_', ' ')} financial statement.
Provide exactly one bullet point for each of the following sections in order:
• **Executive Summary**
• **Liquidity Analysis**
• **Asset Analysis**
• **Income Analysis**
• **Expense Analysis**
• **Risk Observations**
• **Business Recommendations**

Guidelines:
- Return exactly 7-8 concise bullet points in total, using prefix format: '• **[Section Name]**: [Insight]'
- Do NOT perform any mathematical calculations. Use only the supplied pre-calculated values.
- Do NOT make assumptions, invent numbers, or include intro/outro/markdown headers.
- Use professional CA-style language.
- Avoid repeating values verbatim; focus on explaining relationships or status.
- Do NOT mention or evaluate Net Result.

Pre-calculated financial data:
{json.dumps(filtered_data, default=str, indent=2)}
"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-pro")
        points = _parse_bullets(model.generate_content(prompt).text)
        return (points + fallback)[:8]
    except Exception as exc:
        print("Gemini generation failed:", exc)
        return fallback[:8]

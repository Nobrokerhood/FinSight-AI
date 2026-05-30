import google.generativeai as genai
import os

# =====================================
# CONFIGURE GEMINI
# =====================================

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-2.5-pro"
)

# =====================================
# GENERATE AI INSIGHTS
# =====================================

def generate_financial_insights(
    statement_type="balance_sheet",
    comparison_results=None
):

    try:

        if comparison_results is None:
            comparison_results = []

        # =====================================
        # INCOME & EXPENSE STATEMENT
        # =====================================

        if statement_type == "income_expense_statement":

            prompt = f"""
Analyze this Income & Expense Statement.

Focus on:
- Total income
- Expense control
- Net surplus or deficit
- Financial sustainability
- Key risks
- Recommendations

Financial Data:
{comparison_results}
"""

        # =====================================
        # BALANCE SHEET
        # =====================================

        elif statement_type == "balance_sheet":

            prompt = f"""
Analyze this Balance Sheet.

Focus on:
- Asset growth
- Liability management
- Liquidity position
- Capital strength
- Financial risks
- Recommendations

Financial Data:
{comparison_results}
"""

        # =====================================
        # TRIAL BALANCE
        # =====================================

        elif statement_type == "trial_balance":

            prompt = f"""
Analyze this Trial Balance.

Focus on:
- Debit/Credit irregularities
- Large balances
- Suspicious movements
- Financial observations
- Recommendations

Financial Data:
{comparison_results}
"""

        # =====================================
        # PROFIT & LOSS
        # =====================================

        elif statement_type == "profit_and_loss":

            prompt = f"""
Analyze this Profit & Loss Statement.

Focus on:
- Revenue trends
- Expense trends
- Profitability
- Cost management
- Business performance
- Recommendations

Financial Data:
{comparison_results}
"""

        # =====================================
        # DEFAULT
        # =====================================

        else:

            prompt = f"""
Analyze this financial statement.

Financial Data:
{comparison_results}
"""

        # =====================================
        # GEMINI RESPONSE
        # =====================================

        response = model.generate_content(prompt)

        return {
            "status": "success",
            "ai_analysis": response.text
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }
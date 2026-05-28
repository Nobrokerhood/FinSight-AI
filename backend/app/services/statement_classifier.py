def classify_statement(columns, data):

    text = " ".join(
        [str(c).lower() for c in columns]
    )

    # =====================================
    # INCOME & EXPENSE STATEMENT
    # =====================================

    if (
        "income" in text and
        "expenses" in text
    ):

        return "income_expense_statement"

    # =====================================
    # TRIAL BALANCE
    # =====================================

    elif (
        "opening balance" in text or
        "closing balance" in text or
        (
            "debit" in text and
            "credit" in text
        )
    ):

        return "trial_balance"

    # =====================================
    # BALANCE SHEET
    # =====================================

    elif (
        "assets" in text and
        "liabilities" in text
    ):

        return "balance_sheet"

    # =====================================
    # PROFIT & LOSS
    # =====================================

    elif (
        "profit" in text or
        "loss" in text or
        "revenue" in text
    ):

        return "profit_and_loss"

    return "unknown"
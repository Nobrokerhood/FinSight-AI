def classify_statement(columns, data, report_text=""):

    title = report_text.lower()
    text = title + " " + " ".join(
        [str(c).lower() for c in columns]
    )
    text += " " + " ".join(
        str(value).lower()
        for row in data[:30]
        for value in row.values()
    )

    # =====================================
    # INCOME & EXPENSE STATEMENT
    # =====================================

    if "income and expense" in title or "income & expense" in title:
        return "income_expense"

    elif "balance sheet" in title:
        return "balance_sheet"

    elif "trial balance" in title:
        return "trial_balance"

    elif "profit & loss" in title or "profit and loss" in title:
        return "profit_and_loss"

    elif (
        "income" in text and
        "expenses" in text
    ):

        return "income_expense"

    # =====================================
    # TRIAL BALANCE
    # =====================================

    elif (
        "assets" in text and
        "liabilities" in text
    ):

        return "balance_sheet"

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
    # PROFIT & LOSS
    # =====================================

    elif (
        "profit" in text or
        "loss" in text or
        "revenue" in text
    ):

        return "profit_and_loss"

    return "unknown"

def classify_statement(columns, data):

    text = " ".join(columns).lower()

    for row in data[:30]:
        text += " ".join(
            [str(v).lower() for v in row.values()]
        )

    # Balance Sheet
    balance_keywords = [
        "balance sheet",
        "assets",
        "liabilities",
        "current assets",
        "current liabilities"
    ]

    # Profit & Loss
    pnl_keywords = [
        "profit",
        "loss",
        "revenue",
        "sales",
        "income",
        "expenses"
    ]

    # Trial Balance
    tb_keywords = [
        "trial balance",
        "debit",
        "credit"
    ]

    if any(
        keyword in text
        for keyword in balance_keywords
    ):
        return "balance_sheet"

    elif any(
        keyword in text
        for keyword in pnl_keywords
    ):
        return "profit_loss"

    elif any(
        keyword in text
        for keyword in tb_keywords
    ):
        return "trial_balance"

    return "unknown"
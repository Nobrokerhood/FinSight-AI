def analyze_income_expense(data):

    total_income = 0
    total_expense = 0

    income_accounts = []
    expense_accounts = []

    for row in data:

        account = str(
            row.get("account", "")
        ).lower()

        value = row.get(
            "year2_value", 0
        )

        try:
            amount = float(
                str(value).replace(",", "")
            )
        except:
            amount = 0

        # =========================
        # INCOME DETECTION
        # =========================
        if (
            "income" in account or
            "contribution" in account or
            "revenue" in account
        ):

            total_income += amount

            income_accounts.append({
                "account": row.get("account"),
                "amount": amount
            })

        # =========================
        # EXPENSE DETECTION
        # =========================
        elif (
            "expense" in account or
            "salary" in account or
            "maintenance" in account
        ):

            total_expense += amount

            expense_accounts.append({
                "account": row.get("account"),
                "amount": amount
            })

    # =========================
    # NET RESULT
    # =========================
    net_income = total_income - total_expense

    return {
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expense, 2),
        "net_income": round(net_income, 2),
        "income_accounts": income_accounts[:10],
        "expense_accounts": expense_accounts[:10]
    }
STATEMENT_SECTIONS = {
    "balance_sheet": ("assets", "liabilities", "equity"),
    "trial_balance": ("assets", "liabilities", "equity", "income", "expenses"),
    "profit_and_loss": (
        "revenue",
        "direct_expenses",
        "indirect_expenses",
        "net_profit_or_loss",
    ),
    "income_expense": ("income", "expenses", "surplus_or_deficit"),
}

SECTION_ALIASES = {
    "assets": "assets",
    "liabilities": "liabilities",
    "capital account": "equity",
    "equity": "equity",
    "reserves & surplus": "equity",
    "income": "income",
    "revenue": "revenue",
    "expenses": "expenses",
    "direct expenses": "direct_expenses",
    "indirect expenses": "indirect_expenses",
    "profit & loss a/c": "net_profit_or_loss",
    "surplus or deficit": "surplus_or_deficit",
}


def _allowed_section(section, statement_type):
    if statement_type == "profit_and_loss" and section == "income":
        return "revenue"
    if statement_type == "income_expense" and section in ("revenue", "direct_expenses", "indirect_expenses"):
        return "income" if section == "revenue" else "expenses"
    if statement_type == "trial_balance":
        if section in ("direct_expenses", "indirect_expenses"):
            return "expenses"
        if section == "revenue":
            return "income"
    return section


def _fallback_section(account, statement_type):
    text = account.lower()
    if any(word in text for word in ("expense", "salary", "charges paid", "cost")):
        return "expenses"
    if any(word in text for word in ("income", "revenue", "interest received", "contribution")):
        return "income" if statement_type != "profit_and_loss" else "revenue"
    if any(word in text for word in ("asset", "cash", "bank", "debtor", "receivable", "investment")):
        return "assets"
    if any(word in text for word in ("liabilit", "creditor", "payable", "loan")):
        return "liabilities"
    if any(word in text for word in ("capital", "equity", "reserve", "corpus")):
        return "equity"
    return "unknown"


def _normal_amount(row, section):
    debit_normal = section in ("assets", "expenses", "direct_expenses", "indirect_expenses")
    debit = row["debit"]
    credit = row["credit"]
    if debit or credit:
        return debit - credit if debit_normal else credit - debit
    return row["closing_balance"]


def map_statement(rows, statement_type):
    sections = {section: [] for section in STATEMENT_SECTIONS[statement_type]}
    sections["unknown"] = []
    current_section = ""

    for row in rows:
        account = row["account"].strip()
        alias = SECTION_ALIASES.get(account.lower())
        hint = row["raw_row"].get("section_hint", "")
        if alias:
            current_section = _allowed_section(alias, statement_type)

        fallback = _fallback_section(account, statement_type)
        if alias:
            section = current_section
        elif fallback != "unknown":
            section = fallback
        else:
            section = _allowed_section(hint, statement_type) if hint else current_section
        if section not in sections:
            section = "unknown"

        mapped_row = dict(row)
        mapped_row["section"] = section
        mapped_row["amount"] = round(_normal_amount(row, section), 2)
        mapped_row["is_total"] = bool(
            row["raw_row"].get("is_total")
            or alias
            or account.lower() in ("total", "net income:", "net expense:")
        )
        sections[section].append(mapped_row)

    return sections

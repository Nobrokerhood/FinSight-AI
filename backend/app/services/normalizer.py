import math
import re


def _number(value):
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


def normalize_rows(rows):
    normalized = []
    for row in rows:
        account = str(row.get("account", "")).strip()
        if not account or account == "-":
            continue
        debit = _number(row.get("closing_debit", row.get("debit", 0)))
        credit = _number(row.get("closing_credit", row.get("credit", 0)))
        amount = _number(row.get("amount"))
        closing_balance = amount if "amount" in row else debit - credit
        normalized.append({
            "account": account,
            "debit": debit,
            "credit": credit,
            "closing_balance": round(closing_balance, 2),
            "raw_row": dict(row),
        })
    return normalized

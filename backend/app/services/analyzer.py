def _all_rows(mapped):
    return [row for rows in mapped.values() for row in rows]


def _analysis_rows(mapped):
    # Some reports include a roll-up row followed by its ledger children.
    # Drop that roll-up when the following child values reconcile to it.
    result = []
    for rows in mapped.values():
        for index, row in enumerate(rows):
            if row["is_total"]:
                continue
            child_sum = 0.0
            child_count = 0
            for child in rows[index + 1:]:
                if child["is_total"]:
                    break
                child_sum += child["amount"]
                child_count += 1
                if abs(child_sum - row["amount"]) < 0.01 and row["amount"] != 0:
                    break
            if child_count >= 2 and row["amount"] and abs(child_sum - row["amount"]) < 0.01:
                continue
            result.append(row)
    return result or _all_rows(mapped)


def _total(mapped, *sections):
    rows = [row for section in sections for row in mapped.get(section, [])]
    explicit_total = [row for row in rows if row["account"].lower() == "total"]
    if explicit_total:
        return round(explicit_total[-1]["amount"], 2)
    analysis_rows = _analysis_rows({
        section: mapped.get(section, []) for section in sections
    })
    return round(sum(row["amount"] for row in analysis_rows), 2)


def build_summary(mapped):
    total_income = _total(mapped, "income", "revenue")
    total_expenses = _total(mapped, "expenses", "direct_expenses", "indirect_expenses")
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_assets": _total(mapped, "assets"),
        "total_liabilities": _total(mapped, "liabilities"),
        "net_result": round(total_income - total_expenses, 2),
    }


def _account_key(account):
    return " ".join(account.lower().split())


def _compact(row):
    return {
        "section": row["section"],
        "account": row["account"],
        "current_value": row["amount"],
    }


def single_period_results(mapped):
    return [_compact(row) for row in _analysis_rows(mapped)]


def compare_periods(current, previous):
    current_rows = {_account_key(row["account"]): row for row in _analysis_rows(current)}
    previous_rows = {_account_key(row["account"]): row for row in _analysis_rows(previous)}
    results = []
    for key in sorted(current_rows.keys() | previous_rows.keys()):
        current_row = current_rows.get(key)
        previous_row = previous_rows.get(key)
        current_value = current_row["amount"] if current_row else 0.0
        previous_value = previous_row["amount"] if previous_row else 0.0
        variance = round(current_value - previous_value, 2)
        percentage = None if previous_value == 0 else round(variance / abs(previous_value) * 100, 2)
        source = current_row or previous_row
        results.append({
            "section": source["section"],
            "account": source["account"],
            "previous_value": previous_value,
            "current_value": current_value,
            "variance_amount": variance,
            "variance_percentage": percentage,
        })
    return results


def analyze(mapped, previous_mapped=None):
    rows = _analysis_rows(mapped)
    comparison_results = (
        compare_periods(mapped, previous_mapped)
        if previous_mapped is not None
        else single_period_results(mapped)
    )
    top_accounts = sorted(
        (_compact(row) for row in rows),
        key=lambda row: abs(row["current_value"]),
        reverse=True,
    )[:10]
    unusual_balances = [
        _compact(row) for row in rows if row["amount"] < 0
    ][:10]
    top_increases = []
    top_decreases = []
    if previous_mapped is not None:
        top_increases = sorted(
            comparison_results,
            key=lambda row: row["variance_amount"],
            reverse=True,
        )[:10]
        top_decreases = sorted(
            comparison_results,
            key=lambda row: row["variance_amount"],
        )[:10]
    ai_input = {
        "summary": build_summary(mapped),
        "top_accounts": top_accounts,
        "unusual_balances": unusual_balances,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
        "financial_rows": comparison_results[:50],
    }
    return {
        "summary": ai_input["summary"],
        "top_accounts": top_accounts,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
        "comparison_results": comparison_results,
        "ai_input": ai_input,
    }

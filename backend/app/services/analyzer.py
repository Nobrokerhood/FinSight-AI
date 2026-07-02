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


import math
import re

def clean_amount(value):
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

def normalize_account_name(name):
    if name is None:
        return ""
    s = str(name).strip().lower()
    s = re.sub(r"\s+", " ", s)  # Collapse multiple spaces
    s = s.rstrip(":")            # Ignore trailing colon
    s = re.sub(r"^[^\w\s]+|[^\w\s]+$", "", s)  # Ignore leading/trailing punctuation
    return s.strip()

def extract_trial_balance_value(normalized_rows, target_name):
    target = normalize_account_name(target_name)
    for row in normalized_rows:
        acc = normalize_account_name(row.get("account", ""))
        if acc == target:
            raw = row.get("raw_row", {})
            closing_debit = raw.get("closing_debit")
            closing_credit = raw.get("closing_credit")
            if closing_debit is None and closing_credit is None:
                closing_debit = raw.get("debit")
                closing_credit = raw.get("credit")
            if closing_debit is None and closing_credit is None:
                return None
            cd = clean_amount(closing_debit)
            cc = clean_amount(closing_credit)
            
            # Use natural accounting balance
            if target in ("assets", "expenses"):
                val = cd - cc
            elif target in ("liabilities", "income", "equity", "reserves & surplus", "capital account"):
                val = cc - cd
            else:
                val = cd - cc
            return round(val, 2)
    return None

def extract_direct_value(normalized_rows, target_name):
    target = normalize_account_name(target_name)
    for row in normalized_rows:
        acc = normalize_account_name(row.get("account", ""))
        if acc == target:
            raw = row.get("raw_row", {})
            amount = raw.get("amount")
            if amount is not None:
                return round(clean_amount(amount), 2)
            return None
    return None

def get_row_value(row, statement_type, section=None):
    raw = row.get("raw_row", {})
    if statement_type == "trial_balance":
        closing_debit = raw.get("closing_debit")
        closing_credit = raw.get("closing_credit")
        if closing_debit is None and closing_credit is None:
            closing_debit = raw.get("debit")
            closing_credit = raw.get("credit")
        cd = clean_amount(closing_debit)
        cc = clean_amount(closing_credit)
        
        sec = str(section or row.get("section") or "assets").lower().strip()
        if sec == "assets":
            return cd - cc
        elif sec == "liabilities":
            return cc - cd
        elif sec == "income":
            return cc - cd
        elif sec == "expenses":
            return cd - cc
        else:
            return cd - cc
    else:
        amount = raw.get("amount")
        return clean_amount(amount) if amount is not None else 0.0

def build_summary(mapped, normalized_rows=None, statement_type="auto_detect"):
    if normalized_rows is not None:
        st = str(statement_type).lower().strip()
        total_income = None
        total_expenses = None
        total_assets = None
        total_liabilities = None
        equity_val = None

        if st == "trial_balance":
            total_income = extract_trial_balance_value(normalized_rows, "income")
            total_expenses = extract_trial_balance_value(normalized_rows, "expenses")
            total_assets = extract_trial_balance_value(normalized_rows, "assets")
            total_liabilities = extract_trial_balance_value(normalized_rows, "liabilities")
            equity_val = extract_trial_balance_value(normalized_rows, "equity")
            if equity_val is None:
                equity_val = extract_trial_balance_value(normalized_rows, "reserves & surplus")
            if equity_val is None:
                equity_val = extract_trial_balance_value(normalized_rows, "capital account")
        elif st == "balance_sheet":
            total_assets = extract_direct_value(normalized_rows, "assets")
            total_liabilities = extract_direct_value(normalized_rows, "liabilities")
            equity_val = extract_direct_value(normalized_rows, "equity")
        elif st in ("profit_and_loss", "income_expense"):
            total_income = extract_direct_value(normalized_rows, "income")
            if total_income is None:
                total_income = extract_direct_value(normalized_rows, "revenue")
            total_expenses = extract_direct_value(normalized_rows, "expenses")

        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "equity": equity_val,
        }
    
    # Fallback to old behavior if normalized_rows is None
    total_income = _total(mapped, "income", "revenue")
    total_expenses = _total(mapped, "expenses", "direct_expenses", "indirect_expenses")
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_assets": _total(mapped, "assets"),
        "total_liabilities": _total(mapped, "liabilities"),
    }

def find_row_by_name_in_rows(rows, target_name, statement_type):
    target = normalize_account_name(target_name)
    for row in rows:
        if normalize_account_name(row.get("account", "")) == target:
            return get_row_value(row, statement_type), row.get("account", "")
    return None, None

def extract_category_value(rows, category_name, section, statement_type):
    target = normalize_account_name(category_name)
    for row in rows:
        if normalize_account_name(row.get("account", "")) == target:
            raw = row.get("raw_row", {})
            cd = clean_amount(raw.get("closing_debit", raw.get("debit")))
            cc = clean_amount(raw.get("closing_credit", raw.get("credit")))
            if section in ("assets", "expenses"):
                return cd - cc
            else:
                return cc - cd
    return None

def get_cash_bank_value(rows, statement_type):
    val_cash = extract_category_value(rows, "Cash-in-hand", "assets", statement_type)
    val_bank = extract_category_value(rows, "Bank Accounts", "assets", statement_type)
    if val_cash is not None or val_bank is not None:
        return (val_cash or 0.0) + (val_bank or 0.0)
    
    cb_val = 0.0
    for row in rows:
        acc_norm = normalize_account_name(row.get("account", ""))
        if acc_norm in ("total", "assets", "liabilities", "income", "expenses"):
            continue
        if any(w in acc_norm for w in ("cash", "bank", "petty")):
            raw = row.get("raw_row", {})
            cd = clean_amount(raw.get("closing_debit", raw.get("debit")))
            cc = clean_amount(raw.get("closing_credit", raw.get("credit")))
            cb_val += (cd - cc)
    return cb_val

def deduplicate_accounts(accounts_list):
    result = []
    for item in accounts_list:
        name = item["account"]
        val = item["value"]
        norm = normalize_account_name(name)
        
        # Canonical key removing structural suffix/prefix
        clean = norm.replace("accounts", "").replace("account", "").replace("a/c", "").replace("exp", "").replace("expenses", "").strip()
        
        is_dup = False
        for existing in result:
            ext_norm = normalize_account_name(existing["account"])
            ext_clean = ext_norm.replace("accounts", "").replace("account", "").replace("a/c", "").replace("exp", "").replace("expenses", "").strip()
            
            # Match if values are close AND clean names overlap
            if abs(existing["value"] - val) < 0.01 and (clean == ext_clean or clean in ext_clean or ext_clean in clean):
                is_dup = True
                break
        if not is_dup:
            result.append(item)
    return result

def compute_analytics(mapped, current_normalized_rows, statement_type):
    if current_normalized_rows is None:
        return None
        
    st = str(statement_type).lower().strip()
    rows = current_normalized_rows
    
    # 1. Cash & Bank
    cb_val = get_cash_bank_value(rows, st)
    
    # 2. Fixed Assets
    fa_val = extract_category_value(rows, "Fixed Assets", "assets", st) or 0.0
    
    # 3. Investments
    inv_val = extract_category_value(rows, "Investments", "assets", st) or 0.0
    
    # 4. Receivables
    rec_val = extract_category_value(rows, "DUES FROM MEMBERS", "assets", st)
    if rec_val is None:
        rec_val = extract_category_value(rows, "Sundry Debtors", "assets", st) or 0.0
        
    # 5. Payables
    pay_val = extract_category_value(rows, "Sundry Creditors", "liabilities", st)
    if pay_val is None:
        pay_val = extract_category_value(rows, "Payables", "liabilities", st) or 0.0
        
    # Summary
    summary = build_summary(mapped, current_normalized_rows, statement_type)
    tot_assets = summary.get("total_assets") or 0.0
    tot_liabilities = summary.get("total_liabilities") or 0.0
    
    # 6. Current Assets
    ca_val = round(tot_assets - fa_val, 2)
    
    # 7. Current Liabilities
    cl_val = tot_liabilities
    
    # 8. Working Capital
    wc_val = round(ca_val - cl_val, 2)
    
    # Income breakdown & Expense breakdown lists (direct from mapped rows)
    expense_list = []
    for r in mapped.get("expenses", []):
        acc_norm = normalize_account_name(r["account"])
        if acc_norm != "expenses" and "diff. in opening balance" not in acc_norm:
            raw = r.get("raw_row", {})
            cd = clean_amount(raw.get("closing_debit", raw.get("debit")))
            cc = clean_amount(raw.get("closing_credit", raw.get("credit")))
            val = round(cd - cc, 2)
            if val > 0:
                expense_list.append({"account": r["account"], "value": val})
            
    sorted_expense = sorted(expense_list, key=lambda x: x["value"], reverse=True)
    largest_expense_accounts = deduplicate_accounts(sorted_expense)[:10]

    income_list = []
    for r in mapped.get("income", []):
        acc_norm = normalize_account_name(r["account"])
        if acc_norm != "income" and "diff. in opening balance" not in acc_norm:
            raw = r.get("raw_row", {})
            cd = clean_amount(raw.get("closing_debit", raw.get("debit")))
            cc = clean_amount(raw.get("closing_credit", raw.get("credit")))
            val = round(cc - cd, 2)
            if val > 0:
                income_list.append({"account": r["account"], "value": val})
            
    sorted_income = sorted(income_list, key=lambda x: x["value"], reverse=True)
    largest_income_accounts = deduplicate_accounts(sorted_income)[:10]

    asset_list = []
    for r in mapped.get("assets", []):
        acc_norm = normalize_account_name(r["account"])
        if acc_norm != "assets" and "diff. in opening balance" not in acc_norm:
            raw = r.get("raw_row", {})
            cd = clean_amount(raw.get("closing_debit", raw.get("debit")))
            cc = clean_amount(raw.get("closing_credit", raw.get("credit")))
            val = round(cd - cc, 2)
            if val > 0:
                asset_list.append({"account": r["account"], "value": val})
            
    sorted_assets = sorted(asset_list, key=lambda x: x["value"], reverse=True)
    largest_asset_accounts = deduplicate_accounts(sorted_assets)[:10]

    liability_list = []
    for r in mapped.get("liabilities", []):
        acc_norm = normalize_account_name(r["account"])
        if acc_norm != "liabilities" and "diff. in opening balance" not in acc_norm:
            raw = r.get("raw_row", {})
            cd = clean_amount(raw.get("closing_debit", raw.get("debit")))
            cc = clean_amount(raw.get("closing_credit", raw.get("credit")))
            val = round(cc - cd, 2)
            if val > 0:
                liability_list.append({"account": r["account"], "value": val})
            
    sorted_liabs = sorted(liability_list, key=lambda x: x["value"], reverse=True)
    largest_liability_accounts = deduplicate_accounts(sorted_liabs)[:10]

    return {
        "cash_and_bank": {"value": round(cb_val, 2), "accounts": ["Cash-in-hand", "Bank Accounts"]},
        "fixed_assets": {"value": round(fa_val, 2), "accounts": ["Fixed Assets"]},
        "investments": {"value": round(inv_val, 2), "accounts": ["Investments"]},
        "receivables": {"value": round(rec_val, 2), "accounts": ["DUES FROM MEMBERS"]},
        "payables": {"value": round(pay_val, 2), "accounts": ["Sundry Creditors"]},
        "current_assets": {"value": round(ca_val, 2), "accounts": ["Current Assets"]},
        "current_liabilities": {"value": round(cl_val, 2), "accounts": ["Current Liabilities"]},
        "working_capital": {"value": round(wc_val, 2), "accounts": ["Working Capital"]},
        "largest_income_accounts": largest_income_accounts,
        "largest_expense_accounts": largest_expense_accounts,
        "largest_assets": largest_asset_accounts,
        "largest_liabilities": largest_liability_accounts
    }

def get_warnings(mapped, current_normalized_rows, statement_type, summary, analytics):
    warnings = []
    if current_normalized_rows is None:
        return warnings
        
    st = str(statement_type).lower().strip()
    
    # 1. Negative Cash/Bank/Receivables
    for row in current_normalized_rows:
        raw = row.get("raw_row", {})
        closing_debit = clean_amount(raw.get("closing_debit", raw.get("debit")))
        closing_credit = clean_amount(raw.get("closing_credit", raw.get("credit")))
        acc_name = row.get("account", "")
        acc_norm = normalize_account_name(acc_name)
        
        if any(w in acc_norm for w in ("cash", "petty")):
            if closing_credit > closing_debit:
                warnings.append(f"Negative cash detected in account: {acc_name}")
        elif "bank" in acc_norm:
            if closing_credit > closing_debit and not any(w in acc_norm for w in ("loan", "od", "overdraft")):
                warnings.append(f"Negative bank balance (overdraft) detected in account: {acc_name}")
        elif any(w in acc_norm for w in ("receivable", "debtor", "dues from")):
            if closing_credit > closing_debit:
                warnings.append(f"Negative receivable balance detected in account: {acc_name}")

    # 2. Large Creditor / Debtor Concentration
    tot_assets = summary.get("total_assets", 0) or 0
    tot_liabilities = summary.get("total_liabilities", 0) or 0
    
    if tot_liabilities > 0:
        for r in mapped.get("liabilities", []):
            raw = r.get("raw_row", {})
            val = max(clean_amount(raw.get("closing_debit", raw.get("debit"))), clean_amount(raw.get("closing_credit", raw.get("credit"))))
            if normalize_account_name(r["account"]) == "liabilities":
                continue
            if val / tot_liabilities > 0.3:
                pct = (val / tot_liabilities) * 100
                warnings.append(f"Large creditor concentration: {r['account']} represents {pct:.1f}% of liabilities")
                
    if tot_assets > 0:
        for r in mapped.get("assets", []):
            raw = r.get("raw_row", {})
            val = max(clean_amount(raw.get("closing_debit", raw.get("debit"))), clean_amount(raw.get("closing_credit", raw.get("credit"))))
            if normalize_account_name(r["account"]) == "assets":
                continue
            if val / tot_assets > 0.3:
                pct = (val / tot_assets) * 100
                warnings.append(f"Large debtor concentration: {r['account']} represents {pct:.1f}% of assets")

    # 3. Income is Zero
    tot_income = summary.get("total_income", 0) or 0
    if tot_income == 0:
        warnings.append("Income is zero")
        
    # 4. Expenses Exceed Income
    tot_expenses = summary.get("total_expenses", 0) or 0
    if tot_expenses > tot_income:
        warnings.append("Expenses exceed income")
        
    # 5. Missing Section
    from app.services.statement_mapper import STATEMENT_SECTIONS
    expected_sections = STATEMENT_SECTIONS.get(st, [])
    for sec in expected_sections:
        if not mapped.get(sec):
            warnings.append(f"Missing section: {sec}")

    # 6. Duplicate account names
    seen_names = set()
    dup_names = set()
    for row in current_normalized_rows:
        name = row.get("account")
        if name:
            norm = normalize_account_name(name)
            if norm in seen_names:
                dup_names.add(name)
            seen_names.add(norm)
    for dup in sorted(list(dup_names)):
        warnings.append(f"Duplicate account name detected: {dup}")
        
    return warnings

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

def analyze(mapped, previous_mapped=None, current_normalized_rows=None, statement_type="auto_detect"):
    rows = _analysis_rows(mapped)
    comparison_results = (
        compare_periods(mapped, previous_mapped)
        if previous_mapped is not None
        else single_period_results(mapped)
    )
    
    summary = build_summary(mapped, current_normalized_rows, statement_type)
    analytics = compute_analytics(mapped, current_normalized_rows, statement_type)
    warnings = get_warnings(mapped, current_normalized_rows, statement_type, summary, analytics)
    
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
        "summary": summary,
        "analytics": analytics,
        "warnings": warnings,
        "top_accounts": top_accounts,
        "unusual_balances": unusual_balances,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
        "financial_rows": comparison_results[:50],
    }
    return {
        "summary": summary,
        "analytics": analytics,
        "warnings": warnings,
        "top_accounts": top_accounts,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
        "comparison_results": comparison_results,
        "ai_input": ai_input,
    }

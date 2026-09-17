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

def category_calculation(rows, category_name, section, result_label=None):
    target = normalize_account_name(category_name)
    debit_normal = section in ("assets", "expenses")
    formula = "Closing Debit - Closing Credit" if debit_normal else "Closing Credit - Closing Debit"
    for row in rows:
        if normalize_account_name(row.get("account", "")) == target:
            raw = row.get("raw_row", {})
            debit = clean_amount(raw.get("closing_debit", raw.get("debit")))
            credit = clean_amount(raw.get("closing_credit", raw.get("credit")))
            value = debit - credit if debit_normal else credit - debit
            return {
                "title": result_label or category_name,
                "formula": formula,
                "lines": [{
                    "label": row.get("account", category_name),
                    "calculation": f"Closing {'Debit' if debit_normal else 'Credit'} - Closing {'Credit' if debit_normal else 'Debit'}",
                    "inputs": [
                        {"label": "Closing Debit", "value": round(debit, 2)},
                        {"label": "Closing Credit", "value": round(credit, 2)},
                    ],
                    "value": round(value, 2),
                }],
                "result": {"label": result_label or category_name, "value": round(value, 2)},
            }
    return {
        "title": result_label or category_name,
        "formula": formula,
        "lines": [{
            "label": category_name,
            "calculation": "Account not found, treated as zero",
            "inputs": [],
            "value": 0.0,
        }],
        "result": {"label": result_label or category_name, "value": 0.0},
    }

def combined_calculation(title, formula, lines, value):
    return {
        "title": title,
        "formula": formula,
        "lines": lines,
        "result": {"label": title, "value": round(value, 2)},
    }

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
    cash_calc = category_calculation(rows, "Cash-in-hand", "assets", "Cash-in-hand")
    bank_calc = category_calculation(rows, "Bank Accounts", "assets", "Bank Accounts")
    cb_val = get_cash_bank_value(rows, st)
    cb_calc = combined_calculation(
        "Cash & Bank",
        "Cash-in-hand + Bank Accounts",
        [
            {
                "label": "Cash-in-hand",
                "calculation": cash_calc["formula"],
                "inputs": cash_calc["lines"][0]["inputs"],
                "value": cash_calc["result"]["value"],
            },
            {
                "label": "Bank Accounts",
                "calculation": bank_calc["formula"],
                "inputs": bank_calc["lines"][0]["inputs"],
                "value": bank_calc["result"]["value"],
            },
        ],
        cb_val,
    )
    
    # 2. Fixed Assets
    fa_val = extract_category_value(rows, "Fixed Assets", "assets", st) or 0.0
    fa_calc = category_calculation(rows, "Fixed Assets", "assets", "Fixed Assets")
    
    # 3. Investments
    inv_val = extract_category_value(rows, "Investments", "assets", st) or 0.0
    inv_calc = category_calculation(rows, "Investments", "assets", "Investments")
    
    # 4. Receivables
    rec_account = "DUES FROM MEMBERS"
    rec_val = extract_category_value(rows, "DUES FROM MEMBERS", "assets", st)
    if rec_val is None:
        rec_account = "Sundry Debtors"
        rec_val = extract_category_value(rows, "Sundry Debtors", "assets", st) or 0.0
    rec_calc = category_calculation(rows, rec_account, "assets", "Receivables")
        
    # 5. Payables
    pay_account = "Sundry Creditors"
    pay_val = extract_category_value(rows, "Sundry Creditors", "liabilities", st)
    if pay_val is None:
        pay_account = "Payables"
        pay_val = extract_category_value(rows, "Payables", "liabilities", st) or 0.0
    pay_calc = category_calculation(rows, pay_account, "liabilities", "Payables")
        
    # Summary
    summary = build_summary(mapped, current_normalized_rows, statement_type)
    tot_assets = summary.get("total_assets") or 0.0
    tot_liabilities = summary.get("total_liabilities") or 0.0
    total_assets_calc = category_calculation(rows, "Assets", "assets", "Total Assets")
    total_liabilities_calc = category_calculation(rows, "Liabilities", "liabilities", "Total Liabilities")
    
    # 6. Current Assets
    ca_val = round(tot_assets - fa_val, 2)
    ca_calc = combined_calculation(
        "Current Assets",
        "Total Assets - Fixed Assets",
        [
            {
                "label": "Total Assets",
                "calculation": total_assets_calc["formula"],
                "inputs": total_assets_calc["lines"][0]["inputs"],
                "value": round(tot_assets, 2),
            },
            {"label": "Fixed Assets", "calculation": fa_calc["formula"], "inputs": fa_calc["lines"][0]["inputs"], "value": round(fa_val, 2)},
        ],
        ca_val,
    )
    
    # 7. Current Liabilities
    cl_val = tot_liabilities
    cl_calc = combined_calculation(
        "Current Liabilities",
        "Total Liabilities",
        [
            {
                "label": "Total Liabilities",
                "calculation": total_liabilities_calc["formula"],
                "inputs": total_liabilities_calc["lines"][0]["inputs"],
                "value": round(cl_val, 2),
            },
        ],
        cl_val,
    )
    
    # 8. Working Capital
    wc_val = round(ca_val - cl_val, 2)
    wc_calc = combined_calculation(
        "Working Capital",
        "Current Assets - Current Liabilities",
        [
            {"label": "Current Assets", "calculation": "Total Assets - Fixed Assets", "inputs": [], "value": round(ca_val, 2)},
            {"label": "Current Liabilities", "calculation": "Total Liabilities", "inputs": [], "value": round(cl_val, 2)},
        ],
        wc_val,
    )
    
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
        "cash_and_bank": {"value": round(cb_val, 2), "accounts": ["Cash-in-hand", "Bank Accounts"], "calculation": cb_calc},
        "fixed_assets": {"value": round(fa_val, 2), "accounts": ["Fixed Assets"], "calculation": fa_calc},
        "investments": {"value": round(inv_val, 2), "accounts": ["Investments"], "calculation": inv_calc},
        "receivables": {"value": round(rec_val, 2), "accounts": [rec_account], "calculation": rec_calc},
        "payables": {"value": round(pay_val, 2), "accounts": [pay_account], "calculation": pay_calc},
        "current_assets": {"value": round(ca_val, 2), "accounts": ["Current Assets"], "calculation": ca_calc},
        "current_liabilities": {"value": round(cl_val, 2), "accounts": ["Current Liabilities"], "calculation": cl_calc},
        "working_capital": {"value": round(wc_val, 2), "accounts": ["Working Capital"], "calculation": wc_calc},
        "largest_income_accounts": largest_income_accounts,
        "largest_expense_accounts": largest_expense_accounts,
        "largest_assets": largest_asset_accounts,
        "largest_liabilities": largest_liability_accounts
    }

def add_analytics_comparison(current_analytics, previous_analytics):
    if not current_analytics or not previous_analytics:
        return current_analytics

    metric_keys = (
        "cash_and_bank",
        "fixed_assets",
        "investments",
        "receivables",
        "payables",
        "current_assets",
        "current_liabilities",
        "working_capital",
    )
    lower_is_better = {"receivables", "payables", "current_liabilities"}
    higher_is_better = {"cash_and_bank", "current_assets", "working_capital"}
    for key in metric_keys:
        current_metric = current_analytics.get(key)
        previous_metric = previous_analytics.get(key)
        if not isinstance(current_metric, dict) or not isinstance(previous_metric, dict):
            continue

        current_value = current_metric.get("value")
        previous_value = previous_metric.get("value")
        if current_value is None or previous_value is None:
            continue

        variance = round(current_value - previous_value, 2)
        variance_percentage = None if previous_value == 0 else round(variance / abs(previous_value) * 100, 2)
        if key in lower_is_better:
            display_amount = round(previous_value - current_value, 2)
            display_percentage = None if previous_value == 0 else round(display_amount / abs(previous_value) * 100, 2)
            display_label = "Reduced" if display_amount > 0 else "Increased" if display_amount < 0 else "No change"
            is_favorable = display_amount >= 0
        elif key in higher_is_better:
            display_amount = variance
            display_percentage = variance_percentage
            display_label = "Increased" if display_amount > 0 else "Decreased" if display_amount < 0 else "No change"
            is_favorable = display_amount >= 0
        else:
            display_amount = variance
            display_percentage = variance_percentage
            display_label = "Changed" if display_amount != 0 else "No change"
            is_favorable = None

        current_metric["previous_value"] = round(previous_value, 2)
        current_metric["variance_amount"] = variance
        current_metric["variance_percentage"] = variance_percentage
        current_metric["display_change_amount"] = round(display_amount, 2)
        current_metric["display_change_percentage"] = display_percentage
        current_metric["display_change_label"] = display_label
        current_metric["is_favorable"] = is_favorable
        current_metric["previous_calculation"] = previous_metric.get("calculation")
        current_metric["comparison_calculation"] = {
            "title": f"{current_metric.get('calculation', {}).get('title', key)} Movement",
            "formula": "Current Value - Previous Value",
            "lines": [
                {"label": "Previous Value", "calculation": "Previous period result", "inputs": [], "value": round(previous_value, 2)},
                {"label": "Current Value", "calculation": "Current period result", "inputs": [], "value": round(current_value, 2)},
            ],
            "result": {"label": "Variance", "value": variance},
            "variance_percentage": current_metric["variance_percentage"],
            "display_change_amount": current_metric["display_change_amount"],
            "display_change_percentage": current_metric["display_change_percentage"],
            "display_change_label": current_metric["display_change_label"],
            "is_favorable": current_metric["is_favorable"],
        }

    return current_analytics

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

def analyze(
    mapped,
    previous_mapped=None,
    current_normalized_rows=None,
    statement_type="auto_detect",
    previous_normalized_rows=None,
):
    rows = _analysis_rows(mapped)
    comparison_results = (
        compare_periods(mapped, previous_mapped)
        if previous_mapped is not None
        else single_period_results(mapped)
    )
    
    summary = build_summary(mapped, current_normalized_rows, statement_type)
    analytics = compute_analytics(mapped, current_normalized_rows, statement_type)
    previous_summary = None
    previous_analytics = None
    if previous_mapped is not None and previous_normalized_rows is not None:
        previous_summary = build_summary(previous_mapped, previous_normalized_rows, statement_type)
        previous_analytics = compute_analytics(previous_mapped, previous_normalized_rows, statement_type)
        analytics = add_analytics_comparison(analytics, previous_analytics)
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
        "previous_summary": previous_summary,
        "analytics": analytics,
        "previous_analytics": previous_analytics,
        "warnings": warnings,
        "top_accounts": top_accounts,
        "unusual_balances": unusual_balances,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
        "financial_rows": comparison_results[:50],
    }
    return {
        "summary": summary,
        "previous_summary": previous_summary,
        "analytics": analytics,
        "previous_analytics": previous_analytics,
        "warnings": warnings,
        "top_accounts": top_accounts,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
        "comparison_results": comparison_results,
        "ai_input": ai_input,
    }

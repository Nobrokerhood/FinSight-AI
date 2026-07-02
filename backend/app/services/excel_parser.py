import csv
from pathlib import Path

import pandas as pd


HEADER_KEYWORDS = (
    "account head",
    "particular",
    "ledger name",
    "ledger",
    "account",
)


def _is_account_header(value):
    text = _lower(value)
    return (
        text in ("account", "ledger", "ledger name", "account head", "particular", "particulars")
        or "account head" in text
        or "ledger name" in text
    )


def _text(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _lower(value):
    return _text(value).lower()


def _read_rows(file_path):
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        with open(file_path, newline="", encoding="utf-8-sig") as handle:
            return list(csv.reader(handle))

    frame = pd.read_excel(file_path, header=None, sheet_name=0)
    return frame.where(pd.notna(frame), None).values.tolist()


def _find_header_row(rows):
    best_index = None
    best_score = 0
    for index, row in enumerate(rows[:30]):
        cells = [_lower(value) for value in row]
        account_score = sum(_is_account_header(cell) for cell in cells)
        if not account_score:
            continue
        score = account_score * 3
        score += sum("closing balance" in cell for cell in cells)
        score += sum(cell in ("debit", "credit", "amount") for cell in cells)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index if best_score >= 2 else None


def _find_account_columns(rows, header_index):
    header = [_lower(value) for value in rows[header_index]]
    columns = [
        index
        for index, value in enumerate(header)
        if _is_account_header(value)
    ]

    if not columns:
        return []

    # Trial balances commonly put "Account Head" over two columns and the
    # useful account name in a lower sub-header.
    next_row = rows[header_index + 1] if header_index + 1 < len(rows) else []
    adjusted = []
    for column in columns:
        candidate = column
        for index in range(column, min(column + 3, len(next_row))):
            if _lower(next_row[index]) in ("account", "ledger", "ledger name"):
                candidate = index
        if candidate not in adjusted:
            adjusted.append(candidate)
    return adjusted


def _column_role(rows, header_index, column):
    labels = []
    for index in range(max(0, header_index - 1), min(len(rows), header_index + 3)):
        if column < len(rows[index]):
            val = rows[index][column]
            # Propagate merged group headers leftwards if current cell is empty/NaN
            if (val is None or pd.isna(val) or str(val).strip() == "") and column > 0:
                for left_col in range(column - 1, -1, -1):
                    left_val = rows[index][left_col]
                    if left_val is not None and not pd.isna(left_val) and str(left_val).strip() != "":
                        val = left_val
                        break
            labels.append(_lower(val))
    text = " ".join(labels)
    if "closing" in text and "debit" in text:
        return "closing_debit"
    if "closing" in text and "credit" in text:
        return "closing_credit"
    if "debit" in text:
        return "debit"
    if "credit" in text:
        return "credit"
    if "amount" in text or "closing balance" in text:
        return "amount"
    return ""



def _section_hint(rows, header_index, start, end):
    for row_index in range(header_index - 1, -1, -1):
        text = " ".join(_lower(value) for value in rows[row_index][start:end])
        if "expense" in text:
            return "expenses"
        if "income" in text or "revenue" in text:
            return "income"
    return ""


def _parse_tabular(rows, header_index):
    account_columns = _find_account_columns(rows, header_index)
    parsed = []
    data_start = header_index + 1
    if data_start < len(rows):
        next_text = " ".join(_lower(value) for value in rows[data_start])
        if "debit" in next_text or "credit" in next_text:
            data_start += 1

    for position, account_column in enumerate(account_columns):
        start = account_column
        end = (
            account_columns[position + 1]
            if position + 1 < len(account_columns)
            else len(rows[header_index])
        )
        roles = {
            column: _column_role(rows, header_index, column)
            for column in range(start + 1, end)
        }
        hint = _section_hint(rows, header_index, start, end)

        for row_number, row in enumerate(rows[data_start:], start=data_start + 1):
            account = _text(row[account_column]) if account_column < len(row) else ""
            if not account:
                continue
            raw = {
                "account": account,
                "section_hint": hint,
                "source_row": row_number,
            }
            for column, role in roles.items():
                if role and column < len(row):
                    raw[role] = row[column]
            parsed.append(raw)
    return parsed


def _parse_sectioned(rows):
    parsed = []
    section_hint = ""
    for row_number, row in enumerate(rows, start=1):
        account = _text(row[0]) if row else ""
        if not account:
            continue
        lowered = account.lower()
        if lowered == "assets":
            section_hint = "assets"
            if len(row) > 1 and any(x is not None and not pd.isna(x) and str(x).strip() for x in row[1:]):
                pass
            else:
                continue
        if lowered == "liabilities":
            section_hint = "liabilities"
            if len(row) > 1 and any(x is not None and not pd.isna(x) and str(x).strip() for x in row[1:]):
                pass
            else:
                continue
        if lowered in ("balance sheet", "profit & loss", "profit and loss"):
            continue
        if lowered == "total":
            parsed.append({
                "account": account,
                "amount": row[1] if len(row) > 1 else 0,
                "section_hint": section_hint,
                "source_row": row_number,
                "is_total": True,
            })
            continue
        if len(row) < 2:
            continue
        parsed.append({
            "account": account,
            "amount": row[1],
            "section_hint": section_hint,
            "source_row": row_number,
        })
    return parsed


def parse_excel(file_path):
    """Read the first worksheet and emit layout-neutral financial rows."""
    try:
        rows = _read_rows(file_path)
        header_index = _find_header_row(rows)
        data = (
            _parse_tabular(rows, header_index)
            if header_index is not None
            else _parse_sectioned(rows)
        )
        return {
            "status": "success",
            "columns": rows[header_index] if header_index is not None else [],
            "report_text": " ".join(
                _text(value) for row in rows[:6] for value in row
            ),
            "total_rows": len(data),
            "header_row": header_index + 1 if header_index is not None else None,
            "data": data,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": []}

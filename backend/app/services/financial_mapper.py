def map_financial_structure(cleaned_data):

    mapped_data = {
        "assets": [],
        "liabilities": [],
        "equity": [],
        "revenue": [],
        "expenses": [],
        "unknown": []
    }

    current_section = "unknown"

    for row in cleaned_data:

        row_text = " ".join(
            [str(v).lower() for v in row.values()]
        )

        # Detect Sections
        if "asset" in row_text:
            current_section = "assets"
            continue

        elif "liabilit" in row_text:
            current_section = "liabilities"
            continue

        elif "equity" in row_text:
            current_section = "equity"
            continue

        elif (
            "revenue" in row_text
            or "sales" in row_text
            or "income" in row_text
        ):
            current_section = "revenue"
            continue

        elif (
            "expense" in row_text
            or "salary" in row_text
            or "cost" in row_text
        ):
            current_section = "expenses"
            continue

        # Store row in detected section
        mapped_data[current_section].append(row)

    return mapped_data
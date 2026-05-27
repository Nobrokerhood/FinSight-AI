def calculate_growth(old_value, new_value):

    try:

        old_value = float(old_value)
        new_value = float(new_value)

        if old_value == 0:
            return 0

        growth = (
            (new_value - old_value) / abs(old_value)
        ) * 100

        return round(growth, 2)

    except:
        return 0


def compare_financial_data(mapped_data, year_mapping):

    comparison_results = []

    # Detect year columns
    year_columns = list(year_mapping.keys())

    if len(year_columns) < 2:
        return comparison_results

    year1_col = year_columns[0]
    year2_col = year_columns[1]

    # Compare all sections
    for section, rows in mapped_data.items():

        for row in rows:

            try:

                account_name = list(row.values())[0]

                old_value = row.get(year1_col, 0)
                new_value = row.get(year2_col, 0)

                growth_percent = calculate_growth(
                    old_value,
                    new_value
                )

                comparison_results.append({
                    "section": section,
                    "account": account_name,
                    "year1_value": old_value,
                    "year2_value": new_value,
                    "growth_percent": growth_percent
                })

            except:
                continue

    return comparison_results
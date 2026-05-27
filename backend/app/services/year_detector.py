import re

def detect_year_columns(cleaned_data):

    detected_years = {}

    for row in cleaned_data[:20]:

        values = list(row.values())

        row_text = " ".join(
            [str(v) for v in values]
        )

        # Find years
        years = re.findall(r'20\d{2}', row_text)

        if len(years) >= 2:

            keys = list(row.keys())

            if len(keys) >= 3:

                detected_years[keys[1]] = years[0]
                detected_years[keys[2]] = years[1]

                return detected_years

        # Detect financial periods
        elif "2024" in row_text and "2025" in row_text:

            keys = list(row.keys())

            if len(keys) >= 3:

                detected_years[keys[1]] = "2024"
                detected_years[keys[2]] = "2025"

                return detected_years

    return detected_years
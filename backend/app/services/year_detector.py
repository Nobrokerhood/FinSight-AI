import re


def detect_year_columns(cleaned_data):

    detected_years = {}

    if not cleaned_data:
        return detected_years

    first_row = cleaned_data[0]

    for column in first_row.keys():

        col = str(column)

        year_match = re.search(r'20\d{2}', col)

        if year_match:
            detected_years[column] = year_match.group()

    return detected_years
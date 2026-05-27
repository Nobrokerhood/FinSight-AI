import pandas as pd

def clean_financial_data(data):

    cleaned_data = []

    for row in data:

        cleaned_row = {}

        for key, value in row.items():

            # Skip unnamed empty columns
            if "Unnamed" in str(key) and value == "":
                continue

            # Clean value
            if pd.isna(value):
                value = ""

            cleaned_row[str(key).strip()] = str(value).strip()

        # Skip completely empty rows
        if any(v != "" for v in cleaned_row.values()):
            cleaned_data.append(cleaned_row)

    return cleaned_data
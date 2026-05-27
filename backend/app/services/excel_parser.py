import pandas as pd

def parse_excel(file_path):

    try:
        # Read Excel file
        df = pd.read_excel(file_path)

        # Convert dataframe to dictionary
        data = df.fillna("").to_dict(orient="records")

        return {
            "status": "success",
            "columns": list(df.columns),
            "total_rows": len(df),
            "data": data
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
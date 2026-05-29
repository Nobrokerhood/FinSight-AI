import pandas as pd

def parse_excel(file_path):

    try:

        raw_df = pd.read_excel(
            file_path,
            header=None
        )

        header_row = 0

        for i in range(min(20, len(raw_df))):

            row_text = " ".join(
                raw_df.iloc[i]
                .fillna("")
                .astype(str)
                .tolist()
            ).lower()

            if "account head" in row_text:

                header_row = i
                break

        df = pd.read_excel(
            file_path,
            header=header_row
        )

        data = (
            df.fillna("")
            .to_dict(orient="records")
        )

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
import pdfplumber

def parse_pdf(file_path):

    try:

        extracted_text = ""

        with pdfplumber.open(file_path) as pdf:

            for page in pdf.pages:
                text = page.extract_text()

                if text:
                    extracted_text += text + "\n"

        return {
            "status": "success",
            "text_preview": extracted_text[:5000]
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }
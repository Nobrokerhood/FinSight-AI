from fastapi import APIRouter, UploadFile, File
import os
import shutil

from app.services.excel_parser import parse_excel
from app.services.statement_classifier import classify_statement
from app.services.financial_cleaner import clean_financial_data
from app.services.pdf_parser import parse_pdf
from app.services.financial_mapper import map_financial_structure
from app.services.year_detector import detect_year_columns
from app.services.comparison_engine import compare_financial_data
from app.services.gemini_service import generate_financial_insights
from app.services.income_expense_analyzer import analyze_income_expense

router = APIRouter()

UPLOAD_FOLDER = "uploads"

# Create uploads folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    # =========================
    # SAVE FILE
    # =========================
    file_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # =========================
    # BASE RESPONSE
    # =========================
    response = {
        "status": "success",
        "filename": file.filename,
        "content_type": file.content_type,
        "saved_path": file_path
    }

    # ====================================================
    # EXCEL / CSV PROCESSING
    # ====================================================
    if file.filename.endswith((".xlsx", ".xls", ".csv")):

        # Parse Excel
        excel_data = parse_excel(file_path)

        # Check parsing status
        if excel_data["status"] == "success":

            # =========================
            # CLEAN DATA
            # =========================
            cleaned_data = clean_financial_data(
                excel_data["data"]
            )

            # =========================
            # DETECT STATEMENT TYPE
            # =========================
            statement_type = classify_statement(
                excel_data["columns"],
                cleaned_data
            )

            # =========================
            # DETECT YEAR COLUMNS
            # =========================
            year_mapping = detect_year_columns(
                cleaned_data
            )

            # =========================
            # MAP FINANCIAL STRUCTURE
            # =========================
            mapped_data = map_financial_structure(
                cleaned_data
            )

            # =========================
            # COMPARATIVE ANALYSIS
            # =========================
            comparison_results = compare_financial_data(
                mapped_data,
                year_mapping
            )

            # =========================
            # FINAL RESPONSE
            # =========================
            response["summary"] = {
                "statement_type": statement_type,
                "year_mapping": year_mapping,
                "total_sections": {
                    "assets": len(mapped_data["assets"]),
                    "liabilities": len(mapped_data["liabilities"]),
                    "equity": len(mapped_data["equity"]),
                    "revenue": len(mapped_data["revenue"]),
                    "expenses": len(mapped_data["expenses"]),
                    "unknown": len(mapped_data["unknown"])
                }
            }

            response["comparison_results"] = (
                comparison_results[:10]
            )
            # =====================================
            # INCOME & EXPENSE ANALYSIS
            # =====================================

            if statement_type == "income_expense_statement":

                income_expense_summary = (
                    analyze_income_expense(
                    comparison_results))
                response[
                    "income_expense_summary"
                 ] = income_expense_summary

            # Generate AI Insights
            ai_response = generate_financial_insights(
                comparison_results
                )
            response["ai_insights"] = ai_response

        else:

            response["error"] = (
                "Excel parsing failed"
            )

    # ====================================================
    # PDF PROCESSING
    # ====================================================
    elif file.filename.endswith(".pdf"):

        pdf_data = parse_pdf(file_path)

        response["pdf_preview"] = pdf_data

    # ====================================================
    # IMAGE PROCESSING
    # ====================================================
    elif file.filename.endswith(
        (".png", ".jpg", ".jpeg")
    ):

        response["image_status"] = "success"

        response["message"] = (
            "OCR engine will be added next"
        )

    # ====================================================
    # UNSUPPORTED FILES
    # ====================================================
    else:

        response["status"] = "error"

        response["message"] = (
            "Unsupported file type"
        )

    return response
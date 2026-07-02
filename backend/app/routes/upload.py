import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends, Request

from app.services.analyzer import analyze
from app.services.excel_parser import parse_excel
from app.services.gemini_service import generate_financial_insights
from app.services.normalizer import normalize_rows
from app.services.statement_classifier import classify_statement
from app.services.statement_mapper import STATEMENT_SECTIONS, map_statement
from app.auth.auth import get_current_user, parse_user_agent
from app.services.sheets_logger import log_audit_event


router = APIRouter()
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
SUPPORTED_FILES = (".xlsx", ".xls", ".csv")


def _statement_type(value, parsed):
    normalized = (value or "auto_detect").strip().lower().replace(" ", "_")
    aliases = {
        "auto": "auto_detect",
        "profit_loss": "profit_and_loss",
        "income_expense_statement": "income_expense",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized == "auto_detect":
        normalized = classify_statement(
            parsed.get("columns", []),
            parsed["data"],
            parsed.get("report_text", ""),
        )
        normalized = aliases.get(normalized, normalized)
    if normalized not in STATEMENT_SECTIONS:
        raise HTTPException(status_code=400, detail="Could not determine a supported statement type")
    return normalized


async def _save(upload):
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_FILES:
        raise HTTPException(status_code=400, detail="Only Excel and CSV files are supported")
    path = UPLOAD_FOLDER / f"{uuid4().hex}{suffix}"
    with path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return path


async def _parse_upload(upload):
    path = await _save(upload)
    try:
        parsed = parse_excel(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if parsed["status"] != "success":
        raise HTTPException(status_code=400, detail=f"Excel parsing failed: {parsed.get('message', '')}")
    return parsed


@router.post("/analyze")
@router.post("/upload")
async def analyze_statement(
    request: Request,
    current_file: UploadFile = File(None),
    previous_file: UploadFile = File(None),
    statement_type: str = Form("auto_detect"),
    compare_mode: str = Form("no"),
    from_date: str = Form(""),
    to_date: str = Form(""),
    compare_from_date: str = Form(""),
    compare_to_date: str = Form(""),
    # Legacy GitHub Pages frontend compatibility during deployment rollout.
    file: UploadFile = File(None),
    compare_report: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    current_file = current_file or file
    if not current_file:
        raise HTTPException(status_code=400, detail="current_file is required")

    current_parsed = await _parse_upload(current_file)
    resolved_type = _statement_type(statement_type, current_parsed)
    current_rows = normalize_rows(current_parsed["data"])
    current_mapped = map_statement(current_rows, resolved_type)

    should_compare = (compare_mode or compare_report).strip().lower() == "yes"
    previous_rows = []
    previous_mapped = None
    if should_compare:
        if not previous_file:
            raise HTTPException(status_code=400, detail="previous_file is required when compare_mode is yes")
        previous_parsed = await _parse_upload(previous_file)
        previous_rows = normalize_rows(previous_parsed["data"])
        previous_mapped = map_statement(previous_rows, resolved_type)

    results = analyze(current_mapped, previous_mapped, current_rows, resolved_type)
    mapped_section_count = sum(bool(rows) for rows in current_mapped.values())
    print("statement_type:", resolved_type)
    print("current rows count:", len(current_rows))
    print("previous rows count:", len(previous_rows))
    print("mapped sections count:", mapped_section_count)
    print("comparison count:", len(results["comparison_results"]))
    print("AI input count:", len(results["ai_input"]["financial_rows"]))

    # Parse headers for logging context
    ip_addr = request.client.host
    ua = request.headers.get("user-agent", "")
    browser, browser_version, os_name, device = parse_user_agent(ua)
    session_id = current_user.get("session_id")
    google_user_id = current_user.get("google_user_id")
    login_timestamp = current_user.get("iat")

    # Asynchronously log FILE_UPLOAD
    log_audit_event(
        email=current_user.get("email"),
        name=current_user.get("name"),
        google_user_id=google_user_id,
        action="FILE_UPLOAD",
        statement_type=resolved_type,
        filename=current_file.filename or "unknown",
        browser=browser,
        browser_version=browser_version,
        os_name=os_name,
        device=device,
        ip_address=ip_addr,
        session_id=session_id,
        login_timestamp=login_timestamp,
        status="SUCCESS"
    )

    if should_compare and previous_file:
        log_audit_event(
            email=current_user.get("email"),
            name=current_user.get("name"),
            google_user_id=google_user_id,
            action="FILE_UPLOAD",
            statement_type=resolved_type,
            filename=previous_file.filename or "unknown",
            browser=browser,
            browser_version=browser_version,
            os_name=os_name,
            device=device,
            ip_address=ip_addr,
            session_id=session_id,
            login_timestamp=login_timestamp,
            status="SUCCESS"
        )

    # Asynchronously log REPORT_ANALYSIS
    log_audit_event(
        email=current_user.get("email"),
        name=current_user.get("name"),
        google_user_id=google_user_id,
        action="REPORT_ANALYSIS",
        statement_type=resolved_type,
        filename=current_file.filename or "unknown",
        browser=browser,
        browser_version=browser_version,
        os_name=os_name,
        device=device,
        ip_address=ip_addr,
        session_id=session_id,
        login_timestamp=login_timestamp,
        status="SUCCESS"
    )

    return {
        "status": "success",
        "statement_type": resolved_type,
        "mode": "comparison" if should_compare else "single_period",
        "period": {"from_date": from_date, "to_date": to_date},
        "comparison_period": (
            {"from_date": compare_from_date, "to_date": compare_to_date}
            if should_compare
            else None
        ),
        "summary": results["summary"],
        "analytics": results["analytics"],
        "warnings": results["warnings"],
        "top_accounts": results["top_accounts"],
        "top_increases": results["top_increases"],
        "top_decreases": results["top_decreases"],
        "comparison_results": results["comparison_results"],
        "ai_insights": generate_financial_insights(resolved_type, results["ai_input"]),
    }

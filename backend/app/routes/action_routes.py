from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from app.auth.auth import get_current_user, parse_user_agent
from app.services.sheets_logger import log_audit_event

router = APIRouter(prefix="/api/log", tags=["Logging"])

class LogExportRequest(BaseModel):
    statement_type: str = "unknown"
    filename: str = "unknown"
    status: str = "SUCCESS"
    error_message: str = "-"

@router.post("/pdf-export")
async def log_pdf_export(payload: LogExportRequest, request: Request, current_user: dict = Depends(get_current_user)):
    ip_addr = request.client.host
    ua = request.headers.get("user-agent", "")
    browser, browser_version, os_name, device = parse_user_agent(ua)
    
    log_audit_event(
        email=current_user.get("email"),
        name=current_user.get("name"),
        google_user_id=current_user.get("google_user_id"),
        action="PDF_EXPORT",
        statement_type=payload.statement_type,
        filename=payload.filename,
        export_type="PDF",
        browser=browser,
        browser_version=browser_version,
        os_name=os_name,
        device=device,
        ip_address=ip_addr,
        session_id=current_user.get("session_id"),
        login_timestamp=current_user.get("iat"),
        status=payload.status,
        error_message=payload.error_message
    )
    return {"status": "success"}
 
@router.post("/excel-export")
async def log_excel_export(payload: LogExportRequest, request: Request, current_user: dict = Depends(get_current_user)):
    ip_addr = request.client.host
    ua = request.headers.get("user-agent", "")
    browser, browser_version, os_name, device = parse_user_agent(ua)
    
    log_audit_event(
        email=current_user.get("email"),
        name=current_user.get("name"),
        google_user_id=current_user.get("google_user_id"),
        action="EXCEL_EXPORT",
        statement_type=payload.statement_type,
        filename=payload.filename,
        export_type="EXCEL",
        browser=browser,
        browser_version=browser_version,
        os_name=os_name,
        device=device,
        ip_address=ip_addr,
        session_id=current_user.get("session_id"),
        login_timestamp=current_user.get("iat"),
        status=payload.status,
        error_message=payload.error_message
    )
    return {"status": "success"}

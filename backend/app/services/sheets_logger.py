import os
import datetime
import threading
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL")
PRIVATE_KEY_ID = os.getenv("GOOGLE_PRIVATE_KEY_ID")
PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS = [
    "Timestamp",
    "Login Time",
    "Logout Time",
    "Session Duration",
    "Session ID",
    "Employee Name",
    "Employee Email",
    "Google User ID",
    "Action",
    "Statement Type",
    "Uploaded Filename",
    "Export Type",
    "Browser",
    "Browser Version",
    "Operating System",
    "Device",
    "IP Address",
    "Status",
    "Failure Reason"
]

def get_sheets_service():
    """
    Builds the Google Sheets API service client.
    """
    if not PRIVATE_KEY or not CLIENT_EMAIL or not SPREADSHEET_ID:
        print("Google Sheets credentials or Sheet ID missing in environment.")
        return None
        
    pk = PRIVATE_KEY.replace("\\n", "\n").strip('"')
    
    info = {
        "type": "service_account",
        "project_id": PROJECT_ID,
        "private_key_id": PRIVATE_KEY_ID,
        "private_key": pk,
        "client_email": CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    
    try:
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        service = build("sheets", "v4", credentials=credentials)
        return service
    except Exception as e:
        print(f"Failed to create Google Sheets credentials: {e}")
        return None

def ensure_audit_logs_sheet(service):
    """
    Ensures that the 'Audit Logs' worksheet exists in the spreadsheet
    and contains the correct 19-column header.
    """
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = spreadsheet.get("sheets", [])
        sheet_names = [s.get("properties", {}).get("title") for s in sheets]
        
        if "Audit Logs" not in sheet_names:
            body = {
                "requests": [{
                    "addSheet": {
                        "properties": {
                            "title": "Audit Logs"
                        }
                    }
                }]
            }
            service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
            
        res = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Audit Logs!A1:S1"
        ).execute()
        
        current_headers = res.get("values", [[]])[0]
        if current_headers != HEADERS:
            header_body = {
                "values": [HEADERS]
            }
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range="Audit Logs!A1:S1",
                valueInputOption="USER_ENTERED",
                body=header_body
            ).execute()
            print("Successfully updated 'Audit Logs' worksheet headers.")
    except Exception as e:
        print(f"Failed to ensure/update 'Audit Logs' worksheet: {e}")

_sheet_initialized = False
_sheet_init_lock = threading.Lock()

def _log_event_worker(
    email: str, name: str, google_user_id: str, action: str,
    statement_type: str, filename: str, export_type: str,
    browser: str, browser_version: str, os_name: str, device: str,
    ip_address: str, session_id: str, login_timestamp: float,
    status: str, error_message: str
):
    print("[DEBUG] BUILDING SHEETS CLIENT")
    global _sheet_initialized
    try:
        service = get_sheets_service()
        if not service:
            print("[DEBUG] FAILED: Service build returned None")
            return
    except Exception as exc:
        print("[DEBUG] FAILED: get_sheets_service raised an exception:")
        import traceback
        traceback.print_exc()
        return
        
    with _sheet_init_lock:
        if not _sheet_initialized:
            print("[DEBUG] OPENING SPREADSHEET")
            try:
                ensure_audit_logs_sheet(service)
                _sheet_initialized = True
            except Exception as exc:
                print("[DEBUG] FAILED: ensure_audit_logs_sheet failed:")
                import traceback
                traceback.print_exc()
                return
            
    now_dt = datetime.datetime.now(datetime.UTC)
    timestamp = now_dt.isoformat() + "Z"
    
    login_time = "-"
    logout_time = "-"
    session_duration = "-"
    
    if login_timestamp:
        try:
            login_time_dt = datetime.datetime.fromtimestamp(login_timestamp, datetime.UTC)
            login_time = login_time_dt.isoformat() + "Z"
            session_duration = f"{(now_dt - login_time_dt).total_seconds():.1f}s"
        except Exception as e:
            print("Error calculating session times:", e)
    elif action == "LOGIN" and status == "SUCCESS":
        login_time = timestamp
        session_duration = "0.0s"
        
    if action in ("LOGOUT", "SESSION_EXPIRED"):
        logout_time = timestamp
        
    row = [
        timestamp,
        login_time,
        logout_time,
        session_duration,
        session_id or "-",
        name or "-",
        email or "-",
        google_user_id or "-",
        action or "-",
        statement_type or "-",
        filename or "-",
        export_type or "-",
        browser or "-",
        browser_version or "-",
        os_name or "-",
        device or "-",
        ip_address or "-",
        status or "-",
        error_message or "-"
    ]
    
    print("[DEBUG] APPENDING ROW")
    try:
        body = {"values": [row]}
        res = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Audit Logs!A:S",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        print("[DEBUG] GOOGLE RESPONSE:", res)
        print("[DEBUG] SUCCESS")
    except Exception as e:
        print("[DEBUG] FAILED: execute append failed")
        import traceback
        traceback.print_exc()

def log_audit_event(
    email: str = None, name: str = None, google_user_id: str = None, action: str = None,
    statement_type: str = None, filename: str = None, export_type: str = None,
    browser: str = None, browser_version: str = None, os_name: str = None, device: str = None,
    ip_address: str = None, session_id: str = None, login_timestamp: float = None,
    status: str = "SUCCESS", error_message: str = "-"
):
    """
    Logs an audit event to the Google Sheet asynchronously in a background thread.
    """
    print("[DEBUG] LOGGER CALLED")
    try:
        t = threading.Thread(
            target=_log_event_worker,
            args=(
                email, name, google_user_id, action, statement_type, filename, export_type,
                browser, browser_version, os_name, device, ip_address, session_id,
                login_timestamp, status, error_message
            ),
            daemon=True
        )
        t.start()
        print("[DEBUG] THREAD STARTED")
    except Exception as e:
        print("[DEBUG] FAILED: Thread start failed:")
        import traceback
        traceback.print_exc()

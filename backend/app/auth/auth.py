import os
import datetime
import jwt
from fastapi import Request, HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests

JWT_SECRET = os.environ["JWT_SECRET"]
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_ALGORITHM = "HS256"
SESSION_TIMEOUT_HOURS = 8

def verify_google_token(token: str) -> dict:
    """
    Verifies the Google ID token and returns the parsed payload.
    Raises HTTPException 403 on invalid domain or 401 on token verification issues.
    """
    try:
        # Verify the ID token using the official Google Transports requests
        id_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        # Verify audience and issuer
        if id_info.get("aud") != GOOGLE_CLIENT_ID:
            raise ValueError("Audience mismatch.")
        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Issuer mismatch.")
            
        # Validate email domain
        email = id_info.get("email", "")
        if not email.endswith("@nobroker.in"):
            raise HTTPException(
                status_code=403,
                detail="Access Denied.\nOnly NoBroker employees can access FinSight AI."
            )
            
        return id_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Google ID Token: {str(e)}"
        )

def create_jwt_token(user_info: dict, session_id: str) -> str:
    """
    Generates a JWT session token valid for 8 hours.
    """
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": user_info.get("sub"),
        "name": user_info.get("name"),
        "email": user_info.get("email"),
        "picture": user_info.get("picture"),
        "session_id": session_id,
        "iat": now,
        "exp": now + datetime.timedelta(hours=SESSION_TIMEOUT_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def parse_user_agent(ua_string: str) -> tuple[str, str, str, str]:
    import re
    if not ua_string:
        return "Unknown", "Unknown", "Unknown", "Unknown"
        
    ua = ua_string
    ua_lower = ua.lower()
    
    # 1. Device Type Detection
    if "mobi" in ua_lower or "iphone" in ua_lower or "ipod" in ua_lower or "android" in ua_lower and "mobile" in ua_lower:
        device = "Mobile"
    elif "ipad" in ua_lower or "tablet" in ua_lower or "android" in ua_lower:
        device = "Tablet"
    else:
        device = "Desktop"
        
    # 2. OS Detection
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        if "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
            os_name = "iOS"
        else:
            os_name = "macOS"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        os_name = "iOS"
    else:
        os_name = "Unknown"
        
    # 3. Browser & Version Detection
    browser = "Other"
    version = "Unknown"
    
    # Check Edge
    edge_match = re.search(r'(Edg|Edge|EdgA|EdgiOS)/(\d+(\.\d+)*)', ua)
    if edge_match:
        browser = "Edge"
        version = edge_match.group(2)
    # Check Firefox
    elif "firefox" in ua_lower or "fxios" in ua_lower:
        browser = "Firefox"
        ff_match = re.search(r'(Firefox|FxDoS|FxIOS)/(\d+(\.\d+)*)', ua)
        if ff_match:
            version = ff_match.group(2)
    # Check Chrome
    elif "chrome" in ua_lower or "crios" in ua_lower:
        browser = "Chrome"
        chrome_match = re.search(r'(Chrome|CriOS)/(\d+(\.\d+)*)', ua)
        if chrome_match:
            version = chrome_match.group(2)
    # Check Safari
    elif "safari" in ua_lower:
        browser = "Safari"
        safari_match = re.search(r'Version/(\d+(\.\d+)*)', ua)
        if safari_match:
            version = safari_match.group(1)
        else:
            safari_match_alt = re.search(r'Safari/(\d+(\.\d+)*)', ua)
            if safari_match_alt:
                version = safari_match_alt.group(1)
                
    return browser, version, os_name, device

def verify_jwt_token(token: str) -> dict:
    """
    Decodes and validates a JWT session token.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

def get_current_user(request: Request) -> dict:
    """
    Dependency to retrieve the currently logged in user based on the session_token cookie.
    Logs SESSION_EXPIRED and UNAUTHORIZED_ACCESS events to Google Sheets when authorization fails.
    """
    token = request.cookies.get("session_token")
    
    ip_addr = request.client.host
    ua = request.headers.get("user-agent", "")
    browser, browser_version, os_name, device = parse_user_agent(ua)
    
    from app.services.sheets_logger import log_audit_event
    
    if not token:
        log_audit_event(
            email="-",
            name="-",
            google_user_id="-",
            action="UNAUTHORIZED_ACCESS",
            browser=browser,
            browser_version=browser_version,
            os_name=os_name,
            device=device,
            ip_address=ip_addr,
            session_id="-",
            status="FAILED",
            error_message="Missing session token cookie."
        )
        raise HTTPException(
            status_code=401,
            detail="Session expired or not found. Please log in."
        )
        
    try:
        payload = verify_jwt_token(token)
        # Map sub to google_user_id
        if "sub" in payload and "google_user_id" not in payload:
            payload["google_user_id"] = payload["sub"]
        return payload
    except jwt.ExpiredSignatureError:
        # Extract email and session_id from expired token for logging
        email = "-"
        name = "-"
        google_user_id = "-"
        session_id = "-"
        login_timestamp = None
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            email = decoded.get("email", "-")
            name = decoded.get("name", "-")
            google_user_id = decoded.get("sub", "-")
            session_id = decoded.get("session_id", "-")
            login_timestamp = decoded.get("iat")
        except:
            pass
        log_audit_event(
            email=email,
            name=name,
            google_user_id=google_user_id,
            action="SESSION_EXPIRED",
            browser=browser,
            browser_version=browser_version,
            os_name=os_name,
            device=device,
            ip_address=ip_addr,
            session_id=session_id,
            login_timestamp=login_timestamp,
            status="FAILED",
            error_message="JWT signature expired."
        )
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        log_audit_event(
            email="-",
            name="-",
            google_user_id="-",
            action="UNAUTHORIZED_ACCESS",
            browser=browser,
            browser_version=browser_version,
            os_name=os_name,
            device=device,
            ip_address=ip_addr,
            session_id="-",
            status="FAILED",
            error_message="Invalid JWT signature."
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid session token. Please log in again."
        )

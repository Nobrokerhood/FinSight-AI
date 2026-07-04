import os
import uuid
import jwt
from fastapi import APIRouter, Response, Request, HTTPException, Depends
from pydantic import BaseModel
from app.auth.auth import verify_google_token, create_jwt_token, get_current_user, parse_user_agent
from app.services.sheets_logger import log_audit_event

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    credential: str

@router.get("/config")
async def get_config():
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID")
    }

@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    print("[DEBUG] LOGIN RECEIVED")
    ip_addr = request.client.host
    ua = request.headers.get("user-agent", "")
    browser, browser_version, os_name, device = parse_user_agent(ua)
    
    # Generate temporary session ID for potential failure logging
    temp_session_id = str(uuid.uuid4())
    
    try:
        id_info = verify_google_token(payload.credential)
    except HTTPException as he:
        # If it was a domain validation error (403), log as INVALID_DOMAIN
        if he.status_code == 403:
            unverified_email = "unknown"
            unverified_name = "unknown"
            try:
                decoded = jwt.decode(payload.credential, options={"verify_signature": False})
                unverified_email = decoded.get("email", "unknown")
                unverified_name = decoded.get("name", "unknown")
            except:
                pass
            log_audit_event(
                email=unverified_email,
                name=unverified_name,
                google_user_id="-",
                action="INVALID_DOMAIN",
                browser=browser,
                browser_version=browser_version,
                os_name=os_name,
                device=device,
                ip_address=ip_addr,
                session_id=temp_session_id,
                status="FAILED",
                error_message="Access Denied. Only NoBroker employees can access FinSight AI."
            )
        else:
            log_audit_event(
                email="unknown",
                name="unknown",
                google_user_id="-",
                action="LOGIN_FAILED",
                browser=browser,
                browser_version=browser_version,
                os_name=os_name,
                device=device,
                ip_address=ip_addr,
                session_id=temp_session_id,
                status="FAILED",
                error_message=str(he.detail)
            )
        raise he
    except Exception as e:
        log_audit_event(
            email="unknown",
            name="unknown",
            google_user_id="-",
            action="LOGIN_FAILED",
            browser=browser,
            browser_version=browser_version,
            os_name=os_name,
            device=device,
            ip_address=ip_addr,
            session_id=temp_session_id,
            status="FAILED",
            error_message=str(e)
        )
        raise HTTPException(status_code=401, detail=str(e))
        
    email = id_info.get("email")
    name = id_info.get("name")
    picture = id_info.get("picture")
    google_user_id = id_info.get("sub")
    
    session_id = str(uuid.uuid4())
    
    # Create JWT
    jwt_token = create_jwt_token(id_info, session_id)
    print("[DEBUG] JWT CREATED")
    
    # Render compatibility for cookie security (Auto secure on HTTPS, false on local HTTP)
    is_secure = request.url.scheme == "https"
    
    response.set_cookie(
        key="session_token",
        value=jwt_token,
        httponly=True,
        samesite="none" if is_secure else "lax",
        secure=is_secure,
        max_age=8 * 3600
    )
    
    # Log successful LOGIN
    log_audit_event(
        email=email,
        name=name,
        google_user_id=google_user_id,
        action="LOGIN",
        browser=browser,
        browser_version=browser_version,
        os_name=os_name,
        device=device,
        ip_address=ip_addr,
        session_id=session_id,
        status="SUCCESS"
    )
    
    return {
        "email": email,
        "name": name,
        "picture": picture,
        "session_id": session_id
    }
 
@router.post("/logout")
async def logout(request: Request, response: Response, current_user: dict = Depends(get_current_user)):
    ip_addr = request.client.host
    ua = request.headers.get("user-agent", "")
    browser, browser_version, os_name, device = parse_user_agent(ua)
    
    # Log LOGOUT
    log_audit_event(
        email=current_user.get("email"),
        name=current_user.get("name"),
        google_user_id=current_user.get("google_user_id"),
        action="LOGOUT",
        browser=browser,
        browser_version=browser_version,
        os_name=os_name,
        device=device,
        ip_address=ip_addr,
        session_id=current_user.get("session_id"),
        login_timestamp=current_user.get("iat"),
        status="SUCCESS"
    )
    
    is_secure = request.url.scheme == "https"
    response.delete_cookie(
        "session_token",
        samesite="none" if is_secure else "lax",
        secure=is_secure
    )
    return {"status": "success"}
 
@router.get("/session")
async def get_session(current_user: dict = Depends(get_current_user)):
    return current_user

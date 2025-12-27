# app/routes/auth.py
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token_purpose,
)
from app.core.password_policy import ensure_strong_password, mark_password_changed, password_is_expired
from app.models.user import User
from app.schemas.auth import (
    RegisterIn,
    LoginIn,
    TokenOut,
    MessageOut,
    ResendVerifyIn,
    VerifyOut,
)
from app.services.email import EmailDeliveryError, EmailNotConfiguredError, send_email
from app.services.email_verification import (
    consume_email_verification_token,
    issue_email_verification_token,
)
from app.services.refresh_tokens import (
    clear_refresh_cookie,
    get_valid_refresh_token,
    hash_refresh_token,
    issue_refresh_token,
    read_refresh_cookie,
    revoke_refresh_token,
    set_refresh_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# -----------------------------
# Email verification sender
# -----------------------------
def send_verification_email(email: str, token: str) -> None:
    # Send users to the frontend route which calls the backend /auth/verify endpoint.
    verify_link = f"{settings.FRONTEND_BASE_URL}/verify?token={token}&email={email}"
    subject = "Verify your Job Tracker email"
    body = "\n".join(
        [
            "Welcome to Job Tracker!",
            "",
            "Please verify your email by clicking the link below:",
            verify_link,
            "",
            "If you did not create this account, you can ignore this email.",
        ]
    )

    try:
        msg_id = send_email(to_email=email, subject=subject, body=body)
    except EmailNotConfiguredError as e:
        # Explicit and safe: tells dev what to configure.
        raise HTTPException(status_code=500, detail=f"Email delivery not configured: {e}")
    except EmailDeliveryError as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Log something visible in dev logs without leaking the token/link.
    # NOTE: settings.EMAIL_PROVIDER defaults to "resend" if unset.
    print(f"[email] verification email queued to={email} provider={settings.EMAIL_PROVIDER} msg_id={msg_id}")


# -----------------------------
# Routes
# -----------------------------
@router.post("/register", response_model=MessageOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    ensure_strong_password(payload.password, email=email, username=name)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        name=name,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_email_verified=False,
        email_verified_at=None,
    )
    mark_password_changed(user)
    db.add(user)
    db.flush()
    try:
        token = issue_email_verification_token(db, user)
        send_verification_email(email, token)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "Registration successful. Please verify your email."}


@router.get("/verify", response_model=VerifyOut)
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = verify_token_purpose(token, expected_purpose="email_verification")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    email = (payload.get("sub") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    try:
        consume_email_verification_token(db, user, jti)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if user.is_email_verified:
        db.commit()
        return {"message": "Email already verified"}

    user.is_email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Email verified successfully. You can now log in."}


@router.post("/resend-verification", response_model=MessageOut)
def resend_verification(payload: ResendVerifyIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": "If that email exists, a verification link was sent."}

    if not user.is_active:
        return {"message": "If that email exists, a verification link was sent."}

    if user.is_email_verified:
        return {"message": "Email already verified. Please log in."}

    try:
        token = issue_email_verification_token(db, user)
        send_verification_email(email, token)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "If that email exists, a verification link was sent."}


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    access_token = create_access_token(subject=email, token_version=user.token_version)

    # Issue refresh token + set HttpOnly cookie
    refresh_token = issue_refresh_token(db, user_id=user.id)
    set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_change_password": password_is_expired(user),
    }


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Rotate refresh tokens via HttpOnly cookie:
      - read refresh token from cookie
      - validate
      - revoke old
      - issue new refresh cookie
      - return new access token
    """
    raw = read_refresh_cookie(request)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    rt = get_valid_refresh_token(db, raw)
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == rt.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    # rotate
    revoke_refresh_token(db, rt.token_hash)
    new_refresh_token = issue_refresh_token(db, user_id=user.id)
    set_refresh_cookie(response, new_refresh_token)

    access_token = create_access_token(subject=user.email, token_version=user.token_version)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "must_change_password": password_is_expired(user),
    }


@router.post("/logout", response_model=MessageOut)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Logout by revoking the refresh token in cookie (if present) and clearing cookie.
    """
    raw = read_refresh_cookie(request)
    if raw:
        token_hash = hash_refresh_token(raw)
        revoke_refresh_token(db, token_hash)

    clear_refresh_cookie(response)
    return {"message": "Logged out"}
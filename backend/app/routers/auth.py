"""
Sign-up (gated, admin-approved) + sign-in (passcode -> mandatory MFA) flows.

Zero Trust: every failed login is logged; repeated failures are flagged
to the ledger rather than silently retried indefinitely.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserStatus, UserRole
from app.schemas import (
    SignUpRequest, SignUpResponse, LoginRequest, LoginStepOneResponse,
    MfaVerifyRequest, TokenResponse, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasscodeRequest,
)
from app.security.aes import encrypt_field, decrypt_field
from app.security.passcode import hash_passcode, verify_passcode
from app.security.mfa import (
    generate_totp_secret, get_provisioning_qr_png_b64, verify_totp, generate_backup_codes,
)
from app.security.jwt import create_access_token, create_refresh_token, make_session_fingerprint
from app.security.email import send_email
from app.blockchain.ledger import append_block

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

MFA_CHALLENGE_TYPE = "mfa_challenge"
MFA_CHALLENGE_TTL_MINUTES = 5


@router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignUpRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user = User(
        email=body.email,
        passcode_hash=hash_passcode(body.passcode),
        full_name_enc=encrypt_field(body.full_name),
        organisation_enc=encrypt_field(body.organisation),
        phone_enc=encrypt_field(body.phone_number),
        role=UserRole.VIEWER,
        status=UserStatus.PENDING_VERIFICATION,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    append_block(db, "USER_SIGNUP", {"user_id": user.id, "email": user.email})

    # TODO: notify the Admin review queue via email-to-admin, not just in-app.
    return SignUpResponse(id=user.id, email=user.email, status=user.status.value)


@router.post("/login", response_model=LoginStepOneResponse)
def login_step_one(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()

    # Zero Trust: never reveal whether the email exists via response shape/timing.
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not user or user.status != UserStatus.ACTIVE:
        raise invalid
    if not verify_passcode(body.passcode, user.passcode_hash):
        user.failed_login_count += 1
        db.commit()
        append_block(db, "LOGIN_FAILURE", {"user_id": user.id})
        if user.failed_login_count >= settings.max_failed_logins_before_flag:
            append_block(db, "ACCOUNT_FLAGGED", {"user_id": user.id, "reason": "repeated_failed_logins"})
        raise invalid

    user.failed_login_count = 0
    db.commit()

    provisioning_qr = None
    if not user.mfa_enrolled:
        secret = generate_totp_secret()
        user.mfa_secret_enc = encrypt_field(secret)
        db.commit()
        provisioning_qr = get_provisioning_qr_png_b64(secret, user.email)
        # mfa_enrolled flips to True only once the first TOTP verify succeeds
        # (see /auth/mfa/verify), so an interrupted enrollment can be redone.

    challenge_token = jwt.encode(
        {
            "sub": user.id,
            "type": MFA_CHALLENGE_TYPE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=MFA_CHALLENGE_TTL_MINUTES),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return LoginStepOneResponse(
        mfa_required=True,
        mfa_challenge_token=challenge_token,
        mfa_enrolled=user.mfa_enrolled,
        provisioning_qr_png_b64=provisioning_qr,
    )


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(body: MfaVerifyRequest, request: Request, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(body.mfa_challenge_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA challenge expired or invalid — sign in again")
    if payload.get("type") != MFA_CHALLENGE_TYPE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong challenge token type")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.mfa_secret_enc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "MFA not set up for this account")

    secret = decrypt_field(user.mfa_secret_enc)
    if not verify_totp(secret, body.totp_code):
        append_block(db, "MFA_FAILURE", {"user_id": user.id})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid MFA code")

    if not user.mfa_enrolled:
        user.mfa_enrolled = True
        codes = generate_backup_codes()
        user.backup_codes_enc = encrypt_field(",".join(codes))
        db.commit()
        # TODO: surface `codes` to the client exactly once at enrollment time
        # (not stored anywhere in plaintext after this response).

    fingerprint = make_session_fingerprint(
        request.headers.get("user-agent", ""), request.client.host if request.client else ""
    )
    access = create_access_token(user.id, user.role.value, fingerprint)
    refresh = create_refresh_token(user.id, fingerprint)

    append_block(db, "LOGIN_SUCCESS", {"user_id": user.id})

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(body.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    # TODO: persist issued/consumed refresh-token `jti`s (e.g. Redis or a
    # table) so reuse of an already-rotated token can be detected and the
    # whole `family` invalidated, per the Zero Trust spec.

    fingerprint = make_session_fingerprint(
        request.headers.get("user-agent", ""), request.client.host if request.client else ""
    )
    user_id = payload["sub"]
    from app.models import User as _User
    user = db.query(_User).filter(_User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    access = create_access_token(user.id, user.role.value, fingerprint)
    new_refresh = create_refresh_token(user.id, fingerprint, family_id=payload.get("family"))
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "status": user.status.value,
        "mfa_enrolled": user.mfa_enrolled,
    }


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always returns the same generic response whether or not the email
    exists — Zero Trust: never reveal account existence via response
    shape/timing, same principle as /auth/login. The actual reset link
    only ever goes out if the account is real."""
    generic_response = {"message": "If that email has an active account, a reset link has been sent."}

    user = db.query(User).filter(User.email == body.email, User.status == UserStatus.ACTIVE).first()
    if not user:
        return generic_response

    raw_token = secrets.token_urlsafe(32)
    user.reset_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    user.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=settings.password_reset_token_ttl_minutes)
    db.commit()

    reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    send_email(
        to=user.email,
        subject="SOCMINT passcode reset",
        body=(
            f"A passcode reset was requested for your SOCMINT account.\n\n"
            f"Reset link (expires in {settings.password_reset_token_ttl_minutes} minutes):\n{reset_link}\n\n"
            f"If you didn't request this, you can ignore this email."
        ),
    )
    append_block(db, "PASSWORD_RESET_REQUESTED", {"user_id": user.id})

    return generic_response


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    user = db.query(User).filter(User.reset_token_hash == token_hash).first()

    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "Reset link is invalid or has expired — request a new one.")
    if not user or not user.reset_token_expires_at:
        raise invalid
    if datetime.utcnow() > user.reset_token_expires_at:
        raise invalid

    user.passcode_hash = hash_passcode(body.new_passcode)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.failed_login_count = 0
    db.commit()

    append_block(db, "PASSWORD_RESET_COMPLETED", {"user_id": user.id})
    return {"message": "Passcode reset. You can now sign in with your new passcode."}


@router.put("/change-passcode")
def change_passcode(
    body: ChangePasscodeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """For a signed-in user changing their own passcode — e.g. right
    after first login with the seeded default admin credentials."""
    if not verify_passcode(body.current_passcode, user.passcode_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current passcode is incorrect")

    user.passcode_hash = hash_passcode(body.new_passcode)
    db.commit()

    append_block(db, "PASSCODE_CHANGED", {"user_id": user.id})
    return {"message": "Passcode changed."}

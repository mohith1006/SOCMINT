"""
Short-lived access tokens + rotating refresh tokens, bound to a
device/session fingerprint (Zero Trust: continuous validation per request,
not just at login).
"""
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from app.config import get_settings

settings = get_settings()


def _now():
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, role: str, session_fingerprint: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "fp": session_fingerprint,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, session_fingerprint: str, family_id: str | None = None) -> str:
    """`family_id` groups a chain of refresh tokens so that reuse of an
    already-rotated token can invalidate the entire session chain."""
    payload = {
        "sub": user_id,
        "fp": session_fingerprint,
        "type": "refresh",
        "family": family_id or str(uuid.uuid4()),
        "jti": str(uuid.uuid4()),
        "iat": _now(),
        "exp": _now() + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {e}")


def make_session_fingerprint(user_agent: str, ip: str) -> str:
    """Coarse device/session fingerprint. In production, combine with
    client-side signals (e.g. TLS JA3, device ID) for stronger binding."""
    import hashlib
    return hashlib.sha256(f"{user_agent}|{ip}".encode()).hexdigest()[:32]

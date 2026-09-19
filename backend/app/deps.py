"""
Zero-Trust request dependencies: every endpoint independently validates the
JWT, checks the role, and (for access tokens) checks the session fingerprint
against the requesting device — never relies on prior session history alone.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.security.jwt import decode_token, make_session_fingerprint

bearer_scheme = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")

    # Continuous validation: recompute the fingerprint for *this* request
    # and compare — a stolen token replayed from a different device/IP fails.
    current_fp = make_session_fingerprint(
        request.headers.get("user-agent", ""), request.client.host if request.client else ""
    )
    if payload.get("fp") != current_fp:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session fingerprint mismatch — re-authenticate")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_role(*allowed_roles: UserRole):
    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this action")
        return user

    return _checker


require_admin = require_role(UserRole.ADMIN)

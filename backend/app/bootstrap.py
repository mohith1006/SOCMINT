"""
Seeds a default Admin account on first boot if no admin exists yet, so a
fresh `docker compose up` is actually usable without hand-running SQL
against Postgres. Credentials come from DEFAULT_ADMIN_EMAIL /
DEFAULT_ADMIN_PASSCODE in .env — see .env.example, which ships with
`admin@socmint.local` / `ChangeMe#2026!` by default.

This only ever creates ONE account, only when zero admins exist. It never
resets or overwrites an existing admin's passcode — if you've already
changed it, this does nothing on subsequent restarts.
"""
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserRole, UserStatus
from app.security.aes import encrypt_field
from app.security.passcode import hash_passcode
from app.blockchain.ledger import append_block

logger = logging.getLogger("socmint.bootstrap")
settings = get_settings()


def ensure_default_admin(db: Session) -> None:
    existing_admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if existing_admin:
        return

    admin = User(
        email=settings.default_admin_email,
        passcode_hash=hash_passcode(settings.default_admin_passcode),
        full_name_enc=encrypt_field("Default Admin"),
        organisation_enc=encrypt_field("SOCMINT"),
        phone_enc=encrypt_field("0000000000"),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(admin)
    db.commit()

    append_block(db, "DEFAULT_ADMIN_SEEDED", {"email": settings.default_admin_email})

    # Loud and impossible to miss in `docker compose up` output — this
    # matters precisely because it's a well-known, publicly-committed
    # default credential (see .env.example).
    logger.warning(
        "=" * 70 + "\n"
        "SOCMINT: seeded a default admin account (no admin existed yet):\n"
        f"    email:    {settings.default_admin_email}\n"
        f"    passcode: {settings.default_admin_passcode}\n"
        "This is a PUBLIC, COMMITTED default from .env.example — sign in\n"
        "and change the passcode immediately (Settings page), or set\n"
        "DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSCODE in your .env before\n"
        "first boot for anything beyond local judging/demo use.\n"
        + "=" * 70
    )

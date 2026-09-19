"""
TOTP-based MFA (pyotp), mandatory for every role, enrolled at first
successful login. Generates a QR-enrollable secret and one-time backup codes.
"""
import base64
import io
import secrets

import pyotp
import qrcode
from qrcode.image.pil import PilImage

from app.config import get_settings

settings = get_settings()


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_qr_png_b64(secret: str, account_email: str) -> str:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=settings.mfa_issuer_name
    )
    img = qrcode.make(uri,image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes(count: int = 8) -> list[str]:
    return [secrets.token_hex(4) for _ in range(count)]

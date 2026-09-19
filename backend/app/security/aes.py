"""
AES-256-GCM field-level encryption for sensitive PII columns
(full_name, organisation, phone_number, mfa_secret, backup_codes).

Key is sourced from settings.field_encryption_key (env var FIELD_ENCRYPTION_KEY),
must be a base64-encoded 32-byte key. Generate one with:
    python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"

Output format stored in the DB: base64(nonce || ciphertext_with_tag)
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

_settings = get_settings()
try:
    _key = base64.b64decode(_settings.field_encryption_key, validate=True)
except Exception as e:
    raise ValueError(
        "FIELD_ENCRYPTION_KEY in your .env is not valid base64. Generate a "
        'real one with: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())" '
        "and put the output in .env, then restart."
    ) from e
if len(_key) != 32:
    raise ValueError(
        f"FIELD_ENCRYPTION_KEY decodes to {len(_key)} bytes, but AES-256 needs exactly 32. "
        'Generate a valid one with: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())" '
        "and put the output in .env, then restart."
    )

_aesgcm = AESGCM(_key)


def encrypt_field(plaintext: str) -> str:
    nonce = os.urandom(12)
    ciphertext = _aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_field(token: str) -> str:
    raw = base64.b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = _aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")

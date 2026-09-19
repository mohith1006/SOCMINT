"""
Passcode hashing and the sign-up strength policy:

- Minimum 12 characters
- At least one uppercase, one lowercase, one digit, one special character
- Rejected against a common-password blocklist
- No more than 2 identical characters in a row

Hashing uses the `bcrypt` package directly rather than passlib's bcrypt
backend. passlib==1.7.4 detects the installed bcrypt version by reading
`bcrypt.__about__.__version__`, an attribute bcrypt removed starting in its
4.x releases — this throws `AttributeError: module 'bcrypt' has no
attribute '__about__'` (sometimes trapped and merely logged, sometimes
fatal depending on the exact bcrypt patch version) on every fresh install,
since pip installs the latest bcrypt by default regardless of what
passlib expects. Calling bcrypt directly sidesteps that version-sniffing
entirely — this is the fix multiple independent teams converged on for
the same bug, not a workaround pinned to whatever bcrypt version happens
to work today.
"""
import re

import bcrypt

# bcrypt truncates/errors past 72 BYTES of input — truncate deliberately
# and consistently between hashing and verification, rather than let it
# happen implicitly (or inconsistently) inside the library.
BCRYPT_MAX_BYTES = 72

COMMON_PASSWORD_BLOCKLIST = {
    "password123!", "welcome123!", "admin12345!", "changeme123!",
    "qwerty123456!", "letmein12345!",
}

SPECIAL_CHARS = r"""!"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~"""


class PasscodeError(ValueError):
    pass


def validate_passcode_strength(passcode: str) -> None:
    if len(passcode) < 12:
        raise PasscodeError("Passcode must be at least 12 characters long.")
    if not re.search(r"[A-Z]", passcode):
        raise PasscodeError("Passcode must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", passcode):
        raise PasscodeError("Passcode must contain at least one lowercase letter.")
    if not re.search(r"\d", passcode):
        raise PasscodeError("Passcode must contain at least one digit.")
    if not re.search(f"[{SPECIAL_CHARS}]", passcode):
        raise PasscodeError("Passcode must contain at least one special character.")
    if passcode.lower() in COMMON_PASSWORD_BLOCKLIST:
        raise PasscodeError("Passcode is too common. Choose something less guessable.")
    for i in range(len(passcode) - 2):
        if passcode[i] == passcode[i + 1] == passcode[i + 2]:
            raise PasscodeError("Passcode cannot contain 3+ identical characters in a row.")


def hash_passcode(passcode: str) -> str:
    truncated = passcode.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_passcode(passcode: str, passcode_hash: str) -> bool:
    truncated = passcode.encode("utf-8")[:BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(truncated, passcode_hash.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash format — never let this become a 500.
        return False

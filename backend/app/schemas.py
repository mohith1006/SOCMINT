from pydantic import BaseModel, EmailStr, field_validator

from app.security.passcode import validate_passcode_strength, PasscodeError


class SignUpRequest(BaseModel):
    email: EmailStr
    full_name: str
    organisation: str
    phone_number: str
    passcode: str

    @field_validator("passcode")
    @classmethod
    def check_passcode_strength(cls, v: str) -> str:
        try:
            validate_passcode_strength(v)
        except PasscodeError as e:
            raise ValueError(str(e))
        return v


class SignUpResponse(BaseModel):
    id: str
    email: EmailStr
    status: str


class LoginRequest(BaseModel):
    email: EmailStr
    passcode: str


class LoginStepOneResponse(BaseModel):
    mfa_required: bool
    mfa_challenge_token: str
    mfa_enrolled: bool
    # Present only on first-ever login, so the client can render the QR code
    provisioning_qr_png_b64: str | None = None


class MfaVerifyRequest(BaseModel):
    mfa_challenge_token: str
    totp_code: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_passcode: str

    @field_validator("new_passcode")
    @classmethod
    def check_new_passcode_strength(cls, v: str) -> str:
        try:
            validate_passcode_strength(v)
        except PasscodeError as e:
            raise ValueError(str(e))
        return v


class ChangePasscodeRequest(BaseModel):
    current_passcode: str
    new_passcode: str

    @field_validator("new_passcode")
    @classmethod
    def check_new_passcode_strength(cls, v: str) -> str:
        try:
            validate_passcode_strength(v)
        except PasscodeError as e:
            raise ValueError(str(e))
        return v


class AdminDecisionRequest(BaseModel):
    reason: str | None = None


class PendingUserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: str


class LedgerBlockOut(BaseModel):
    index: int
    timestamp: str
    data_hash: str
    event_type: str
    previous_hash: str
    hash: str


class LedgerVerifyOut(BaseModel):
    valid: bool
    brokenAtIndex: int | None

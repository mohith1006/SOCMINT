"""
Minimal SMTP email sending for the password-reset flow. If SMTP_HOST isn't
set in .env, this logs the email (including the reset link) to the
backend console instead of failing — fine for local dev/judging, not a
substitute for real email in production. Callers should never assume the
email was actually delivered; the API response is intentionally the same
either way (see the forgot-password endpoint) to avoid leaking whether an
account exists.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("socmint.email")
settings = get_settings()


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.warning(
            "SMTP not configured (SMTP_HOST unset) — logging email instead of sending:\n"
            f"To: {to}\nSubject: {subject}\n\n{body}"
        )
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except Exception:
        # Never let an email delivery failure surface as a 500 to the
        # caller — log it and move on; the API response doesn't reveal
        # delivery status either way (see module docstring).
        logger.exception(f"Failed to send email to {to}")

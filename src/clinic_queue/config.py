import os
import secrets
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    # Signs the session cookie. Without one, a random key is used and desk logins
    # don't survive a restart, which is fine for local dev but not for production.
    secret_key: str
    # scrypt hash of the 4-digit desk PIN (see `python -m clinic_queue.security`).
    desk_pin_hash: str | None
    # Send the session cookie over HTTPS only. Must be on in production.
    https_only: bool = False
    # Wait estimate before today has enough finished consults to measure.
    default_consult_minutes: float = 8
    # Public address printed in the QR code, e.g. https://queue.example.com
    public_base_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            database_url=os.environ.get("DATABASE_URL"),
            secret_key=os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32),
            desk_pin_hash=os.environ.get("DESK_PIN_HASH"),
            https_only=os.environ.get("HTTPS_ONLY", "").lower() in {"1", "true", "yes"},
            default_consult_minutes=float(os.environ.get("DEFAULT_CONSULT_MINUTES") or 8),
            public_base_url=os.environ.get("PUBLIC_BASE_URL") or None,
        )

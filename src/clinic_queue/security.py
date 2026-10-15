"""Desk PIN hashing and login rate limiting.

A 4-digit PIN has only 10,000 values, so the hash alone can't stop guessing.
The rate limiter is the real protection: 5 wrong tries locks that client out
for 5 minutes, so trying every PIN would take about a week.

Generate settings for .env with:  uv run python -m clinic_queue.security 1234
"""

import base64
import hashlib
import hmac
import re
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

PIN_PATTERN = re.compile(r"\d{4}")

# scrypt cost parameters: ~16 MB of memory per hash, deliberately slow.
_N, _R, _P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            pin.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    # Constant-time comparison: timing doesn't reveal how close a guess was.
    return hmac.compare_digest(actual, expected)


@dataclass
class _Attempts:
    failures: int = 0
    locked_until: float = 0.0


class LoginLimiter:
    """Counts failed logins per client and locks the client out after too many.

    Kept in memory: fine for one server process. Restarting the app clears it.
    """

    def __init__(
        self,
        max_failures: int = 5,
        lockout_seconds: float = 300,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self.clock = clock
        self._attempts: dict[str, _Attempts] = {}

    def seconds_locked(self, key: str) -> float:
        """Seconds until `key` may try again (0 if not locked)."""
        attempts = self._attempts.get(key)
        return max(0.0, attempts.locked_until - self.clock()) if attempts else 0.0

    def record_failure(self, key: str) -> None:
        attempts = self._attempts.setdefault(key, _Attempts())
        attempts.failures += 1
        if attempts.failures >= self.max_failures:
            attempts.locked_until = self.clock() + self.lockout_seconds
            attempts.failures = 0

    def record_success(self, key: str) -> None:
        self._attempts.pop(key, None)


if __name__ == "__main__":
    if len(sys.argv) != 2 or not PIN_PATTERN.fullmatch(sys.argv[1]):
        sys.exit("usage: python -m clinic_queue.security <4-digit PIN>")
    print(f"DESK_PIN_HASH={hash_pin(sys.argv[1])}")
    print(f"SECRET_KEY={secrets.token_urlsafe(32)}")

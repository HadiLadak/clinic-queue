"""Core queue operations: sessions, issuing tokens, Next, Undo, Reset.

Every function takes an open psycopg connection in autocommit mode and does its
work inside `with conn.transaction():`, so each operation is all-or-nothing.

Concurrency rule: every write first locks the open session's row
(`SELECT ... FOR UPDATE`). Two requests for the same session therefore run one
after the other, never interleaved, which is what keeps token numbers unique
and consecutive and makes double-tapped Next/Undo safe.

`now` is passed in rather than read from the clock so tests can control time.
It must be timezone-aware and is used for every timestamp written.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg

CLINIC_TZ = ZoneInfo("Asia/Karachi")
# A clinic day runs from 04:00 to 04:00 Pakistan time, so evening shifts that
# run past midnight stay in one session.
DAY_START_HOUR = 4
MAX_NAME_LENGTH = 60

_TOKEN_COLUMNS = "id, number, name, status"


@dataclass(frozen=True)
class Token:
    id: int
    number: int
    name: str | None
    status: str  # 'waiting' | 'serving' | 'done'


def _to_token(row: tuple | None) -> Token | None:
    return Token(*row) if row else None


def clinic_day_start(now: datetime) -> datetime:
    """Return the start (04:00 Asia/Karachi) of the clinic day that `now` falls in."""
    local = now.astimezone(CLINIC_TZ)
    start = local.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if local.hour < DAY_START_HOUR:
        start -= timedelta(days=1)
    return start


def current_session_id(conn: psycopg.Connection, now: datetime) -> int:
    """Return the open session's id, starting a new one if needed (automatic daily reset).

    A new session is needed when there is no open session, or the open one started
    before today's clinic day began.
    """
    with conn.transaction():
        row = conn.execute(
            "SELECT id, started_at FROM sessions WHERE ended_at IS NULL FOR UPDATE"
        ).fetchone()
        if row and row[1] >= clinic_day_start(now):
            return row[0]
        if row:
            conn.execute("UPDATE sessions SET ended_at = %s WHERE id = %s", (now, row[0]))
        # Two first-ever requests can both find no open session (FOR UPDATE has no row
        # to lock). The one-open-session index makes the loser's INSERT a no-op.
        new = conn.execute(
            "INSERT INTO sessions (started_at) VALUES (%s)"
            " ON CONFLICT ((true)) WHERE ended_at IS NULL DO NOTHING RETURNING id",
            (now,),
        ).fetchone()
        if new:
            return new[0]
    # Lost the race: the winner's session is committed now, so read it.
    return current_session_id(conn, now)


def reset(conn: psycopg.Connection, now: datetime) -> int:
    """The "Reset queue" button: close the open session (if any), open a new one, return its id."""
    with conn.transaction():
        conn.execute("UPDATE sessions SET ended_at = %s WHERE ended_at IS NULL", (now,))
        return conn.execute(
            "INSERT INTO sessions (started_at) VALUES (%s) RETURNING id", (now,)
        ).fetchone()[0]


def _lock_session(conn: psycopg.Connection, session_id: int) -> None:
    conn.execute("SELECT 1 FROM sessions WHERE id = %s FOR UPDATE", (session_id,))


def issue_token(
    conn: psycopg.Connection, request_id: UUID, name: str | None, now: datetime
) -> Token:
    """Add a patient to the open session and return their token.

    `name` is optional: whitespace is stripped, blank means None, and names longer
    than MAX_NAME_LENGTH raise ValueError. Calling again with the same request_id
    returns the original token without using up a number.
    """
    name = (name or "").strip() or None
    if name is not None and len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Name must be at most {MAX_NAME_LENGTH} characters")

    session_id = current_session_id(conn, now)
    with conn.transaction():
        _lock_session(conn, session_id)
        # Checked after the lock, before bumping the counter: a duplicate of this
        # request that got here first has committed, so we see it and burn no number.
        existing = conn.execute(
            f"SELECT {_TOKEN_COLUMNS} FROM tokens WHERE request_id = %s", (request_id,)
        ).fetchone()
        if existing:
            return _to_token(existing)

        number = conn.execute(
            "UPDATE sessions SET last_number = last_number + 1 WHERE id = %s RETURNING last_number",
            (session_id,),
        ).fetchone()[0]
        row = conn.execute(
            "INSERT INTO tokens (session_id, number, name, request_id, created_at)"
            f" VALUES (%s, %s, %s, %s, %s) RETURNING {_TOKEN_COLUMNS}",
            (session_id, number, name, request_id, now),
        ).fetchone()
    return _to_token(row)


def _serving(conn: psycopg.Connection, session_id: int) -> Token | None:
    return _to_token(
        conn.execute(
            f"SELECT {_TOKEN_COLUMNS} FROM tokens WHERE session_id = %s AND status = 'serving'",
            (session_id,),
        ).fetchone()
    )


def _is_stale(current: Token | None, expected_serving: int | None) -> bool:
    """True if the desk screen's "now serving" no longer matches the database."""
    return (current.number if current else None) != expected_serving


def call_next(
    conn: psycopg.Connection, expected_serving: int | None, now: datetime
) -> Token | None:
    """The "Next patient" button. Returns the token now being served (None if nobody).

    `expected_serving` is the number the desk screen showed as "now serving" (None if
    nobody). If it doesn't match, the screen is stale (double tap, or another phone
    already pressed Next), so nothing changes and the current serving token is returned.
    """
    session_id = current_session_id(conn, now)
    with conn.transaction():
        _lock_session(conn, session_id)
        current = _serving(conn, session_id)
        if _is_stale(current, expected_serving):
            return current

        # Finish the current patient first: only one 'serving' row may exist.
        if current:
            conn.execute(
                "UPDATE tokens SET status = 'done', finished_at = %s WHERE id = %s",
                (now, current.id),
            )
        row = conn.execute(
            "UPDATE tokens SET status = 'serving', called_at = %s WHERE id = ("
            "  SELECT id FROM tokens WHERE session_id = %s AND status = 'waiting'"
            "  ORDER BY number LIMIT 1"
            f") RETURNING {_TOKEN_COLUMNS}",
            (now, session_id),
        ).fetchone()
    return _to_token(row)


def undo(conn: psycopg.Connection, expected_serving: int | None, now: datetime) -> Token | None:
    """The "Undo" button: reverse the most recent Next. Returns the token now being served.

    Same stale-screen rule as call_next. The serving patient goes back to 'waiting'
    (lowest number, so they're first in line again) and the most recently finished
    patient is served again. If nobody has finished yet, nothing changes.
    """
    session_id = current_session_id(conn, now)
    with conn.transaction():
        _lock_session(conn, session_id)
        current = _serving(conn, session_id)
        if _is_stale(current, expected_serving):
            return current

        last_done = conn.execute(
            "SELECT id FROM tokens WHERE session_id = %s AND status = 'done'"
            " ORDER BY finished_at DESC, number DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if not last_done:
            return current

        if current:
            conn.execute(
                "UPDATE tokens SET status = 'waiting', called_at = NULL WHERE id = %s",
                (current.id,),
            )
        row = conn.execute(
            "UPDATE tokens SET status = 'serving', finished_at = NULL WHERE id = %s"
            f" RETURNING {_TOKEN_COLUMNS}",
            (last_done[0],),
        ).fetchone()
    return _to_token(row)

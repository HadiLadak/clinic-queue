"""Read-only queue status for patients: people ahead and the estimated wait.

Nothing here writes to the database, so the public /status page can't change
the queue (or start a new day's session) no matter what it's asked.
"""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import psycopg

from clinic_queue.queue_ops import clinic_day_start

# Median of the most recent consults, so the estimate follows today's pace.
RECENT_CONSULTS = 10
# With fewer finished consults than this, fall back to the configured default.
MIN_CONSULTS = 3

# "overview": no token entered, only "now serving" is shown.
State = Literal["not_started", "overview", "not_found", "waiting", "serving", "done"]


@dataclass(frozen=True)
class PatientStatus:
    state: State
    now_serving: int | None = None
    ahead: int = 0
    wait_seconds: float | None = None
    rough_estimate: bool = False


def open_session_today(conn: psycopg.Connection, now: datetime) -> int | None:
    """The open session's id, or None if there isn't one for today's clinic day."""
    row = conn.execute("SELECT id, started_at FROM sessions WHERE ended_at IS NULL").fetchone()
    if row and row[1] >= clinic_day_start(now):
        return row[0]
    return None


def typical_consult_seconds(conn: psycopg.Connection, session_id: int) -> float | None:
    """Median length of the last RECENT_CONSULTS consults, or None if too few so far.

    Median, not mean: one long consult (or the doctor's break) barely moves it.
    """
    rows = conn.execute(
        "SELECT extract(epoch FROM finished_at - called_at) FROM tokens"
        " WHERE session_id = %s AND status = 'done'"
        " AND called_at IS NOT NULL AND finished_at IS NOT NULL"
        " ORDER BY finished_at DESC LIMIT %s",
        (session_id, RECENT_CONSULTS),
    ).fetchall()
    if len(rows) < MIN_CONSULTS:
        return None
    return float(statistics.median(float(r[0]) for r in rows))


def estimate_wait_seconds(ahead: int, typical: float, current_elapsed: float | None) -> float:
    """Everyone waiting ahead takes a typical consult; the current one has some time left.

    `current_elapsed` is how long the patient being seen has been in (None if nobody).
    A consult already running longer than typical is assumed to be nearly done.
    """
    remaining_current = max(typical - current_elapsed, 0.0) if current_elapsed is not None else 0.0
    return ahead * typical + remaining_current


def patient_status(
    conn: psycopg.Connection, number: int | None, now: datetime, default_consult_seconds: float
) -> PatientStatus:
    """What the patient holding token `number` should see (number=None: just "now serving")."""
    session_id = open_session_today(conn, now)
    if session_id is None:
        return PatientStatus(state="not_started")

    serving = conn.execute(
        "SELECT number, called_at FROM tokens WHERE session_id = %s AND status = 'serving'",
        (session_id,),
    ).fetchone()
    now_serving = serving[0] if serving else None
    if number is None:
        return PatientStatus(state="overview", now_serving=now_serving)

    row = conn.execute(
        "SELECT status FROM tokens WHERE session_id = %s AND number = %s", (session_id, number)
    ).fetchone()
    if row is None:
        return PatientStatus(state="not_found", now_serving=now_serving)
    if row[0] != "waiting":
        return PatientStatus(state=row[0], now_serving=now_serving)

    ahead = conn.execute(
        "SELECT count(*) FROM tokens WHERE session_id = %s AND status = 'waiting' AND number < %s",
        (session_id, number),
    ).fetchone()[0]
    typical = typical_consult_seconds(conn, session_id)
    elapsed = (now - serving[1]).total_seconds() if serving and serving[1] else None
    return PatientStatus(
        state="waiting",
        now_serving=now_serving,
        ahead=ahead,
        wait_seconds=estimate_wait_seconds(ahead, typical or default_consult_seconds, elapsed),
        rough_estimate=typical is None,
    )

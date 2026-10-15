"""Tests for the core queue operations in clinic_queue.queue_ops."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from clinic_queue.queue_ops import (
    CLINIC_TZ,
    MAX_NAME_LENGTH,
    call_next,
    clinic_day_start,
    current_session_id,
    issue_token,
    reset,
    undo,
)

# 09:00 on a clinic morning, Pakistan time.
T0 = datetime(2026, 10, 14, 9, 0, tzinfo=CLINIC_TZ)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def rid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def conn(connect):
    with connect(autocommit=True) as c:
        yield c


def statuses(conn) -> dict[int, str]:
    rows = conn.execute("SELECT number, status FROM tokens ORDER BY number").fetchall()
    return dict(rows)


def add_patients(conn, count: int) -> None:
    for i in range(count):
        issue_token(conn, rid(), None, at(i))


# --- clinic_day_start -------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Morning: day started at 04:00 today.
        (datetime(2026, 10, 14, 10, 0, tzinfo=CLINIC_TZ), datetime(2026, 10, 14, 4, 0)),
        # Exactly 04:00 is the start of a new day.
        (datetime(2026, 10, 14, 4, 0, tzinfo=CLINIC_TZ), datetime(2026, 10, 14, 4, 0)),
        # 01:30 after an evening shift still belongs to the previous day.
        (datetime(2026, 10, 14, 1, 30, tzinfo=CLINIC_TZ), datetime(2026, 10, 13, 4, 0)),
        # UTC input: 23:30 UTC on the 13th is 04:30 on the 14th in Karachi.
        (datetime(2026, 10, 13, 23, 30, tzinfo=UTC), datetime(2026, 10, 14, 4, 0)),
    ],
)
def test_clinic_day_start(now, expected):
    assert clinic_day_start(now) == expected.replace(tzinfo=CLINIC_TZ)


# --- sessions and reset ------------------------------------------------------


def test_current_session_is_created_then_reused(conn):
    first = current_session_id(conn, at(0))
    assert current_session_id(conn, at(60)) == first


def test_session_survives_past_midnight(conn):
    evening = datetime(2026, 10, 14, 20, 0, tzinfo=CLINIC_TZ)
    after_midnight = datetime(2026, 10, 15, 1, 0, tzinfo=CLINIC_TZ)
    assert current_session_id(conn, after_midnight) == current_session_id(conn, evening)


def test_new_session_starts_automatically_next_morning(conn):
    today = current_session_id(conn, at(0))
    tomorrow = current_session_id(conn, at(0) + timedelta(days=1))

    assert tomorrow != today
    open_sessions = conn.execute("SELECT id FROM sessions WHERE ended_at IS NULL").fetchall()
    assert open_sessions == [(tomorrow,)]


def test_numbers_restart_at_one_on_next_day(conn):
    add_patients(conn, 3)
    token = issue_token(conn, rid(), None, at(0) + timedelta(days=1))
    assert token.number == 1


def test_reset_closes_session_and_restarts_numbers(conn):
    add_patients(conn, 3)
    old = current_session_id(conn, at(10))

    new = reset(conn, at(11))

    assert new != old
    assert current_session_id(conn, at(12)) == new
    assert issue_token(conn, rid(), None, at(13)).number == 1


def test_reset_with_no_session_creates_one(conn):
    new = reset(conn, at(0))
    assert current_session_id(conn, at(1)) == new


# --- issue_token ---------------------------------------------------------------


def test_tokens_are_numbered_from_one_and_wait(conn):
    first = issue_token(conn, rid(), "Ayesha", at(0))
    second = issue_token(conn, rid(), None, at(1))

    assert (first.number, first.name, first.status) == (1, "Ayesha", "waiting")
    assert (second.number, second.name, second.status) == (2, None, "waiting")


@pytest.mark.parametrize(("raw", "stored"), [("  Bilal  ", "Bilal"), ("", None), ("   ", None)])
def test_name_is_trimmed_and_blank_means_none(conn, raw, stored):
    assert issue_token(conn, rid(), raw, at(0)).name == stored


def test_overlong_name_is_rejected_without_using_a_number(conn):
    with pytest.raises(ValueError):
        issue_token(conn, rid(), "x" * (MAX_NAME_LENGTH + 1), at(0))
    assert issue_token(conn, rid(), None, at(1)).number == 1


def test_same_request_id_returns_same_token(conn):
    request = rid()
    first = issue_token(conn, request, "Ali", at(0))
    again = issue_token(conn, request, "Ali", at(0))

    assert again == first
    assert conn.execute("SELECT count(*) FROM tokens").fetchone()[0] == 1


def test_retried_request_does_not_leave_a_gap(conn):
    request = rid()
    issue_token(conn, request, None, at(0))
    issue_token(conn, request, None, at(0))

    assert issue_token(conn, rid(), None, at(1)).number == 2


# --- concurrency -----------------------------------------------------------------

WORKERS = 10  # Stay well under the Supabase free-tier pooler connection limit.


def run_concurrently(connect, request_ids):
    """Each request runs on its own connection; a barrier releases them all at once."""
    barrier = threading.Barrier(len(request_ids))

    def worker(request_id):
        with connect(autocommit=True) as c:
            barrier.wait()
            return issue_token(c, request_id, None, at(0))

    with ThreadPoolExecutor(max_workers=len(request_ids)) as pool:
        return list(pool.map(worker, request_ids))


def test_concurrent_requests_get_unique_consecutive_numbers(connect, conn):
    current_session_id(conn, at(0))

    tokens = run_concurrently(connect, [rid() for _ in range(WORKERS)])

    assert sorted(t.number for t in tokens) == list(range(1, WORKERS + 1))


def test_concurrent_first_requests_share_one_session(connect, conn):
    # No session exists yet: every worker races to create one.
    tokens = run_concurrently(connect, [rid() for _ in range(WORKERS)])

    assert sorted(t.number for t in tokens) == list(range(1, WORKERS + 1))
    assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1


def test_concurrent_same_request_id_issues_one_token_and_no_gap(connect, conn):
    current_session_id(conn, at(0))
    request = rid()

    tokens = run_concurrently(connect, [request] * WORKERS)

    assert {t.number for t in tokens} == {1}
    assert issue_token(conn, rid(), None, at(1)).number == 2


# --- call_next ---------------------------------------------------------------------


def test_next_on_empty_queue_returns_none(conn):
    assert call_next(conn, None, at(0)) is None


def test_next_serves_patients_in_order(conn):
    add_patients(conn, 3)

    assert call_next(conn, None, at(5)).number == 1
    assert call_next(conn, 1, at(10)).number == 2
    assert statuses(conn) == {1: "done", 2: "serving", 3: "waiting"}


def test_next_records_call_and_finish_times(conn):
    add_patients(conn, 2)
    call_next(conn, None, at(5))
    call_next(conn, 1, at(12))

    rows = conn.execute("SELECT number, called_at, finished_at FROM tokens ORDER BY number")
    assert rows.fetchall() == [(1, at(5), at(12)), (2, at(12), None)]


def test_double_tapped_next_only_advances_once(conn):
    add_patients(conn, 3)
    call_next(conn, None, at(5))

    # Both taps were sent from a screen showing "now serving #1".
    call_next(conn, 1, at(10))
    second_tap = call_next(conn, 1, at(10))

    assert second_tap.number == 2
    assert statuses(conn) == {1: "done", 2: "serving", 3: "waiting"}


def test_next_after_last_patient_finishes_them(conn):
    add_patients(conn, 1)
    call_next(conn, None, at(5))

    assert call_next(conn, 1, at(10)) is None
    assert statuses(conn) == {1: "done"}


# --- undo ------------------------------------------------------------------------------


def test_undo_reverses_last_next(conn):
    add_patients(conn, 3)
    call_next(conn, None, at(5))
    call_next(conn, 1, at(10))

    serving = undo(conn, 2, at(11))

    assert serving.number == 1
    assert statuses(conn) == {1: "serving", 2: "waiting", 3: "waiting"}
    row = conn.execute("SELECT called_at, finished_at FROM tokens WHERE number = 2").fetchone()
    assert row == (None, None)


def test_undo_then_next_calls_the_same_patient_again(conn):
    add_patients(conn, 3)
    call_next(conn, None, at(5))
    call_next(conn, 1, at(10))
    undo(conn, 2, at(11))

    assert call_next(conn, 1, at(12)).number == 2


def test_repeated_undo_steps_back_further(conn):
    add_patients(conn, 3)
    call_next(conn, None, at(5))
    call_next(conn, 1, at(10))
    call_next(conn, 2, at(15))

    undo(conn, 3, at(16))
    assert undo(conn, 2, at(17)).number == 1
    assert statuses(conn) == {1: "serving", 2: "waiting", 3: "waiting"}


def test_undo_after_queue_finished_brings_back_last_patient(conn):
    add_patients(conn, 1)
    call_next(conn, None, at(5))
    call_next(conn, 1, at(10))  # Queue is now empty: nobody serving.

    assert undo(conn, None, at(11)).number == 1
    assert statuses(conn) == {1: "serving"}


def test_undo_with_nothing_finished_changes_nothing(conn):
    add_patients(conn, 2)
    call_next(conn, None, at(5))

    assert undo(conn, 1, at(6)).number == 1
    assert statuses(conn) == {1: "serving", 2: "waiting"}


def test_double_tapped_undo_only_reverses_once(conn):
    add_patients(conn, 3)
    call_next(conn, None, at(5))
    call_next(conn, 1, at(10))

    undo(conn, 2, at(11))
    second_tap = undo(conn, 2, at(11))  # Stale screen still showed #2.

    assert second_tap.number == 1
    assert statuses(conn) == {1: "serving", 2: "waiting", 3: "waiting"}

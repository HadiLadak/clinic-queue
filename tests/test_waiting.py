"""Tests for the read-only patient status and wait estimate (clinic_queue.waiting)."""

import uuid
from datetime import datetime, timedelta

import pytest

from clinic_queue.queue_ops import CLINIC_TZ, call_next, current_session_id, issue_token
from clinic_queue.waiting import (
    estimate_wait_seconds,
    patient_status,
    typical_consult_seconds,
)

T0 = datetime(2026, 10, 14, 9, 0, tzinfo=CLINIC_TZ)
DEFAULT = 8 * 60


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


@pytest.fixture
def conn(connect):
    with connect(autocommit=True) as c:
        yield c


def add_patients(conn, count: int) -> None:
    for _ in range(count):
        issue_token(conn, uuid.uuid4(), None, at(0))


def run_consults(conn, minutes: list[float]) -> float:
    """Serve one patient per entry, each consult lasting that many minutes.

    Returns the time (in minutes after T0) when the last consult ended.
    """
    t = 1.0
    expected = None
    for length in [0, *minutes]:
        t += length
        token = call_next(conn, expected, at(t))
        expected = token.number if token else None
    return t


# --- estimate_wait_seconds ----------------------------------------------------


def test_estimate_counts_everyone_ahead_plus_rest_of_current_consult():
    assert estimate_wait_seconds(ahead=3, typical=600, current_elapsed=200) == 3 * 600 + 400


def test_estimate_when_current_consult_is_overrunning():
    assert estimate_wait_seconds(ahead=2, typical=600, current_elapsed=900) == 1200


def test_estimate_when_nobody_is_being_seen():
    assert estimate_wait_seconds(ahead=2, typical=600, current_elapsed=None) == 1200


# --- typical_consult_seconds ------------------------------------------------------


def test_typical_is_none_with_too_few_consults(conn):
    add_patients(conn, 3)
    run_consults(conn, [5, 6])
    assert typical_consult_seconds(conn, current_session_id(conn, at(30))) is None


def test_typical_is_median_so_one_long_consult_barely_moves_it(conn):
    add_patients(conn, 5)
    run_consults(conn, [5, 6, 7, 60])  # the doctor took a break during one consult

    assert typical_consult_seconds(conn, current_session_id(conn, at(90))) == 6.5 * 60


def test_typical_uses_only_recent_consults(conn):
    add_patients(conn, 16)
    run_consults(conn, [30] * 5 + [4] * 10)  # slow morning, fast now

    assert typical_consult_seconds(conn, current_session_id(conn, at(300))) == 4 * 60


# --- patient_status -----------------------------------------------------------------


def test_status_before_queue_starts_is_not_started(conn):
    assert patient_status(conn, 1, at(0), DEFAULT).state == "not_started"


def test_status_does_not_create_a_session(conn):
    patient_status(conn, 1, at(0), DEFAULT)
    assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_yesterdays_queue_counts_as_not_started(conn):
    add_patients(conn, 2)
    assert patient_status(conn, 1, at(0) + timedelta(days=1), DEFAULT).state == "not_started"


def test_overview_without_token_shows_now_serving(conn):
    add_patients(conn, 2)
    call_next(conn, None, at(1))

    status = patient_status(conn, None, at(2), DEFAULT)

    assert (status.state, status.now_serving) == ("overview", 1)


def test_unknown_token_is_not_found(conn):
    add_patients(conn, 2)
    assert patient_status(conn, 9, at(1), DEFAULT).state == "not_found"


def test_waiting_patient_sees_people_ahead_and_rough_default_estimate(conn):
    add_patients(conn, 4)
    call_next(conn, None, at(1))  # #1 is in with the doctor

    status = patient_status(conn, 4, at(3), DEFAULT)

    assert status.state == "waiting"
    assert status.now_serving == 1
    assert status.ahead == 2  # #2 and #3
    # 2 ahead × 8 min + 6 min left of #1's consult
    assert status.wait_seconds == 2 * DEFAULT + 6 * 60
    assert status.rough_estimate


def test_estimate_uses_todays_median_once_there_is_enough_data(conn):
    add_patients(conn, 6)
    end = run_consults(conn, [4, 4, 4])  # #4 is now being seen

    status = patient_status(conn, 6, at(end), DEFAULT)

    assert status.ahead == 1
    assert status.wait_seconds == 4 * 60 + 4 * 60
    assert not status.rough_estimate


def test_next_in_line_has_nobody_ahead(conn):
    add_patients(conn, 2)
    call_next(conn, None, at(1))
    assert patient_status(conn, 2, at(2), DEFAULT).ahead == 0


def test_serving_and_done_states(conn):
    add_patients(conn, 2)
    call_next(conn, None, at(1))
    call_next(conn, 1, at(5))

    assert patient_status(conn, 2, at(6), DEFAULT).state == "serving"
    assert patient_status(conn, 1, at(6), DEFAULT).state == "done"

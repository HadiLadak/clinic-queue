"""Tests for the public /status page."""

import uuid
from datetime import UTC, datetime

import pytest

from clinic_queue.config import Settings
from clinic_queue.queue_ops import call_next, issue_token
from clinic_queue.status import wait_text


@pytest.fixture
def client(make_client):
    return make_client(Settings(database_url=None, secret_key="s", desk_pin_hash=None))


@pytest.fixture
def conn(connect):
    with connect(autocommit=True) as c:
        yield c


def add(conn, name=None):
    return issue_token(conn, uuid.uuid4(), name, datetime.now(UTC))


def test_status_page_without_queue(client):
    response = client.get("/status")
    assert response.status_code == 200
    assert "hasn&#39;t started yet" in response.text
    assert 'name="token"' in response.text


def test_status_page_never_starts_a_session(client, conn):
    client.get("/status?token=1")
    client.get("/status/panel?token=1")
    assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_waiting_patient_sees_place_in_line(client, conn):
    for _ in range(3):
        add(conn)
    call_next(conn, None, datetime.now(UTC))

    response = client.get("/status?token=3")

    assert "#1" in response.text  # now serving
    assert "1 person ahead of you" in response.text
    assert "Estimated wait" in response.text
    assert "Rough estimate" in response.text


def test_next_in_line_is_told_so(client, conn):
    add(conn)
    add(conn)
    call_next(conn, None, datetime.now(UTC))
    assert "You&#39;re next" in client.get("/status?token=2").text


def test_called_patient_sees_their_turn(client, conn):
    add(conn)
    call_next(conn, None, datetime.now(UTC))
    assert "It&#39;s your turn" in client.get("/status?token=1").text


def test_unknown_token_is_explained(client, conn):
    add(conn)
    assert "is not in today&#39;s queue" in client.get("/status?token=42").text


@pytest.mark.parametrize("token", ["abc", "0", "12345", "-1"])
def test_invalid_token_shows_hint(client, conn, token):
    add(conn)
    assert "Enter the number printed" in client.get(f"/status?token={token}").text


def test_hash_prefix_is_accepted(client, conn):
    add(conn)
    add(conn)
    assert "1 person ahead" in client.get("/status?token=%232").text


def test_patient_names_are_never_shown(client, conn):
    add(conn, name="Secret Name")
    call_next(conn, None, datetime.now(UTC))
    add(conn, name="Another Name")

    for path in ["/status", "/status?token=1", "/status?token=2", "/status/panel?token=2"]:
        text = client.get(path).text
        assert "Secret Name" not in text
        assert "Another Name" not in text


def test_panel_polls_with_the_token(client, conn):
    add(conn)
    response = client.get("/status/panel?token=1")
    assert 'hx-get="/status/panel?token=1"' in response.text
    assert "every 10s" in response.text


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (60, "a few minutes"),
        (4 * 60 + 59, "a few minutes"),
        (23 * 60, "about 25 min"),
        (37 * 60, "about 35 min"),
        (60 * 60, "about 1 h"),
        (100 * 60, "about 1 h 45 min"),
    ],
)
def test_wait_text_is_rounded(seconds, text):
    assert wait_text(seconds) == text

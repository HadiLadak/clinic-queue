"""Tests for the /desk page, driven through FastAPI's TestClient."""

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from clinic_queue.config import Settings
from clinic_queue.db import get_conn
from clinic_queue.main import create_app
from clinic_queue.security import hash_pin

PIN = "4821"
PIN_HASH = hash_pin(PIN)


@pytest.fixture
def client(connect):
    app = create_app(Settings(database_url=None, secret_key="test-secret", desk_pin_hash=PIN_HASH))

    def test_conn():
        with connect(autocommit=True) as conn:
            yield conn

    app.dependency_overrides[get_conn] = test_conn
    return TestClient(app)


@pytest.fixture
def desk(client):
    response = client.post("/desk/login", data={"pin": PIN})
    assert response.status_code == 200
    return client


def request_id_in(html: str) -> str:
    return re.search(r'name="request_id" value="([0-9a-f-]{36})"', html).group(1)


def serving_number(html: str) -> str | None:
    match = re.search(r'id="serving".*?class="big-number">#(\d+)<', html, re.S)
    return match.group(1) if match else None


def add(desk, name="", request_id=None):
    data = {"request_id": request_id or str(uuid.uuid4()), "name": name}
    return desk.post("/desk/tokens", data=data)


# --- login -------------------------------------------------------------------


def test_logged_out_desk_shows_pin_form(client):
    response = client.get("/desk")
    assert response.status_code == 200
    assert 'name="pin"' in response.text
    assert "Next patient" not in response.text


def test_wrong_pin_is_rejected(client):
    response = client.post("/desk/login", data={"pin": "0000"})
    assert response.status_code == 401
    assert "Wrong PIN" in response.text


def test_non_numeric_pin_is_rejected(client):
    assert client.post("/desk/login", data={"pin": "abcd"}).status_code == 401


def test_correct_pin_opens_desk(desk):
    page = desk.get("/desk")
    assert "Next patient" in page.text
    assert "Add patient" in page.text


def test_lockout_after_five_wrong_pins_blocks_even_the_right_one(client):
    for _ in range(5):
        client.post("/desk/login", data={"pin": "0000"})

    response = client.post("/desk/login", data={"pin": PIN})

    assert response.status_code == 429
    assert "Too many wrong tries" in response.text


def test_missing_pin_configuration_disables_login(connect):
    app = create_app(Settings(database_url=None, secret_key="s", desk_pin_hash=None))
    response = TestClient(app).post("/desk/login", data={"pin": PIN})
    assert response.status_code == 503


def test_logout_returns_to_pin_form(desk):
    response = desk.post("/desk/logout")
    assert 'name="pin"' in response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/desk/tokens"),
        ("post", "/desk/next"),
        ("post", "/desk/undo"),
        ("post", "/desk/reset"),
        ("get", "/desk/panel"),
    ],
)
def test_actions_require_login(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.headers["HX-Redirect"] == "/desk"


def test_session_cookie_is_http_only_and_same_site(client):
    response = client.post("/desk/login", data={"pin": PIN}, follow_redirects=False)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


# --- adding patients -----------------------------------------------------------


def test_add_patient_shows_token_and_updates_waiting_list(desk):
    response = add(desk, name="Ayesha")

    assert "Token #1: Ayesha" in response.text
    assert "Waiting (1)" in response.text
    assert 'hx-swap-oob="true"' in response.text


def test_each_add_returns_a_fresh_request_id(desk):
    first = request_id_in(desk.get("/desk").text)
    second = request_id_in(add(desk, request_id=first).text)
    assert second != first


def test_double_submitted_add_issues_one_token(desk):
    request_id = request_id_in(desk.get("/desk").text)

    add(desk, request_id=request_id)
    retry = add(desk, request_id=request_id)

    assert "Token #1" in retry.text
    assert "Waiting (1)" in retry.text


def test_overlong_name_shows_error_and_keeps_request_id(desk):
    request_id = str(uuid.uuid4())
    response = add(desk, name="x" * 61, request_id=request_id)

    assert "Name is too long" in response.text
    assert request_id_in(response.text) == request_id
    assert "Waiting (0)" in response.text


def test_names_are_html_escaped(desk):
    response = add(desk, name="<b>x</b>")
    assert "&lt;b&gt;x&lt;/b&gt;" in response.text
    assert "<b>x</b>" not in response.text


def test_invalid_request_id_is_rejected(desk):
    assert add(desk, request_id="not-a-uuid").status_code == 400


# --- next / undo / reset ----------------------------------------------------------


def test_next_and_undo_update_now_serving(desk):
    add(desk)
    add(desk)

    assert serving_number(desk.post("/desk/next", data={"expected": ""}).text) == "1"
    assert serving_number(desk.post("/desk/next", data={"expected": "1"}).text) == "2"
    assert serving_number(desk.post("/desk/undo", data={"expected": "2"}).text) == "1"


def test_retried_next_from_stale_screen_does_not_skip_a_patient(desk):
    for _ in range(3):
        add(desk)
    desk.post("/desk/next", data={"expected": ""})

    desk.post("/desk/next", data={"expected": "1"})
    retry = desk.post("/desk/next", data={"expected": "1"})

    assert serving_number(retry.text) == "2"


def test_invalid_expected_number_is_rejected(desk):
    assert desk.post("/desk/next", data={"expected": "abc"}).status_code == 400


def test_reset_starts_again_from_one(desk):
    add(desk)
    add(desk)

    response = desk.post("/desk/reset")

    assert "Queue reset" in response.text
    assert "Waiting (0)" in response.text
    assert "Token #1" in add(desk).text


def test_panel_shows_current_state(desk):
    add(desk, name="Bilal")
    panel = desk.get("/desk/panel")
    assert "Bilal" in panel.text
    assert "Waiting (1)" in panel.text

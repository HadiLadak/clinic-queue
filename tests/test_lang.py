"""Tests for the English/Urdu toggle, right-to-left layout and the QR poster."""

import re
import string

import pytest

from clinic_queue.config import Settings
from clinic_queue.i18n import SUPPORTED_LANGS, load, pick_lang
from clinic_queue.poster import qr_svg
from clinic_queue.security import hash_pin

PIN = "4821"


@pytest.fixture
def client(make_client):
    return make_client(Settings(database_url=None, secret_key="s", desk_pin_hash=hash_pin(PIN)))


def html_dir(text: str) -> str:
    return re.search(r'<html lang="(\w+)" dir="(\w+)"', text).group(2)


# --- choosing a language ---------------------------------------------------------


@pytest.mark.parametrize(
    ("cookie", "header", "expected"),
    [
        (None, "", "en"),
        (None, "ur-PK,ur;q=0.9,en;q=0.8", "ur"),
        (None, "en-US,en;q=0.9,ur;q=0.5", "en"),
        (None, "fr-FR,ur;q=0.5", "ur"),
        ("ur", "en-US", "ur"),
        ("xx", "en-US", "en"),
    ],
)
def test_pick_lang(cookie, header, expected):
    assert pick_lang(cookie, header) == expected


def test_english_by_default(client):
    response = client.get("/status")
    assert '<html lang="en" dir="ltr">' in response.text
    assert "Queue status" in response.text


def test_urdu_phone_gets_urdu_right_to_left(client):
    response = client.get("/status", headers={"Accept-Language": "ur-PK,ur;q=0.9"})
    assert '<html lang="ur" dir="rtl">' in response.text
    assert load("ur")["status.title"] in response.text


def test_toggle_sets_cookie_and_returns_to_same_page(client):
    response = client.get("/lang/ur?next=/status%3Ftoken%3D2", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/status?token=2"
    assert "lang=ur" in response.headers["set-cookie"]
    assert html_dir(client.get("/status").text) == "rtl"


def test_unknown_language_is_404(client):
    assert client.get("/lang/fr", follow_redirects=False).status_code == 404


@pytest.mark.parametrize(
    "target", ["https://evil.example", "//evil.example", "/\\evil.example", "status"]
)
def test_toggle_refuses_to_redirect_off_site(client, target):
    response = client.get("/lang/ur", params={"next": target}, follow_redirects=False)
    assert response.headers["location"] == "/status"


@pytest.mark.parametrize("path", ["/status", "/desk", "/qr"])
def test_every_page_has_the_toggle_back_to_this_page(client, path):
    text = client.get(path).text
    assert f'href="/lang/ur?next={path}"' in text
    assert load("ur")["lang.self_name"] in text


def test_logged_in_desk_is_translated(client):
    client.get("/lang/ur")
    client.post("/desk/login", data={"pin": PIN})
    text = client.get("/desk").text
    assert load("ur")["desk.next"] in text
    assert 'dir="rtl"' in text


def test_server_side_messages_are_translated(client):
    client.get("/lang/ur")
    response = client.post("/desk/login", data={"pin": "0000"})
    assert load("ur")["desk.login.wrong_pin"] in response.text


# --- translation files ------------------------------------------------------------


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("lang", [lang for lang in SUPPORTED_LANGS if lang != "en"])
def test_translation_has_every_key_with_same_placeholders(lang):
    english, other = load("en"), load(lang)
    assert other.keys() == english.keys()
    for key, text in english.items():
        assert placeholders(other[key]) == placeholders(text), key


def test_urdu_numbers_are_not_prefixed_with_hash():
    # "#12" can be reordered to "12#" by right-to-left text layout.
    assert not [key for key, text in load("ur").items() if "#{" in text]


# --- QR poster --------------------------------------------------------------------


def test_poster_has_qr_for_configured_public_url(make_client):
    client = make_client(
        Settings(
            database_url=None,
            secret_key="s",
            desk_pin_hash=None,
            public_base_url="https://queue.example.com/",
        )
    )
    text = client.get("/qr").text

    assert qr_svg("https://queue.example.com/status") in text
    assert "https://queue.example.com/status" in text


def test_poster_falls_back_to_request_address(client):
    text = client.get("/qr").text
    assert qr_svg("http://testserver/status") in text


def test_poster_shows_both_languages_whatever_the_toggle(client):
    client.get("/lang/ur")
    text = client.get("/qr").text
    assert load("en")["qr.title"] in text
    assert load("ur")["qr.title"] in text


def test_qr_svg_is_scalable():
    svg = qr_svg("https://queue.example.com/status")
    assert svg.startswith("<svg")
    assert "viewBox" in svg
    assert 'width="' not in svg.split(">")[0]


def test_root_redirects_to_status(client):
    response = client.get("/", follow_redirects=False)
    assert response.headers["location"] == "/status"

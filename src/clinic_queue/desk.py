"""The receptionist's /desk page.

Every action returns HTML fragments for HTMX. The serving and waiting panels are
sent as out-of-band swaps, so one response can update several parts of the page.
"""

import math
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from clinic_queue.db import Conn
from clinic_queue.i18n import translate
from clinic_queue.queue_ops import (
    MAX_NAME_LENGTH,
    call_next,
    issue_token,
    reset,
    snapshot,
    undo,
)
from clinic_queue.security import PIN_PATTERN, verify_pin
from clinic_queue.web import templates

router = APIRouter(prefix="/desk")


def _now() -> datetime:
    return datetime.now(UTC)


def _logged_in(request: Request) -> bool:
    return request.session.get("desk") is True


def require_desk(request: Request) -> None:
    """Reject desk actions without a login; HTMX follows HX-Redirect to the PIN page."""
    if not _logged_in(request):
        raise HTTPException(status_code=401, headers={"HX-Redirect": "/desk"})


def _parse_expected(value: str) -> int | None:
    """The "now serving" number the screen showed; blank means nobody was serving."""
    value = value.strip()
    if not value:
        return None
    if not value.isdigit():
        raise HTTPException(status_code=400, detail="invalid expected number")
    return int(value)


def _state(request: Request, conn: psycopg.Connection, message: str | None = None):
    """Serving + waiting panels as out-of-band swaps."""
    context = {"snap": snapshot(conn, _now()), "message": message, "oob": True}
    return templates.TemplateResponse(request, "desk/_state.html", context)


def _login_page(request: Request, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "desk/login.html", {"error": error}, status_code=status_code
    )


@router.get("", response_class=HTMLResponse)
def desk_page(request: Request, conn: Conn):
    if not _logged_in(request):
        return _login_page(request)
    context = {"snap": snapshot(conn, _now()), "request_id": uuid4()}
    return templates.TemplateResponse(request, "desk/desk.html", context)


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, pin: Annotated[str, Form()] = ""):
    settings = request.app.state.settings
    limiter = request.app.state.login_limiter
    client = request.client.host if request.client else "unknown"

    if not settings.desk_pin_hash:
        return _login_page(request, translate("desk.login.not_configured", request.state.lang), 503)

    locked = limiter.seconds_locked(client)
    if locked:
        minutes = math.ceil(locked / 60)
        return _login_page(
            request, translate("desk.login.locked", request.state.lang, minutes=minutes), 429
        )

    if PIN_PATTERN.fullmatch(pin) and verify_pin(pin, settings.desk_pin_hash):
        limiter.record_success(client)
        request.session["desk"] = True
        return RedirectResponse("/desk", status_code=303)

    limiter.record_failure(client)
    locked = limiter.seconds_locked(client)
    if locked:
        minutes = math.ceil(locked / 60)
        return _login_page(
            request, translate("desk.login.locked", request.state.lang, minutes=minutes), 429
        )
    return _login_page(request, translate("desk.login.wrong_pin", request.state.lang), 401)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/desk", status_code=303)


@router.get("/panel", response_class=HTMLResponse, dependencies=[Depends(require_desk)])
def panel(request: Request, conn: Conn):
    """Polled every 10 seconds so every open desk screen stays current."""
    return _state(request, conn)


@router.post("/tokens", response_class=HTMLResponse, dependencies=[Depends(require_desk)])
def add_patient(
    request: Request,
    conn: Conn,
    request_id: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
):
    try:
        rid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid request_id") from None

    try:
        token = issue_token(conn, rid, name, _now())
    except ValueError:
        # Keep the same request_id and the typed name so the receptionist can fix it.
        context = {
            "request_id": rid,
            "name": name,
            "error": translate("desk.add.name_too_long", request.state.lang, max=MAX_NAME_LENGTH),
        }
    else:
        # A fresh request_id: the next patient is a new request.
        context = {"request_id": uuid4(), "issued": token}
    context |= {"snap": snapshot(conn, _now()), "oob": True}
    return templates.TemplateResponse(request, "desk/_add_response.html", context)


@router.post("/next", response_class=HTMLResponse, dependencies=[Depends(require_desk)])
def next_patient(request: Request, conn: Conn, expected: Annotated[str, Form()] = ""):
    call_next(conn, _parse_expected(expected), _now())
    return _state(request, conn)


@router.post("/undo", response_class=HTMLResponse, dependencies=[Depends(require_desk)])
def undo_next(request: Request, conn: Conn, expected: Annotated[str, Form()] = ""):
    undo(conn, _parse_expected(expected), _now())
    return _state(request, conn)


@router.post("/reset", response_class=HTMLResponse, dependencies=[Depends(require_desk)])
def reset_queue(request: Request, conn: Conn):
    reset(conn, _now())
    return _state(request, conn, message=translate("desk.reset.done", request.state.lang))

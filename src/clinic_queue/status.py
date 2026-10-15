"""The public /status page patients reach by scanning the QR code. Read-only, no login."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from clinic_queue.db import Conn
from clinic_queue.i18n import DEFAULT_LANG, translate
from clinic_queue.queue_ops import CLINIC_TZ
from clinic_queue.waiting import patient_status
from clinic_queue.web import templates

router = APIRouter(prefix="/status")

MAX_TOKEN_DIGITS = 4


def wait_text(seconds: float, lang: str = DEFAULT_LANG) -> str:
    """Round the estimate so it doesn't promise false precision."""
    minutes = seconds / 60
    if minutes < 5:
        return translate("status.wait_few", lang)
    if minutes < 60:
        return translate("status.wait_minutes", lang, minutes=5 * round(minutes / 5))
    hours, rest = divmod(15 * round(minutes / 15), 60)
    if rest == 0:
        return translate("status.wait_hours", lang, hours=hours)
    return translate("status.wait_hours_minutes", lang, hours=hours, minutes=rest)


def _parse_token(raw: str) -> tuple[int | None, bool]:
    """Returns (token number or None, whether the input was invalid)."""
    raw = raw.strip().lstrip("#")
    if not raw:
        return None, False
    if raw.isdigit() and len(raw) <= MAX_TOKEN_DIGITS and int(raw) > 0:
        return int(raw), False
    return None, True


def _context(request: Request, conn, token: str) -> dict:
    number, invalid = _parse_token(token)
    now = datetime.now(UTC)
    default_seconds = request.app.state.settings.default_consult_minutes * 60
    status = patient_status(conn, number, now, default_seconds)
    return {
        "number": number,
        "invalid": invalid,
        "status": status,
        "wait": wait_text(status.wait_seconds, request.state.lang)
        if status.wait_seconds is not None
        else None,
        "updated": now.astimezone(CLINIC_TZ).strftime("%H:%M"),
    }


@router.get("", response_class=HTMLResponse)
def status_page(request: Request, conn: Conn, token: str = ""):
    return templates.TemplateResponse(request, "status/status.html", _context(request, conn, token))


@router.get("/panel", response_class=HTMLResponse)
def status_panel(request: Request, conn: Conn, token: str = ""):
    """Polled every 10 seconds while the page is visible."""
    return templates.TemplateResponse(request, "status/_panel.html", _context(request, conn, token))

"""The printable /qr poster that sends patients to /status."""

import segno
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from markupsafe import Markup

from clinic_queue.web import templates

router = APIRouter()


def qr_svg(url: str) -> str:
    """QR code as inline SVG: sharp at any print size, no JavaScript needed."""
    # Error correction "m" survives ~15% damage (creases, smudges on a wall poster).
    return segno.make(url, error="m").svg_inline(scale=10, border=2, omitsize=True)


def status_url(request: Request) -> str:
    """The configured public address, not the Host header: a printed poster must be right."""
    base = request.app.state.settings.public_base_url or str(request.base_url)
    return base.rstrip("/") + "/status"


@router.get("/qr", response_class=HTMLResponse)
def poster(request: Request):
    url = status_url(request)
    context = {"url": url, "qr": Markup(qr_svg(url))}
    return templates.TemplateResponse(request, "qr.html", context)

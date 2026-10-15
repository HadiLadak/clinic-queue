from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from clinic_queue.i18n import LANG_COOKIE, SUPPORTED_LANGS

router = APIRouter()

ONE_YEAR = 365 * 24 * 3600


def safe_next(next_url: str) -> str:
    """Only allow redirects back into this site (no open redirect to other domains)."""
    if next_url.startswith("/") and not next_url.startswith(("//", "/\\")):
        return next_url
    return "/status"


@router.get("/lang/{lang}")
def set_language(lang: str, next: str = "/status"):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    response = RedirectResponse(safe_next(next), status_code=303)
    response.set_cookie(LANG_COOKIE, lang, max_age=ONE_YEAR, samesite="lax", httponly=True)
    return response

from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from clinic_queue.i18n import RTL_LANGS, other_lang, translate

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"


@pass_context
def _t(context, key: str, lang: str | None = None, **params: object) -> str:
    """Template helper: t("key", name=value) in the visitor's language (or an explicit one)."""
    return translate(key, lang or context["request"].state.lang, **params)


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals |= {"t": _t, "rtl_langs": RTL_LANGS, "other_lang": other_lang}

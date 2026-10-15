"""User-facing text. Every string shown to users comes from translations/<lang>.json."""

import json
from functools import cache
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).with_name("translations")
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "ur")
RTL_LANGS = frozenset({"ur"})
LANG_COOKIE = "lang"


@cache
def load(lang: str) -> dict[str, str]:
    return json.loads((TRANSLATIONS_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def translate(key: str, lang: str = DEFAULT_LANG, **params: object) -> str:
    """Look up `key` in `lang`, falling back to English. Missing keys raise KeyError."""
    text = load(lang).get(key) or load(DEFAULT_LANG)[key]
    return text.format(**params) if params else text


def pick_lang(cookie: str | None, accept_language: str) -> str:
    """The visitor's saved choice, else the phone's preferred supported language, else English."""
    if cookie in SUPPORTED_LANGS:
        return cookie
    # e.g. "ur-PK,ur;q=0.9,en-US;q=0.8": browsers list languages in preference order.
    for part in accept_language.lower().split(","):
        tag = part.split(";")[0].strip()
        for lang in SUPPORTED_LANGS:
            if tag == lang or tag.startswith(lang + "-"):
                return lang
    return DEFAULT_LANG


def other_lang(lang: str) -> str:
    return "ur" if lang == "en" else "en"

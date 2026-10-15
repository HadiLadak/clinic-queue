"""User-facing text. Every string shown to users comes from translations/<lang>.json."""

import json
from functools import cache
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).with_name("translations")
DEFAULT_LANG = "en"


@cache
def load(lang: str) -> dict[str, str]:
    return json.loads((TRANSLATIONS_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def translate(key: str, lang: str = DEFAULT_LANG, **params: object) -> str:
    """Look up `key` in `lang`, falling back to English. Missing keys raise KeyError."""
    text = load(lang).get(key) or load(DEFAULT_LANG)[key]
    return text.format(**params) if params else text

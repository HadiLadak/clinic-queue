import re

import pytest

from clinic_queue.i18n import load, translate
from clinic_queue.web import TEMPLATES_DIR

KEY_IN_TEMPLATE = re.compile(r"""\bt\(\s*["']([\w.]+)["']""")


def template_keys() -> set[str]:
    keys = set()
    for path in TEMPLATES_DIR.rglob("*.html"):
        keys |= set(KEY_IN_TEMPLATE.findall(path.read_text(encoding="utf-8")))
    return keys


def test_templates_use_translations():
    assert template_keys(), "expected templates to call t(...)"


def test_every_template_key_exists_in_english():
    missing = template_keys() - load("en").keys()
    assert not missing


def test_translate_fills_parameters():
    assert translate("desk.add.issued", number=7) == "Token #7"


def test_missing_key_raises():
    with pytest.raises(KeyError):
        translate("no.such.key")

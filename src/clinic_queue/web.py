from pathlib import Path

from fastapi.templating import Jinja2Templates

from clinic_queue.i18n import translate

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Templates call t("key", name=value) for every user-facing string.
templates.env.globals["t"] = translate

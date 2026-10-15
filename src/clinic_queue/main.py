from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from clinic_queue import desk, lang, poster, status
from clinic_queue.config import Settings
from clinic_queue.db import apply_schema, create_pool
from clinic_queue.i18n import LANG_COOKIE, pick_lang
from clinic_queue.security import LoginLimiter
from clinic_queue.web import STATIC_DIR

SESSION_MAX_AGE = 7 * 24 * 3600  # Desk phones stay logged in for a week.


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = None
        if settings.database_url:
            pool = create_pool(settings.database_url)
            pool.open(wait=True)
            with pool.connection() as conn:
                apply_schema(conn)
            app.state.pool = pool
        yield
        if pool:
            pool.close()

    app = FastAPI(title="Clinic Queue", lifespan=lifespan)
    app.state.settings = settings
    app.state.login_limiter = LoginLimiter()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="desk_session",
        max_age=SESSION_MAX_AGE,
        same_site="lax",
        https_only=settings.https_only,
    )

    @app.middleware("http")
    async def choose_language(request: Request, call_next):
        request.state.lang = pick_lang(
            request.cookies.get(LANG_COOKIE), request.headers.get("accept-language", "")
        )
        return await call_next(request)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(desk.router)
    app.include_router(status.router)
    app.include_router(lang.router)
    app.include_router(poster.router)

    @app.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/status")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness check: the process is up and serving requests."""
        return {"status": "ok"}

    return app


app = create_app()

# Decisions

Format: Context / Options / Decision / Why.

## M0-1: Tooling and project layout (2026-10-12)
**Context:** Need a reproducible Python setup on Windows that someone else (or a deploy server) can recreate exactly.
**Options:** pip + venv + requirements.txt; Poetry; uv.
**Decision:** uv with a `src/` layout (`src/clinic_queue`), Python 3.13, lockfile committed.
**Why:** uv is fast, manages the venv and the Python version, and `uv.lock` pins exact versions. The `src/` layout means tests import the installed package, not whatever happens to be in the working directory, which catches packaging mistakes early.

## M0-2: Postgres driver (2026-10-12)
**Context:** Supabase is used only as a Postgres host; all logic lives in FastAPI.
**Options:** supabase-py client; SQLAlchemy ORM; psycopg 3 with plain SQL.
**Decision:** psycopg 3 with plain SQL.
**Why:** Keeps us portable (any Postgres works), avoids coupling to Supabase's API, and the queue logic depends on transactions and locking, which are clearest to reason about in raw SQL. An ORM can be added later if it earns its place.

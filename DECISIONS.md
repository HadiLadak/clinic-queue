# Decisions

Format: Context / Options / Decision / Why.

## M0-1: Tooling and project layout (2026-10-12)
**Context:** Need a reproducible Python setup on Windows that someone else (or a deploy server) can recreate exactly.
**Options:** pip + venv + requirements.txt; Poetry; uv.
**Decision:** uv with a `src/` layout (`src/clinic_queue`), Python 3.13, lockfile committed.
**Why:** uv is fast, manages the venv and the Python version, and `uv.lock` pins exact versions. The `src/` layout means tests import the installed package, not whatever happens to be in the working directory, which catches packaging mistakes early.

## M0-3: Database hosting: two Supabase projects (2026-10-12)
**Context:** Need a dev database and a prod database, as close to Pakistan as possible, on a free plan.
**Options:** one project for everything; two projects (dev + prod); self-hosted Postgres.
**Decision:** Two free Supabase projects in ap-south-1 (Mumbai). Connect via the session pooler (IPv4, port 5432). Dev URL in `.env` (gitignored); prod URL in a file outside the repo.
**Why:** Separate projects mean dev mistakes can never touch real clinic data. Mumbai is the closest Supabase region. The direct DB address is IPv6-only, so the pooler is needed for IPv4 networks; session mode (not transaction mode) keeps normal transaction and locking behaviour.

## M0-4: How tests get a clean database (2026-10-14)
**Context:** Tests must never touch prod, must start from a known state, and Milestone 1 needs a test where several connections commit concurrently.
**Options:** (A) roll back a transaction per test; (B) a `test` schema in the dev DB, rebuilt per run and truncated per test; (C) a third Supabase project; (D) local Postgres via Docker or the installer; (E) wipe dev's `public` schema.
**Decision:** B, plus a guard that refuses to run if the URL contains the prod project ref.
**Why:** A can't support the concurrency test, since uncommitted data is invisible to other connections. C exceeds the free plan's 2 active projects. D needs a heavy install and can drift from Supabase's version. E destroys manual dev data. B is free, uses the same Postgres as prod, and keeps dev data intact. Cost: tests are slower (network round trips to Mumbai) and need internet; revisit D if that hurts.

## M0-2: Postgres driver (2026-10-12)
**Context:** Supabase is used only as a Postgres host; all logic lives in FastAPI.
**Options:** supabase-py client; SQLAlchemy ORM; psycopg 3 with plain SQL.
**Decision:** psycopg 3 with plain SQL.
**Why:** Keeps us portable (any Postgres works), avoids coupling to Supabase's API, and the queue logic depends on transactions and locking, which are clearest to reason about in raw SQL. An ORM can be added later if it earns its place.

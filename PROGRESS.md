# Progress

**Current milestone:** 1: Data model + queue logic

## Done
### Milestone 0: Setup ✅
- uv project (Python 3.13, src layout); FastAPI app with `/health` + test
- Dependencies: fastapi, uvicorn, psycopg[binary], python-dotenv; dev: pytest, httpx, ruff
- Docs: README, DECISIONS.md, NOTES.md, PROGRESS.md; `.gitignore` excludes `.env`; LF line endings
- Supabase: `clinic-queue-dev` and `clinic-queue-prod` in ap-south-1 (Mumbai), Postgres 17, via session pooler (IPv4, port 5432); dev URL in `.env`
- Test database: isolated `test` schema in dev DB, rebuilt per run, truncated per test; guard against prod (`tests/conftest.py`)

## Next
Milestone 1 design: tables and columns, preventing duplicate tokens on double tap, Postgres concurrency guarantees, what Undo reverses, token numbering at daily reset.

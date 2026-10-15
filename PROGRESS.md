# Progress

**Current milestone:** 1: Data model + queue logic

## Done
### Milestone 0: Setup ✅
- uv project (Python 3.13, src layout); FastAPI app with `/health` + test
- Dependencies: fastapi, uvicorn, psycopg[binary], python-dotenv; dev: pytest, httpx, ruff
- Docs: README, DECISIONS.md, NOTES.md, PROGRESS.md; `.gitignore` excludes `.env`; LF line endings
- Supabase: `clinic-queue-dev` and `clinic-queue-prod` in ap-south-1 (Mumbai), Postgres 17, via session pooler (IPv4, port 5432); dev URL in `.env`

### Milestone 1 (in progress)
- Design approved (DECISIONS M1-2): `sessions` + `tokens`, session-row lock, `request_id` idempotency, compare-and-set Next/Undo, 04:00 Asia/Karachi rollover
- Tests moved to local PostgreSQL 17 (DECISIONS M1-1); localhost-only guard; suite runs in ~8 s
- `schema.sql`, `db.py`, `queue_ops.py` (stubs), `tests/test_queue_ops.py` (31 tests incl. 3 concurrency tests)

## Next
- Implement `queue_ops.py` functions (TODO(human)): clinic_day_start → current_session_id → reset → issue_token → call_next → undo
- All tests green, ruff clean, commit + push; then Milestone 2 (/desk page)

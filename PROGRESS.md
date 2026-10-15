# Progress

**Current milestone:** 3: /status page (design)

## Done
### Milestone 0: Setup ✅
- uv project (Python 3.13, src layout); FastAPI app with `/health` + test
- Docs: README, DECISIONS.md, NOTES.md, PROGRESS.md; `.gitignore` excludes `.env`; LF line endings
- Supabase: `clinic-queue-dev` and `clinic-queue-prod` in ap-south-1 (Mumbai), Postgres 17, via session pooler (IPv4, port 5432); dev URL in `.env`

### Milestone 1: Data model + queue logic ✅
- `sessions` + `tokens` schema; session-row lock, `request_id` idempotency, compare-and-set Next/Undo, 04:00 Asia/Karachi rollover (DECISIONS M1-2)
- Tests on local PostgreSQL 17 with localhost-only guard (DECISIONS M1-1)

### Milestone 2: /desk page ✅
- PIN login (scrypt hash in env, 5-try lockout, signed 7-day cookie) (DECISIONS M2-1)
- Add patient → big token number; Next / Undo; waiting list; two-tap Reset; 10 s polling; "tap again" banner on network errors (DECISIONS M2-2)
- All text from `translations/en.json`; htmx 2.0.4 vendored in `static/`
- 71 tests passing, ruff clean; checked in a browser (login, add, Next)

## Next
Milestone 3: /status page: "Now serving", patient enters their token, people ahead + estimated wait, refresh every 10 s.

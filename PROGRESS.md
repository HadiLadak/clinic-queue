# Progress

**Current milestone:** 5: Deploy (on hold; design done, hosting not chosen)

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

### Milestone 3: /status page ✅
- Now serving; token lookup → people ahead, "You're next", "It's your turn", already called, not found, not started (DECISIONS M3-2)
- Wait = median of last 10 consults (default 8 min until 3 done), rounded (DECISIONS M3-1)
- Read-only (`waiting.py`), no names, polls every 10 s while visible, no-JS meta refresh
- 105 tests passing, ruff clean; checked in a browser

### Milestone 4: /qr poster and languages ✅
- English/Urdu on every page via `lang` cookie (default from phone language); Urdu right-to-left (DECISIONS M4-1)
- `/qr`: printable A4 poster in both languages, server-side SVG QR code from `PUBLIC_BASE_URL` (DECISIONS M4-2)
- `/` redirects to `/status`; desk links to the poster
- 131 tests passing, ruff clean; checked Urdu status page and poster in a browser

## Next
Milestone 5 (on hold): deploy with the prod database. Recommended: Fly.io in Mumbai (`bom`, ~$2–3/month, always on, next to the DB); free alternative is Render (sleeps after 15 min idle). Plan: Dockerfile, `fly.toml`, secrets, proxy headers, daily DB keep-alive and weekly encrypted backup via GitHub Actions, README screenshots.

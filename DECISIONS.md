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

## M4-1: Translations and right-to-left (2026-10-14)
**Context:** Every user-facing string must exist in English and Urdu; Urdu reads right to left; phones and internet are slow.
**Options:** gettext `.po` files vs one JSON file per language; language in the URL vs a cookie; Urdu web font vs system fonts.
**Decision:** JSON per language with a test that enforces identical keys and `{placeholders}`. Choice stored in a `lang` cookie set by `/lang/<code>` (default: the phone's `Accept-Language`, else English), redirecting back only to local paths. `<html dir="rtl">` plus logical CSS properties; token numbers wrapped in `<bdi>`, and Urdu strings avoid `#` before numbers. System fonts only.
**Why:** ~60 strings in two languages don't justify gettext's compile step and tooling. A cookie keeps URLs clean and is sent with HTMX polling too. Checking `next` prevents an open redirect. Logical properties let one stylesheet serve both directions. An Urdu Nastaliq web font is ~1 MB, too heavy on slow connections. Urdu wording should be reviewed by a native speaker before the pilot.

## M4-2: QR code generated on the server (2026-10-14)
**Context:** The clinic prints a poster whose QR code opens /status.
**Options:** JavaScript QR library in the browser; server-side library producing PNG; server-side SVG.
**Decision:** `segno` (pure Python, no dependencies) renders an inline SVG with medium error correction. The URL comes from `PUBLIC_BASE_URL`, falling back to the request address in dev. The poster shows both languages and has print CSS for A4.
**Why:** SVG stays sharp at any print size and needs no JavaScript. Using configuration instead of the Host header guarantees the printed code points at the real site. Medium error correction tolerates creases and smudges on a wall poster.

## M3-1: Wait estimate (2026-10-14)
**Context:** Patients want "how long until I'm seen?" Consult lengths vary, and the doctor may take breaks.
**Options:** fixed minutes per patient; mean of today's consults; median of recent consults; a model by time of day.
**Decision:** Median of the last 10 finished consults today; fall back to `DEFAULT_CONSULT_MINUTES` (8) until there are 3. Wait = people ahead × typical + what's left of the current consult. Shown rounded ("a few minutes", "about 25 min", "about 1 h 15 min"), flagged as rough while using the default.
**Why:** The median ignores one-off long consults or breaks that would skew a mean; "last 10" follows the doctor's current pace. Rounding avoids promising precision we don't have. A per-hour model needs weeks of data we don't have yet.

## M3-2: Public status page (2026-10-14)
**Context:** Anyone with the QR link can open /status and type any token number.
**Options:** show names for reassurance vs numbers only; share desk logic vs a separate read-only path; polling vs push.
**Decision:** Numbers only, never names. A separate read-only module (`waiting.py`) that never starts a session. HTMX polling every 10 s, paused while the tab is hidden; `<meta refresh>` 30 s without JavaScript; "Updated HH:MM" shown.
**Why:** Names on a public page would leak who is at the clinic. Read-only means the public page can't change the queue. Polling is ~10 req/s for 100 phones with ~1 KB responses, which is fine at one clinic; at many clinics, add a short in-memory cache, then Server-Sent Events. The timestamp lets patients notice stale data when their connection drops.

## M2-1: Desk PIN and sessions (2026-10-14)
**Context:** One shared 4-digit PIN protects the desk. Receptionists shouldn't re-enter it all day.
**Options:** PIN in a DB table vs environment; plain vs hashed; per-request PIN vs session cookie; with or without rate limiting.
**Decision:** scrypt hash in `DESK_PIN_HASH` (env), constant-time compare, in-memory limiter (5 failures → 5-minute lockout per client IP), signed 7-day session cookie (HttpOnly, SameSite=Lax, HTTPS-only in prod).
**Why:** One clinic means no table is needed. With 10,000 possible PINs a hash alone is weak, so the limiter is the real defence (a full search takes about a week). SameSite=Lax blocks cross-site form posts (CSRF). Trade-off: the in-memory limiter resets on restart and only works with one server process; behind a proxy it must see the real client IP (M5).

## M2-2: Desk UI updates and resilience (2026-10-14)
**Context:** Slow, flaky internet; possibly two phones on one desk; text typed into the name field must not be wiped.
**Options:** full-page reloads; HTMX swapping the whole desk; HTMX with targeted out-of-band (OOB) swaps; WebSockets.
**Decision:** HTMX (vendored, no CDN). Actions return the serving and waiting panels as OOB swaps; the add form is swapped on its own; a hidden poller refreshes the panels every 10 s. Buttons are disabled while in flight, and a banner says "tap again" on network/server errors. Reset uses a native `<details>` confirm (two taps, no JS dialog).
**Why:** OOB swaps update everything an action changed without touching the half-typed name. Retries are safe because Add carries a `request_id` and Next/Undo carry the expected number (M1). Polling is simple and good enough for a few phones; WebSockets would add complexity with little gain at this scale. A pool of connections avoids reconnecting (~seconds) per request.

## M1-1: Tests move to a local Postgres (2026-10-14), revises M0-4
**Context:** The developer is in North America and the dev database is in Mumbai: ~1.7 s to connect, ~250 ms per query. The queue tests took over 5 minutes.
**Options:** keep testing against Supabase; batch queries to cut round trips; local Postgres 17.
**Decision:** Local PostgreSQL 17 via the official installer, still with an isolated `test` schema. `conftest.py` refuses any non-localhost URL.
**Why:** Sub-millisecond queries make the suite run in seconds and work offline. Same major version as Supabase keeps behaviour aligned. The localhost guard is stricter than the old prod-ref check: tests can't reach any Supabase database. Batching would make test code less readable and still be slow.

## M1-2: Queue data model and concurrency (2026-10-14)
**Context:** Tokens must never duplicate, even on a fast double tap or two phones at once; Undo and a daily reset are needed.
**Options:** `MAX(number)+1` per insert; a Postgres sequence per day; a counter column on a per-day `sessions` row.
**Decision:** `sessions` (one open at a time, `last_number` counter) + `tokens` (status, timestamps, unique `request_id`). Every write locks the session row first. Next/Undo carry the number the screen showed (compare-and-set). Undo reverses the last Next only. Sessions roll over at 04:00 Asia/Karachi or on manual Reset.
**Why:** The row lock serialises writers so numbers are consecutive with no gaps, unlike `MAX+1` (races) or sequences (gaps on rollback). `request_id` makes "Add patient" idempotent; compare-and-set makes Next/Undo safe against stale screens. Unique constraints are the last line of defence. 04:00 local keeps evening shifts that run past midnight in one session.

## M0-2: Postgres driver (2026-10-12)
**Context:** Supabase is used only as a Postgres host; all logic lives in FastAPI.
**Options:** supabase-py client; SQLAlchemy ORM; psycopg 3 with plain SQL.
**Decision:** psycopg 3 with plain SQL.
**Why:** Keeps us portable (any Postgres works), avoids coupling to Supabase's API, and the queue logic depends on transactions and locking, which are clearest to reason about in raw SQL. An ORM can be added later if it earns its place.

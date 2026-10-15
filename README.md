# Clinic Queue

A queue app for walk-in clinics in Pakistan. The receptionist adds patients and calls the next one; patients scan a QR code to see how many people are ahead of them and roughly how long they'll wait.

**Status:** v0 in progress, see [PROGRESS.md](PROGRESS.md).

## Stack
Python 3.13 · FastAPI · Jinja2 + HTMX (server-rendered, no build step) · PostgreSQL on Supabase · pytest · ruff · uv

## Setup
Requires [uv](https://docs.astral.sh/uv/).

```powershell
uv sync                       # create .venv and install exact locked versions
Copy-Item .env.example .env   # then fill in DATABASE_URL
```

## Run
```powershell
uv run uvicorn clinic_queue.main:app --reload
```
Open http://127.0.0.1:8000/health

## Test and lint
Database tests need a **local PostgreSQL 17** (e.g. `winget install PostgreSQL.PostgreSQL.17`) and `TEST_DATABASE_URL` in `.env` pointing at localhost. They run in an isolated `test` schema rebuilt every run, and refuse to run against any non-local host, so they can never touch Supabase. Without `TEST_DATABASE_URL` they are skipped.

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
```

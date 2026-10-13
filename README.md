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
```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
```

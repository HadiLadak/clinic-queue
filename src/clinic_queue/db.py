import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def database_url() -> str:
    load_dotenv()
    return os.environ["DATABASE_URL"]


def apply_schema(conn: psycopg.Connection) -> None:
    """Create tables and indexes if they don't exist yet."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

from collections.abc import Iterator
from pathlib import Path

import psycopg
from fastapi import Request
from psycopg_pool import ConnectionPool

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def apply_schema(conn: psycopg.Connection) -> None:
    """Create tables and indexes if they don't exist yet."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def create_pool(database_url: str) -> ConnectionPool:
    """A small pool of reusable connections; opening one from scratch takes seconds."""
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True},
        open=False,
    )


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    """FastAPI dependency: borrow a pooled connection for the length of one request."""
    with request.app.state.pool.connection() as conn:
        yield conn

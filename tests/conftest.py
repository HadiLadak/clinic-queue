"""Shared test fixtures.

Database tests run against a local Postgres (TEST_DATABASE_URL), isolated in a
`test` schema that is rebuilt once per run; its tables are emptied before every
test. Tests refuse to run against any non-local host, so they can never reach
the Supabase dev or prod databases.
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from clinic_queue.config import Settings
from clinic_queue.db import apply_schema, get_conn
from clinic_queue.main import create_app

TEST_SCHEMA = "test"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@pytest.fixture(scope="session")
def database_url() -> str:
    load_dotenv()
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set (see README: local Postgres for tests)")
    if conninfo_to_dict(url).get("host") not in LOCAL_HOSTS:
        raise RuntimeError("Refusing to run tests against a non-local database.")

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(TEST_SCHEMA))
        )
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(TEST_SCHEMA)))
    with psycopg.connect(url, autocommit=True, options=f"-c search_path={TEST_SCHEMA}") as conn:
        apply_schema(conn)
    return url


@pytest.fixture
def connect(database_url):
    """Factory that opens connections pinned to the test schema.

    Call it several times to get independent connections (e.g. for concurrency tests).
    Every table in the test schema is emptied before the test starts.
    """
    opened: list[psycopg.Connection] = []

    def _connect(**kwargs) -> psycopg.Connection:
        conn = psycopg.connect(database_url, options=f"-c search_path={TEST_SCHEMA}", **kwargs)
        opened.append(conn)
        return conn

    with _connect(autocommit=True) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = %s", (TEST_SCHEMA,)
            )
        ]
        if tables:
            conn.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(TEST_SCHEMA, t) for t in tables)
                )
            )

    yield _connect

    for conn in opened:
        conn.close()


@pytest.fixture
def make_client(connect):
    """Build a TestClient for an app whose routes use the isolated test database."""

    def _make(settings: Settings) -> TestClient:
        app = create_app(settings)

        def test_conn():
            with connect(autocommit=True) as conn:
                yield conn

        app.dependency_overrides[get_conn] = test_conn
        return TestClient(app)

    return _make

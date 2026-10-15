"""Shared test fixtures.

Database tests run against the dev Supabase database, isolated in their own
`test` schema: the schema is rebuilt once per test run and its tables are
emptied before every test. Your dev data in `public` is never touched.
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import sql

TEST_SCHEMA = "test"

# The prod project's ref (not a secret). Tests refuse to run if they ever see it.
PROD_PROJECT_REF = "hnpbatszdpkknwkgablw"


@pytest.fixture(scope="session")
def database_url() -> str:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set (copy .env.example to .env)")
    if PROD_PROJECT_REF in url:
        raise RuntimeError("Refusing to run tests against the PROD database.")

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(TEST_SCHEMA))
        )
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(TEST_SCHEMA)))
        # Milestone 1: create the app's tables here.
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

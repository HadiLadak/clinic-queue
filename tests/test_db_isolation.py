"""Proves the test database setup is isolated before any real logic depends on it."""


def test_connections_use_test_schema(connect):
    with connect() as conn:
        assert conn.execute("SELECT current_schema()").fetchone()[0] == "test"


def test_unqualified_tables_are_created_in_test_schema_not_public(connect):
    with connect(autocommit=True) as conn:
        conn.execute("CREATE TABLE isolation_probe (id int)")
        test_table, public_table = conn.execute(
            "SELECT to_regclass('test.isolation_probe'), to_regclass('public.isolation_probe')"
        ).fetchone()
        conn.execute("DROP TABLE isolation_probe")

    assert test_table is not None
    assert public_table is None

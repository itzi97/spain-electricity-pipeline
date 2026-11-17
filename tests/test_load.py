"""Loader tests against a real PostgreSQL, in a throwaway database.

Skipped when no server is reachable with the libpq environment variables.
"""

import os
import uuid
from datetime import date

import psycopg
import pytest

from ingest import load
from ingest.ree import GenerationRow


def _row(day: int, mwh: float, share: float = 0.3) -> GenerationRow:
    return GenerationRow("10291", "Wind", "Renovable", date(2026, 3, day), mwh, share, None)


@pytest.fixture
def scratch_db(monkeypatch):
    name = f"loader_test_{uuid.uuid4().hex[:8]}"
    try:
        admin = psycopg.connect(autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("no PostgreSQL reachable")
    admin.execute(f'create database "{name}"')
    monkeypatch.setenv("PGDATABASE", name)
    try:
        yield name
    finally:
        admin.execute(f'drop database "{name}" with (force)')
        admin.close()


def test_rerun_counts_inserts_revisions_and_unchanged_rows(scratch_db, monkeypatch):
    batches = iter([
        [_row(28, 100.0), _row(29, 200.0)],
        [_row(28, 100.0), _row(29, 250.0), _row(30, 300.0)],  # 29th revised by REE, 30th new
    ])
    monkeypatch.setattr(load, "fetch", lambda start, end: next(batches))

    first = load.run(date(2026, 3, 28), date(2026, 3, 29))
    second = load.run(date(2026, 3, 28), date(2026, 3, 30))

    assert first == {"received": 2, "inserted": 2, "updated": 0, "unchanged": 0}
    assert second == {"received": 3, "inserted": 1, "updated": 1, "unchanged": 1}

    with psycopg.connect() as conn:
        rows = conn.execute(
            "select day, mwh, updated_at > first_loaded_at from raw.ree_generation_daily order by day"
        ).fetchall()
        runs = conn.execute("select count(*) from raw.load_runs where finished_at is not null").fetchone()[0]
    assert [(r[0].day, float(r[1]), r[2]) for r in rows] == [(28, 100.0, False), (29, 250.0, True), (30, 300.0, False)]
    assert runs == 2

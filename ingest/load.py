"""Load REE daily generation into PostgreSQL.

    python -m ingest.load --start 2023-01-01            # backfill to yesterday
    python -m ingest.load --days 14                     # refresh the last two weeks

Connection settings come from the usual libpq variables
(PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE).
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import psycopg

from ingest.ree import GenerationRow, fetch

log = logging.getLogger("ingest")

SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text()

# Insert new rows; update existing ones only when a value actually changed.
# xmax = 0 is true for a freshly inserted row, false for an updated one.
UPSERT_SQL = """
insert into raw.ree_generation_daily
    (technology_id, technology, renewable_class, day, mwh, share, api_last_update)
values (%s, %s, %s, %s, %s, %s, %s)
on conflict (technology_id, day) do update set
    technology      = excluded.technology,
    renewable_class = excluded.renewable_class,
    mwh             = excluded.mwh,
    share           = excluded.share,
    api_last_update = excluded.api_last_update,
    updated_at      = now()
where (raw.ree_generation_daily.mwh, raw.ree_generation_daily.share)
      is distinct from (excluded.mwh, excluded.share)
returning (xmax = 0) as inserted
"""


def upsert(conn: psycopg.Connection, rows: list[GenerationRow]) -> tuple[int, int]:
    inserted = updated = 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                UPSERT_SQL,
                (r.technology_id, r.technology, r.renewable_class, r.day, r.mwh, r.share, r.api_last_update),
            )
            result = cur.fetchone()
            if result is None:
                continue  # unchanged: the WHERE clause skipped the update
            if result[0]:
                inserted += 1
            else:
                updated += 1
    return inserted, updated


def run(start: date, end: date) -> dict:
    with psycopg.connect() as conn:
        conn.execute(SCHEMA_SQL)
        run_id = conn.execute(
            "insert into raw.load_runs (start_day, end_day) values (%s, %s) returning run_id",
            (start, end),
        ).fetchone()[0]

        rows = fetch(start, end)
        inserted, updated = upsert(conn, rows)
        stats = {
            "received": len(rows),
            "inserted": inserted,
            "updated": updated,
            "unchanged": len(rows) - inserted - updated,
        }
        conn.execute(
            """update raw.load_runs
               set finished_at = now(), rows_received = %s, rows_inserted = %s,
                   rows_updated = %s, rows_unchanged = %s
               where run_id = %s""",
            (stats["received"], stats["inserted"], stats["updated"], stats["unchanged"], run_id),
        )
    log.info("run %s, %s to %s: %s", run_id, start, end, stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    window = parser.add_mutually_exclusive_group(required=True)
    window.add_argument("--start", type=date.fromisoformat, help="first day to load (YYYY-MM-DD)")
    window.add_argument("--days", type=int, help="load this many days back from yesterday")
    parser.add_argument("--end", type=date.fromisoformat, help="last day to load (default: yesterday)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    end = args.end or date.today() - timedelta(days=1)
    start = args.start or end - timedelta(days=args.days - 1)
    run(start, end)


if __name__ == "__main__":
    main()

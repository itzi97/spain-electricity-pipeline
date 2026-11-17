"""Export the marts to static JSON for the dashboard in site/.

    python -m export.export_json --out site/data

Reads the same libpq variables as the loader. If dbt's run_results.json is
present, the test summary is included so the page can show that the data it
draws passed its checks.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

RUN_RESULTS = Path(__file__).resolve().parent.parent / "dbt" / "target" / "run_results.json"


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def query(conn: psycopg.Connection, sql: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        return [{k: _plain(v) for k, v in row.items()} for row in cur.fetchall()]


def test_summary(path: Path = RUN_RESULTS) -> dict | None:
    if not path.exists():
        return None
    results = json.loads(path.read_text())["results"]
    tests = [r for r in results if r["unique_id"].startswith("test.")]
    return dict(Counter(r["status"] for r in tests))


def export(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect() as conn:
        daily = query(
            conn,
            """select generation_day as day,
                      round(total_mwh / 1000, 1)          as total_gwh,
                      renewable_share                     as share,
                      renewable_share_7d                  as share_7d,
                      round(wind_mwh / 1000, 1)           as wind_gwh,
                      round(solar_mwh / 1000, 1)          as solar_gwh,
                      round(hydro_mwh / 1000, 1)          as hydro_gwh,
                      round(nuclear_mwh / 1000, 1)        as nuclear_gwh,
                      round(combined_cycle_mwh / 1000, 1) as combined_cycle_gwh,
                      top_technology                      as top
               from marts.mart_daily_mix
               order by generation_day""",
        )
        monthly = query(
            conn,
            """select month, technology_group as tech_group, is_renewable,
                      days_with_data as days,
                      round(net_generation_mwh / 1000, 1) as gwh,
                      share_of_month as share
               from marts.mart_monthly_mix
               order by month, technology_group""",
        )
        last_run = query(
            conn,
            """select finished_at, start_day, end_day, rows_received, rows_inserted,
                      rows_updated, rows_unchanged
               from raw.load_runs
               where finished_at is not null
               order by run_id desc
               limit 1""",
        )

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "first_day": daily[0]["day"] if daily else None,
        "last_day": daily[-1]["day"] if daily else None,
        "days": len(daily),
        "last_load": last_run[0] if last_run else None,
        "dbt_tests": test_summary(),
        "source": "Red Eléctrica, REData API (apidatos.ree.es)",
    }
    (out / "daily.json").write_text(json.dumps(daily, separators=(",", ":")))
    (out / "monthly.json").write_text(json.dumps(monthly, separators=(",", ":")))
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"wrote {len(daily)} days and {len(monthly)} month-group rows to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("site/data"))
    export(parser.parse_args().out)


if __name__ == "__main__":
    main()

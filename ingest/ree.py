"""Client for Red Eléctrica's REData API: daily generation by technology.

Endpoint docs: https://www.ree.es/en/apidatos
The API returns at most one year of daily values per request, and a full
uncached year can take over a minute to come back, so ranges are split into
calendar quarters: more requests, each well inside the timeout.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import requests

BASE_URL = "https://apidatos.ree.es/en/datos/generacion/estructura-generacion"
TIMEOUT_S = 120
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class GenerationRow:
    technology_id: str
    technology: str
    renewable_class: str  # 'Renovable', 'No-Renovable' or 'total', as REE labels it
    day: date
    mwh: float
    share: float
    api_last_update: datetime | None


def quarter_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] into ranges that never cross a calendar quarter."""
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    chunks = []
    cursor = start
    while cursor <= end:
        first_month_next = 3 * ((cursor.month - 1) // 3) + 4
        if first_month_next > 12:
            next_start = date(cursor.year + 1, 1, 1)
        else:
            next_start = date(cursor.year, first_month_next, 1)
        chunk_end = min(next_start - timedelta(days=1), end)
        chunks.append((cursor, chunk_end))
        cursor = next_start
    return chunks


def parse(payload: dict) -> list[GenerationRow]:
    """Flatten one API response into one row per technology per day.

    The day is taken from the local (Spanish) timestamp as written by REE,
    not converted to UTC: '2026-03-29T00:00:00.000+01:00' is 29 March.
    """
    if "errors" in payload:
        raise ValueError(f"API returned errors: {payload['errors']}")
    rows = []
    for item in payload.get("included", []):
        attrs = item["attributes"]
        last_update = attrs.get("last-update")
        for value in attrs.get("values", []):
            rows.append(
                GenerationRow(
                    technology_id=str(item["id"]),
                    technology=item["type"],
                    renewable_class=attrs["type"],
                    day=date.fromisoformat(value["datetime"][:10]),
                    mwh=float(value["value"]),
                    share=float(value["percentage"]),
                    api_last_update=datetime.fromisoformat(last_update) if last_update else None,
                )
            )
    return rows


def fetch(start: date, end: date, session: requests.Session | None = None) -> list[GenerationRow]:
    """Fetch daily generation for [start, end], retrying transient failures.

    REE answers temporary unavailability with HTTP 400 and an error body,
    so 400s are retried along with 429, 5xx, timeouts and dropped connections.
    """
    session = session or requests.Session()
    rows: list[GenerationRow] = []
    for chunk_start, chunk_end in quarter_chunks(start, end):
        params = {
            "start_date": f"{chunk_start.isoformat()}T00:00",
            "end_date": f"{chunk_end.isoformat()}T23:59",
            "time_trunc": "day",
        }
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = session.get(BASE_URL, params=params, timeout=TIMEOUT_S)
            except (requests.Timeout, requests.ConnectionError):
                if attempt == MAX_ATTEMPTS:
                    raise
                time.sleep(2**attempt)
                continue
            if response.status_code == 200:
                # The API can return the day after end_date (its end bound is read
                # in a different time zone), and that day is still incomplete.
                rows.extend(r for r in parse(response.json()) if chunk_start <= r.day <= chunk_end)
                break
            if response.status_code in (400, 429) or response.status_code >= 500:
                if attempt == MAX_ATTEMPTS:
                    response.raise_for_status()
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
    return rows

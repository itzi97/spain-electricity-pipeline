import json
from datetime import date
from pathlib import Path

import pytest
import requests

from ingest import ree

FIXTURE = Path(__file__).parent / "fixtures" / "estructura_generacion_2026-03-28_30.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_quarter_chunks_split_on_calendar_quarters():
    assert ree.quarter_chunks(date(2024, 11, 15), date(2025, 7, 3)) == [
        (date(2024, 11, 15), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 3, 31)),
        (date(2025, 4, 1), date(2025, 6, 30)),
        (date(2025, 7, 1), date(2025, 7, 3)),
    ]


def test_quarter_chunks_cover_every_day_once():
    chunks = ree.quarter_chunks(date(2023, 1, 1), date(2026, 11, 16))
    days = sum((b - a).days + 1 for a, b in chunks)
    assert days == (date(2026, 11, 16) - date(2023, 1, 1)).days + 1
    assert all(b.year == a.year for a, b in chunks)


def test_quarter_chunks_single_day():
    assert ree.quarter_chunks(date(2026, 5, 4), date(2026, 5, 4)) == [(date(2026, 5, 4), date(2026, 5, 4))]


def test_quarter_chunks_reject_reversed_range():
    with pytest.raises(ValueError):
        ree.quarter_chunks(date(2026, 5, 4), date(2026, 5, 3))


def test_parse_keeps_the_local_day_across_the_clock_change():
    # 29 March 2026 is the spring clock change in Spain: the offset moves from +01:00 to +02:00.
    rows = ree.parse(load_fixture())
    wind_days = [r.day for r in rows if r.technology == "Wind"]
    assert wind_days == [date(2026, 3, 28), date(2026, 3, 29), date(2026, 3, 30)]


def test_parse_reads_ids_classes_and_values():
    rows = ree.parse(load_fixture())
    wind = next(r for r in rows if r.technology == "Wind" and r.day == date(2026, 3, 28))
    assert wind.technology_id == "10291"
    assert wind.renewable_class == "Renovable"
    assert wind.mwh == pytest.approx(256231.81)
    assert 0 < wind.share < 1
    total = next(r for r in rows if r.technology == "Total generation" and r.day == date(2026, 3, 28))
    assert total.renewable_class == "total"
    assert total.share == 1


def test_parse_raises_on_an_error_payload():
    with pytest.raises(ValueError, match="unavailable"):
        ree.parse({"errors": [{"status": "400", "detail": "The requested data is currently unavailable."}]})


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Returns the queued responses in order and records the params sent."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_fetch_drops_days_outside_the_requested_range(monkeypatch):
    # The fixture covers 28-30 March but Coal also carries 31 March, as the live API does.
    session = FakeSession([FakeResponse(200, load_fixture())])
    rows = ree.fetch(date(2026, 3, 28), date(2026, 3, 30), session=session)
    assert max(r.day for r in rows) == date(2026, 3, 30)
    assert session.calls[0]["start_date"] == "2026-03-28T00:00"
    assert session.calls[0]["end_date"] == "2026-03-30T23:59"


def test_fetch_retries_the_apis_temporary_400(monkeypatch):
    monkeypatch.setattr(ree.time, "sleep", lambda s: None)
    session = FakeSession([
        FakeResponse(400, {"errors": [{"detail": "currently unavailable"}]}),
        FakeResponse(200, load_fixture()),
    ])
    rows = ree.fetch(date(2026, 3, 28), date(2026, 3, 30), session=session)
    assert len(session.calls) == 2
    assert rows


def test_fetch_retries_a_read_timeout(monkeypatch):
    monkeypatch.setattr(ree.time, "sleep", lambda s: None)
    session = FakeSession([requests.ReadTimeout("slow"), FakeResponse(200, load_fixture())])
    rows = ree.fetch(date(2026, 3, 28), date(2026, 3, 30), session=session)
    assert len(session.calls) == 2
    assert rows


def test_fetch_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(ree.time, "sleep", lambda s: None)
    session = FakeSession([FakeResponse(503, {}) for _ in range(ree.MAX_ATTEMPTS)])
    with pytest.raises(requests.HTTPError):
        ree.fetch(date(2026, 3, 28), date(2026, 3, 30), session=session)
    assert len(session.calls) == ree.MAX_ATTEMPTS

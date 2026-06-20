"""Live data agent tests: parsing + upsert persistence against an in-memory SQLite DB."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import create_engine

from app.agents.live_data import (
    LiveDataAgent,
    parse_fixture,
    parse_standings,
)
from app.db.database import init_db, make_session_factory
from app.db.models import Match
from tests.conftest import make_client


@pytest.fixture
def session_factory():
    # File-less SQLite that persists across connections within the test.
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    return make_session_factory(engine)


def test_parse_fixture_maps_fields(fixtures_payload):
    match = parse_fixture(fixtures_payload["response"][0])
    assert match.fixture_id == 101
    assert match.home_team == "Brazil"
    assert match.away_team_id == 20
    assert match.status == "FT"
    assert match.home_goals == 2
    assert match.round == "Group A - 2"
    assert match.updated_at is not None


def test_parse_standings_flattens_groups(standings_payload):
    rows = parse_standings(standings_payload["response"])
    assert len(rows) == 2
    top = rows[0]
    assert top["team"] == "Brazil"
    assert top["group"] == "Group A"
    assert top["points"] == 6


def test_refresh_persists_and_filters(fixtures_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=fixtures_payload))
    agent = LiveDataAgent(client, session_factory)

    # Only follow Brazil (team 10) → fixture 102 (Cameroon/Switzerland) is filtered out.
    saved = agent.refresh_fixtures_by_date("2026-06-21", followed_team_ids=[10])
    assert [m.fixture_id for m in saved] == [101]

    with session_factory() as s:
        rows = s.query(Match).all()
        assert {r.fixture_id for r in rows} == {101}


def test_refresh_is_upsert(fixtures_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=fixtures_payload))
    agent = LiveDataAgent(client, session_factory)

    agent.refresh_fixtures_by_date("2026-06-21")
    # Simulate a later poll where fixture 101 has progressed.
    updated = {"response": [dict(fixtures_payload["response"][0])], "errors": []}
    updated["response"][0] = {
        **fixtures_payload["response"][0],
        "goals": {"home": 3, "away": 0},
        "fixture": {"id": 101, "date": "2026-06-21T18:00:00+00:00", "status": {"short": "FT"}},
    }
    client2 = make_client(lambda r: httpx.Response(200, json=updated))
    LiveDataAgent(client2, session_factory).refresh_fixtures_by_ids([101])

    with session_factory() as s:
        row = s.get(Match, 101)
        assert row.home_goals == 3  # updated in place, not duplicated
        assert s.query(Match).count() == 2  # 101 + 102 from the first call


def test_fetch_standings(standings_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=standings_payload))
    agent = LiveDataAgent(client, session_factory)
    rows = agent.fetch_standings()
    assert len(rows) == 2
    assert rows[0]["team"] == "Brazil"

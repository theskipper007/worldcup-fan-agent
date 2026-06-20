"""Shared test fixtures and sample API-Football payloads (trimmed to the fields we parse)."""

from __future__ import annotations

import httpx
import pytest

from app.apifootball.client import ApiFootballClient
from app.config import Settings
from app.rate_limiter import TokenBucket


def make_client(
    handler, *, sleep=lambda _s: None, budget=None, cache_ttl=0.0, monotonic=None
) -> ApiFootballClient:
    """Build an ApiFootballClient backed by an httpx MockTransport ``handler``.

    Caching is OFF by default (cache_ttl=0) so each call hits the handler; pass a cache_ttl
    (and optionally a monotonic clock) to exercise the 30-minute throttle.
    """
    import time as _time

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="https://test.local")
    return ApiFootballClient(
        settings=Settings(wc_league_id=1, wc_season=2026),
        budget=budget or TokenBucket(capacity=50, refill_rate=50, per=60.0),
        http_client=http,
        sleep=sleep,
        monotonic=monotonic or _time.monotonic,
        cache_ttl=cache_ttl,
        backoff_base=0.0,
    )


@pytest.fixture
def fixtures_payload() -> dict:
    return {
        "errors": [],
        "results": 2,
        "response": [
            {
                "fixture": {"id": 101, "date": "2026-06-21T18:00:00+00:00",
                            "status": {"short": "FT"}},
                "league": {"id": 1, "season": 2026, "round": "Group A - 2"},
                "teams": {"home": {"id": 10, "name": "Brazil"},
                          "away": {"id": 20, "name": "Serbia"}},
                "goals": {"home": 2, "away": 0},
            },
            {
                "fixture": {"id": 102, "date": "2026-06-21T21:00:00+00:00",
                            "status": {"short": "NS"}},
                "league": {"id": 1, "season": 2026, "round": "Group A - 2"},
                "teams": {"home": {"id": 30, "name": "Cameroon"},
                          "away": {"id": 40, "name": "Switzerland"}},
                "goals": {"home": None, "away": None},
            },
        ],
    }


@pytest.fixture
def predictions_payload() -> dict:
    return {
        "errors": [],
        "response": [
            {
                "predictions": {
                    "winner": {"id": 10, "name": "Brazil"},
                    "win_or_draw": False,
                    "advice": "Combo Double chance : Brazil or draw",
                    "percent": {"home": "55%", "draw": "25%", "away": "20%"},
                },
                "teams": {"home": {"id": 10, "name": "Brazil"},
                          "away": {"id": 20, "name": "Serbia"}},
            }
        ],
    }


@pytest.fixture
def standings_payload() -> dict:
    return {
        "errors": [],
        "response": [
            {"league": {"id": 1, "season": 2026, "standings": [
                [
                    {"rank": 1, "team": {"id": 10, "name": "Brazil"}, "points": 6,
                     "goalsDiff": 4, "group": "Group A", "form": "WW"},
                    {"rank": 2, "team": {"id": 20, "name": "Serbia"}, "points": 3,
                     "goalsDiff": -1, "group": "Group A", "form": "LW"},
                ],
            ]}},
        ],
    }

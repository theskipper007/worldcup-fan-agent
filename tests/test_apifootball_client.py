"""Client tests via httpx MockTransport — no network, no real key. See docs/api-football.md."""

from __future__ import annotations

import httpx
import pytest

from app.apifootball.client import ApiFootballClient, ApiFootballError
from app.config import Settings
from tests.conftest import make_client


def test_injects_league_and_season_params(fixtures_payload):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=fixtures_payload)

    client = make_client(handler)
    client.get_fixtures_by_date("2026-06-21")
    assert seen["params"]["league"] == "1"
    assert seen["params"]["season"] == "2026"
    assert seen["params"]["date"] == "2026-06-21"


def test_batch_ids_joined_with_dashes(fixtures_payload):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ids"] = request.url.params.get("ids")
        return httpx.Response(200, json=fixtures_payload)

    client = make_client(handler)
    client.get_fixtures_by_ids([101, 102, 103])
    assert seen["ids"] == "101-102-103"


def test_rejects_more_than_20_ids():
    client = make_client(lambda r: httpx.Response(200, json={"response": []}))
    with pytest.raises(ValueError):
        client.get_fixtures_by_ids(list(range(21)))


def test_reads_rate_limit_headers(fixtures_payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=fixtures_payload,
            headers={
                "x-ratelimit-requests-limit": "100",
                "x-ratelimit-requests-remaining": "57",
                "X-RateLimit-Limit": "10",
                "X-RateLimit-Remaining": "1",
            },
        )

    client = make_client(handler)
    client.get_fixtures_by_date("2026-06-21")
    rl = client.last_rate_limit
    assert rl.daily_remaining == 57
    assert rl.minute_remaining == 1
    assert rl.minute_low is True


def test_retries_429_then_succeeds(fixtures_payload):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"response": []})
        return httpx.Response(200, json=fixtures_payload)

    client = make_client(handler)  # sleep is a no-op in make_client
    result = client.get_fixtures_by_date("2026-06-21")
    assert calls["n"] == 3
    assert len(result) == 2


def test_429_gives_up_after_max_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"response": []})

    client = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_fixtures_by_date("2026-06-21")


def test_raises_on_api_errors_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": {"token": "invalid key"}, "response": []})

    client = make_client(handler)
    with pytest.raises(ApiFootballError):
        client.get_standings()


def test_missing_key_raises_when_building_real_client():
    with pytest.raises(ValueError):
        ApiFootballClient(settings=Settings(api_football_key=""))


def test_cache_throttles_identical_calls_within_ttl(fixtures_payload):
    """Free tier is 100 req/day: identical calls hit the network at most once per TTL."""
    calls = {"n": 0}
    clock = {"t": 1000.0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=fixtures_payload)

    client = make_client(handler, cache_ttl=1800.0, monotonic=lambda: clock["t"])

    client.get_fixtures_by_date("2026-06-21")
    client.get_fixtures_by_date("2026-06-21")  # within 30 min → served from cache
    assert calls["n"] == 1

    clock["t"] += 1801  # past the 30-minute window
    client.get_fixtures_by_date("2026-06-21")
    assert calls["n"] == 2

    # Different params are cached independently.
    client.get_fixtures_by_date("2026-06-22")
    assert calls["n"] == 3

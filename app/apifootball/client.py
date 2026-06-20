"""API-Football HTTP client.

See ../../docs/api-football.md. Every request goes through the shared rate limiter, always carries
``league=1&season=2026``, reads the ``x-ratelimit-*`` headers on every response, and retries 429s
with exponential backoff (never a tight loop).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from app.rate_limiter import TokenBucket, shared_budget


class ApiFootballError(RuntimeError):
    """API-Football returned a non-empty ``errors`` payload (200 with errors, bad key, etc.)."""


class RateLimitExhausted(RuntimeError):
    """The local shared budget could not grant a token within the acquire timeout."""


@dataclass
class RateLimitInfo:
    """Last-seen rate-limit headers. API-Football returns daily + per-minute counters."""

    daily_limit: int | None = None
    daily_remaining: int | None = None
    minute_limit: int | None = None
    minute_remaining: int | None = None

    @property
    def minute_low(self) -> bool:
        """True when the per-minute remaining is low enough to defer non-urgent calls."""
        return self.minute_remaining is not None and self.minute_remaining <= 2


def _to_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ApiFootballClient:
    """Thin client over API-Football. Acquires from the shared budget before each call."""

    def __init__(
        self,
        settings: Settings | None = None,
        budget: TokenBucket | None = None,
        http_client: httpx.Client | None = None,
        *,
        acquire_timeout: float = 30.0,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        sleep=time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self.budget = budget or shared_budget
        self.acquire_timeout = acquire_timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self._owns_http = http_client is None
        self._http = http_client or self._build_http_client()
        self.last_rate_limit = RateLimitInfo()

    def _build_http_client(self) -> httpx.Client:
        if not self.settings.api_football_key:
            raise ValueError(
                "API_FOOTBALL_KEY is not set — add it to .env (see .env.example)."
            )
        return httpx.Client(
            base_url=self.settings.api_football_base_url,
            headers={"x-apisports-key": self.settings.api_football_key},
            timeout=15.0,
        )

    # -- core ---------------------------------------------------------------

    def _default_params(self) -> dict:
        """Params every World Cup call must include (docs/api-football.md)."""
        return {"league": self.settings.wc_league_id, "season": self.settings.wc_season}

    def _update_rate_limit(self, headers: httpx.Headers) -> None:
        self.last_rate_limit = RateLimitInfo(
            daily_limit=_to_int(headers.get("x-ratelimit-requests-limit")),
            daily_remaining=_to_int(headers.get("x-ratelimit-requests-remaining")),
            minute_limit=_to_int(headers.get("X-RateLimit-Limit")),
            minute_remaining=_to_int(headers.get("X-RateLimit-Remaining")),
        )

    def _request(self, path: str, params: dict | None = None) -> dict:
        merged = {**self._default_params(), **(params or {})}
        attempt = 0
        while True:
            if not self.budget.acquire(timeout=self.acquire_timeout):
                raise RateLimitExhausted(
                    "shared API-Football budget exhausted; try again shortly"
                )
            resp = self._http.get(path, params=merged)
            self._update_rate_limit(resp.headers)

            if resp.status_code == 429:
                if attempt >= self.max_retries:
                    resp.raise_for_status()
                wait = self.backoff_base * (2**attempt) + random.uniform(0, 0.5)
                self._sleep(wait)
                attempt += 1
                continue

            resp.raise_for_status()
            data = resp.json()
            errors = data.get("errors")
            if errors:  # empty list/dict is falsy
                raise ApiFootballError(str(errors))
            return data

    @staticmethod
    def _response_list(data: dict) -> list[dict]:
        return data.get("response", []) or []

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "ApiFootballClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- endpoints (docs/api-football.md) -----------------------------------

    def get_coverage(self) -> dict:
        """GET /leagues?id=1&season=2026 → the first response item (inspect its `coverage`)."""
        data = self._request("/leagues", {"id": self.settings.wc_league_id})
        items = self._response_list(data)
        return items[0] if items else {}

    def get_fixtures_by_ids(self, fixture_ids: list[int]) -> list[dict]:
        """GET /fixtures?ids=ID1-ID2-… — batch up to 20 ids in ONE call."""
        if not fixture_ids:
            return []
        if len(fixture_ids) > 20:
            raise ValueError("API-Football accepts at most 20 ids per /fixtures call")
        ids = "-".join(str(i) for i in fixture_ids)
        return self._response_list(self._request("/fixtures", {"ids": ids}))

    def get_fixtures_by_date(self, date: str) -> list[dict]:
        """GET /fixtures?date=YYYY-MM-DD — one call for the whole World Cup matchday."""
        return self._response_list(self._request("/fixtures", {"date": date}))

    def get_live_fixtures(self) -> list[dict]:
        """GET /fixtures?live=all — use sparingly; prefer batched ids for followed teams."""
        return self._response_list(self._request("/fixtures", {"live": "all"}))

    def get_standings(self) -> list[dict]:
        """GET /standings — 12 group tables (feeds the advancement calculator)."""
        return self._response_list(self._request("/standings"))

    def get_prediction(self, fixture_id: int) -> dict:
        """GET /predictions?fixture=ID — the baseline prediction."""
        items = self._response_list(self._request("/predictions", {"fixture": fixture_id}))
        return items[0] if items else {}

    def get_player_ratings(self, fixture_id: int) -> list[dict]:
        """GET /fixtures/players?fixture=ID — per-match 0–10 ratings (player-of-match source)."""
        return self._response_list(
            self._request("/fixtures/players", {"fixture": fixture_id})
        )

    def get_injuries(self) -> list[dict]:
        """GET /injuries?league=1&season=2026 — structured, preferred over scraped news."""
        return self._response_list(self._request("/injuries"))

"""API-Football HTTP client (stub).

See ../../docs/api-football.md. Every request goes through the shared rate limiter, always carries
``league=1&season=2026``, and reads the ``x-ratelimit-*`` headers on every response so callers can
back off *before* hitting 429.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.rate_limiter import TokenBucket, shared_budget


class ApiFootballClient:
    """Thin client over API-Football. Acquires from the shared budget before each call."""

    def __init__(
        self,
        settings: Settings | None = None,
        budget: TokenBucket = shared_budget,
    ) -> None:
        self.settings = settings or get_settings()
        self.budget = budget

    def _default_params(self) -> dict:
        """Params every World Cup call must include."""
        return {"league": self.settings.wc_league_id, "season": self.settings.wc_season}

    def get_coverage(self) -> dict:
        """GET /leagues?id=1&season=2026 → inspect the `coverage` object (Phase-0 check)."""
        raise NotImplementedError

    def get_fixtures_by_ids(self, fixture_ids: list[int]) -> list[dict]:
        """GET /fixtures?ids=ID1-ID2-… — batch up to 20 ids in ONE call."""
        if len(fixture_ids) > 20:
            raise ValueError("API-Football accepts at most 20 ids per /fixtures call")
        raise NotImplementedError

    def get_live_fixtures(self) -> list[dict]:
        """GET /fixtures?live=all — use sparingly; prefer batched ids for followed teams."""
        raise NotImplementedError

    def get_standings(self) -> list[dict]:
        """GET /standings — 12 group tables (feeds the advancement calculator)."""
        raise NotImplementedError

    def get_prediction(self, fixture_id: int) -> dict:
        """GET /predictions?fixture=ID — the baseline prediction."""
        raise NotImplementedError

    def get_player_ratings(self, fixture_id: int) -> list[dict]:
        """GET /fixtures/players?fixture=ID — per-match 0–10 ratings (player-of-match source)."""
        raise NotImplementedError

    def get_injuries(self) -> list[dict]:
        """GET /injuries?league=1&season=2026 — structured, preferred over scraped news."""
        raise NotImplementedError

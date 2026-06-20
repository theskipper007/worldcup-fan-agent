"""Application settings, loaded from environment / .env.

See ../docs/api-football.md — WC_LEAGUE_ID and WC_SEASON must accompany every API-Football call.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration. Mirrors .env.example."""

    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # The competition is fixed for this project.
    wc_league_id: int = 1
    wc_season: int = 2026

    db_path: str = "worldcup.db"
    backend_url: str = "http://localhost:8000"

    # Free tier is 100 requests/DAY. Cache identical API-Football calls so any given
    # request hits the network at most once per this many seconds (default 30 min).
    cache_ttl_seconds: int = 1800
    # Informational daily cap (the cache above is what actually protects it).
    daily_request_cap: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    """Return application settings (cache in real use)."""
    return Settings()

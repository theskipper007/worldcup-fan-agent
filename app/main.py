"""FastAPI entrypoint. See ../docs/architecture.md for the request flow.

Routes are stubbed: they define the API shape the Streamlit frontend will call. Live logic is
not implemented yet.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title="World Cup Fan Agent", version="0.0.1")


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    s = get_settings()
    return {"status": "ok", "league": s.wc_league_id, "season": s.wc_season}


@app.get("/digest")
def get_digest(date: str, teams: str, language: str = "en") -> dict:
    """Return the morning digest for the given followed teams.

    ``teams`` is a comma-separated list of team ids. See ../docs/agents.md (digest generator).
    """
    raise NotImplementedError("digest generation not implemented yet")


@app.get("/scoreboard")
def get_scoreboard() -> dict:
    """Return the public predictor scoreboard. See ../docs/eval.md."""
    raise NotImplementedError("scoreboard not implemented yet")

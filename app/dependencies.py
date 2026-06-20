"""FastAPI dependency providers. See ../docs/architecture.md.

The engine, session factory, and API-Football client are built once at startup (lifespan) and held
on ``app.state`` so the shared rate-limit budget and DB engine are process-wide singletons.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.agents.live_data import LiveDataAgent
from app.agents.predictor import PredictorAgent
from app.agents.reasoning import make_reasoner
from app.apifootball.client import ApiFootballClient


def get_client(request: Request) -> ApiFootballClient:
    client: ApiFootballClient | None = request.app.state.client
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="API_FOOTBALL_KEY not configured — add it to .env (see .env.example).",
        )
    return client


def get_live_data_agent(request: Request) -> LiveDataAgent:
    return LiveDataAgent(get_client(request), request.app.state.session_factory)


def get_predictor_agent(request: Request) -> PredictorAgent:
    # The client may be None (no API key); only predict() uses it — settle()/scoreboard() are
    # read-only DB aggregations, so the route guards for a missing client where it's needed.
    return PredictorAgent(
        request.app.state.client,
        request.app.state.session_factory,
        make_reasoner(),  # OSS model (Ollama) per config; 'heuristic' if no LLM
    )

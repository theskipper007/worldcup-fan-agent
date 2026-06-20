"""FastAPI entrypoint. See ../docs/architecture.md for the request flow.

Phase 0 live data agent is wired up end-to-end: the DB is initialised on startup and the
fixtures/standings routes are served by the live data agent. Predictor/tactics/digest routes
remain stubs pending later phases.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query

from app.agents.live_data import LiveDataAgent
from app.agents.predictor import PredictorAgent
from app.agents.reasoning import ReasonerError
from app.apifootball.client import ApiFootballClient, ApiFootballError, RateLimitExhausted
from app.config import get_settings
from app.db.database import init_db, make_engine, make_session_factory
from app.dependencies import get_live_data_agent, get_predictor_agent

# Match columns surfaced in API responses.
_MATCH_FIELDS = (
    "fixture_id", "round", "kickoff_utc", "home_team_id", "away_team_id",
    "home_team", "away_team", "status", "home_goals", "away_goals", "updated_at",
)


def _match_to_dict(match) -> dict:
    return {field: getattr(match, field) for field in _MATCH_FIELDS}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings)
    init_db(engine)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    # Build the API client if a key is configured; routes 503 cleanly if not.
    try:
        app.state.client = ApiFootballClient(settings)
    except ValueError:
        app.state.client = None
    try:
        yield
    finally:
        if app.state.client is not None:
            app.state.client.close()
        engine.dispose()


app = FastAPI(title="World Cup Fan Agent", version="0.0.1", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    s = get_settings()
    return {"status": "ok", "league": s.wc_league_id, "season": s.wc_season}


@app.get("/fixtures")
def fixtures(
    date: str = Query(..., description="Matchday, YYYY-MM-DD"),
    teams: str | None = Query(None, description="Comma-separated followed team ids"),
    agent: LiveDataAgent = Depends(get_live_data_agent),
) -> dict:
    """Refresh and return the World Cup fixtures for a date (optionally only followed teams)."""
    followed = [int(t) for t in teams.split(",") if t.strip()] if teams else None
    matches = agent.refresh_fixtures_by_date(date, followed)
    return {"date": date, "count": len(matches), "fixtures": [_match_to_dict(m) for m in matches]}


@app.get("/standings")
def standings(agent: LiveDataAgent = Depends(get_live_data_agent)) -> dict:
    """Return the current 12-group standings snapshot."""
    rows = agent.fetch_standings()
    return {"count": len(rows), "standings": rows}


@app.get("/predict")
def predict(
    fixture: int = Query(..., description="API-Football fixture id"),
    predictor: PredictorAgent = Depends(get_predictor_agent),
) -> dict:
    """Produce (and store) the baseline + agent prediction for a fixture (see ../docs/eval.md)."""
    if predictor.client is None:
        raise HTTPException(
            status_code=503,
            detail="API_FOOTBALL_KEY not configured — add it to .env (see .env.example).",
        )
    try:
        return predictor.predict(fixture)
    except ReasonerError as exc:
        # The OSS reasoning model is unreachable (e.g. Ollama not running / model not pulled).
        raise HTTPException(status_code=503, detail=str(exc))
    except (ApiFootballError, RateLimitExhausted) as exc:
        # Upstream data problem (plan limits, rate budget, bad fixture) — surface it cleanly, not 500.
        raise HTTPException(status_code=502, detail=f"API-Football: {exc}")


@app.post("/predict/{fixture}/settle")
def settle(
    fixture: int,
    predictor: PredictorAgent = Depends(get_predictor_agent),
) -> dict:
    """After full-time, fill the actual result and compute correctness for the scoreboard."""
    result = predictor.settle(fixture)
    if result is None:
        raise HTTPException(status_code=404, detail="no prediction or match row for that fixture")
    return result


@app.get("/scoreboard")
def get_scoreboard(predictor: PredictorAgent = Depends(get_predictor_agent)) -> dict:
    """Return the public predictor scoreboard: baseline vs agent hit-rate + lift (../docs/eval.md)."""
    return predictor.scoreboard()


@app.get("/digest")
def get_digest(date: str, teams: str, language: str = "en") -> dict:
    """Return the morning digest for the given followed teams (see ../docs/agents.md)."""
    raise NotImplementedError("digest generation not implemented yet")

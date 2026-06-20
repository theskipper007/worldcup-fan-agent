"""Predictor agent — baseline (/predictions) + open-source reasoning layer; writes `predictions`.

See ../../docs/agents.md (Predictor) and ../../docs/eval.md. Logs the API-Football baseline AND
the agent's layered call separately so the public scoreboard can compare them. Log EVERY
prediction, including wrong ones; predicted_at must be pre-kickoff; never overwrite a settled row.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.agents.reasoning import Reasoner
from app.apifootball.client import ApiFootballClient
from app.db.database import session_scope
from app.db.models import Match, Prediction

FINISHED_STATUSES = {"FT", "AET", "PEN"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pct(value) -> float | None:
    """Parse API-Football percent strings like '45%' into 0..1 floats."""
    if value is None:
        return None
    try:
        return round(float(str(value).strip().rstrip("%")) / 100.0, 4)
    except (TypeError, ValueError):
        return None


def _winner_from_scores(home: int | None, away: int | None) -> str | None:
    if home is None or away is None:
        return None
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def parse_baseline(raw: dict) -> dict:
    """Map one /predictions response entry into baseline fields (see docs/data-model.md).

    API-Football gives win/draw/win percentages but no reliable exact scoreline, so the baseline
    scoreline stays None; the winner is the argmax of the three percentages.
    """
    pred = raw.get("predictions", {}) or {}
    percent = pred.get("percent", {}) or {}
    probs = {
        "home": _pct(percent.get("home")),
        "draw": _pct(percent.get("draw")),
        "away": _pct(percent.get("away")),
    }
    known = {k: v for k, v in probs.items() if v is not None}
    winner = max(known, key=known.get) if known else None
    return {
        "winner": winner,
        "prob_home": probs["home"],
        "prob_draw": probs["draw"],
        "prob_away": probs["away"],
        "advice": pred.get("advice"),
        "home_team": (raw.get("teams", {}).get("home", {}) or {}).get("name"),
        "away_team": (raw.get("teams", {}).get("away", {}) or {}).get("name"),
    }


class PredictorAgent:
    """Produces and settles predictions, and aggregates the public scoreboard."""

    def __init__(
        self,
        client: ApiFootballClient,
        session_factory: sessionmaker[Session],
        reasoner: Reasoner,
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.reasoner = reasoner

    def predict(self, fixture_id: int, context: dict | None = None) -> dict:
        """Pull the baseline, layer the reasoner's call, and store both. Idempotent before settle.

        ``context`` may carry injuries/sentiment for the reasoner. Returns the stored row as a dict.
        """
        with session_scope(self.session_factory) as session:
            existing = session.get(Prediction, fixture_id)
            if existing is not None and existing.actual_winner is not None:
                return _prediction_to_dict(existing)  # settled — never overwrite

        baseline = parse_baseline(self.client.get_prediction(fixture_id))

        reason_context = {
            "home_team": baseline["home_team"],
            "away_team": baseline["away_team"],
            "baseline": baseline,
            **(context or {}),
        }
        agent = self.reasoner.reason(reason_context)

        row = Prediction(
            fixture_id=fixture_id,
            predicted_at=_now_iso(),
            baseline_winner=baseline["winner"],
            baseline_prob_home=baseline["prob_home"],
            baseline_prob_draw=baseline["prob_draw"],
            baseline_prob_away=baseline["prob_away"],
            agent_winner=agent["winner"],
            agent_home_score=agent["home_score"],
            agent_away_score=agent["away_score"],
            agent_rationale=agent["rationale"],
        )
        with session_scope(self.session_factory) as session:
            merged = session.merge(row)
            session.flush()
            return _prediction_to_dict(merged)

    def settle(self, fixture_id: int) -> dict | None:
        """After FT, fill the actual result and compute baseline_correct / agent_correct."""
        with session_scope(self.session_factory) as session:
            pred = session.get(Prediction, fixture_id)
            match = session.get(Match, fixture_id)
            if pred is None or match is None:
                return None
            if match.status not in FINISHED_STATUSES:
                return _prediction_to_dict(pred)  # not finished yet

            actual = _winner_from_scores(match.home_goals, match.away_goals)
            pred.actual_winner = actual
            pred.actual_home_score = match.home_goals
            pred.actual_away_score = match.away_goals
            if actual is not None:
                pred.baseline_correct = int(pred.baseline_winner == actual)
                pred.agent_correct = int(pred.agent_winner == actual)
            session.flush()
            return _prediction_to_dict(pred)

    def scoreboard(self) -> dict:
        """Aggregate settled predictions: baseline vs agent hit-rate, and the lift (docs/eval.md)."""
        with session_scope(self.session_factory) as session:
            settled = (
                session.query(Prediction)
                .filter(Prediction.agent_correct.isnot(None))
                .all()
            )
        n = len(settled)
        if n == 0:
            return {"settled": 0, "baseline_hit_rate": None, "agent_hit_rate": None,
                    "lift": None, "agent_exact": None}

        baseline_hits = sum(p.baseline_correct or 0 for p in settled)
        agent_hits = sum(p.agent_correct or 0 for p in settled)
        # Baseline has no exact scoreline from API-Football, so only the agent's exact rate is reported.
        agent_exact = sum(
            1 for p in settled
            if p.agent_home_score == p.actual_home_score
            and p.agent_away_score == p.actual_away_score
        )
        baseline_rate = round(baseline_hits / n, 4)
        agent_rate = round(agent_hits / n, 4)
        return {
            "settled": n,
            "baseline_hit_rate": baseline_rate,
            "agent_hit_rate": agent_rate,
            "lift": round(agent_rate - baseline_rate, 4),
            "agent_exact": round(agent_exact / n, 4),
        }


def _prediction_to_dict(p: Prediction) -> dict:
    return {
        "fixture_id": p.fixture_id,
        "predicted_at": p.predicted_at,
        "baseline_winner": p.baseline_winner,
        "baseline_prob_home": p.baseline_prob_home,
        "baseline_prob_draw": p.baseline_prob_draw,
        "baseline_prob_away": p.baseline_prob_away,
        "agent_winner": p.agent_winner,
        "agent_home_score": p.agent_home_score,
        "agent_away_score": p.agent_away_score,
        "agent_rationale": p.agent_rationale,
        "actual_winner": p.actual_winner,
        "actual_home_score": p.actual_home_score,
        "actual_away_score": p.actual_away_score,
        "baseline_correct": p.baseline_correct,
        "agent_correct": p.agent_correct,
    }

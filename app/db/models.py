"""SQLAlchemy models mirroring schema.sql. See ../../docs/data-model.md.

These are scaffold definitions of the table shapes; session/engine wiring is added in the build phase.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Match(Base):
    """Written by the live data agent."""

    __tablename__ = "matches"

    fixture_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round: Mapped[str | None] = mapped_column(String)
    kickoff_utc: Mapped[str | None] = mapped_column(String)
    home_team_id: Mapped[int | None] = mapped_column(Integer)
    away_team_id: Mapped[int | None] = mapped_column(Integer)
    home_team: Mapped[str | None] = mapped_column(String)
    away_team: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[str | None] = mapped_column(String)


class Prediction(Base):
    """Written by the predictor agent. Baseline + agent + actual, for independent eval."""

    __tablename__ = "predictions"

    fixture_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.fixture_id"), primary_key=True
    )
    predicted_at: Mapped[str | None] = mapped_column(String)
    baseline_winner: Mapped[str | None] = mapped_column(String)
    baseline_home_score: Mapped[int | None] = mapped_column(Integer)
    baseline_away_score: Mapped[int | None] = mapped_column(Integer)
    baseline_prob_home: Mapped[float | None] = mapped_column(Float)
    baseline_prob_draw: Mapped[float | None] = mapped_column(Float)
    baseline_prob_away: Mapped[float | None] = mapped_column(Float)
    agent_winner: Mapped[str | None] = mapped_column(String)
    agent_home_score: Mapped[int | None] = mapped_column(Integer)
    agent_away_score: Mapped[int | None] = mapped_column(Integer)
    agent_rationale: Mapped[str | None] = mapped_column(String)
    actual_winner: Mapped[str | None] = mapped_column(String)
    actual_home_score: Mapped[int | None] = mapped_column(Integer)
    actual_away_score: Mapped[int | None] = mapped_column(Integer)
    baseline_correct: Mapped[int | None] = mapped_column(Integer)
    agent_correct: Mapped[int | None] = mapped_column(Integer)


class TacticalReport(Base):
    """Written by the tactics agent. Every number traces to stat_sources."""

    __tablename__ = "tactical_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("matches.fixture_id")
    )
    formation_home: Mapped[str | None] = mapped_column(String)
    formation_away: Mapped[str | None] = mapped_column(String)
    possession_home: Mapped[int | None] = mapped_column(Integer)
    possession_away: Mapped[int | None] = mapped_column(Integer)
    shots_home: Mapped[int | None] = mapped_column(Integer)
    shots_away: Mapped[int | None] = mapped_column(Integer)
    player_of_match_id: Mapped[int | None] = mapped_column(Integer)
    player_of_match_rating: Mapped[float | None] = mapped_column(Float)
    narrative: Mapped[str | None] = mapped_column(String)
    stat_sources: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String)


class Digest(Base):
    """Written by the digest generator."""

    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    digest_date: Mapped[str | None] = mapped_column(String)
    followed_teams: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String)

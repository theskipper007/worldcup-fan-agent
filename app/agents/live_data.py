"""Live data agent — scores, fixtures, standings. Writes `matches`.

See ../../docs/agents.md (Live data agent). Poll only fixtures a followed team is in; batch via
/fixtures?ids=… rather than looping. All API access goes through the shared-budget client.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.apifootball.client import ApiFootballClient
from app.db.database import session_scope
from app.db.models import Match


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_fixture(raw: dict) -> Match:
    """Map one API-Football fixture entry onto a Match row (see docs/data-model.md)."""
    fixture = raw.get("fixture", {})
    league = raw.get("league", {})
    teams = raw.get("teams", {})
    goals = raw.get("goals", {})
    home, away = teams.get("home", {}), teams.get("away", {})
    return Match(
        fixture_id=fixture.get("id"),
        round=league.get("round"),
        kickoff_utc=fixture.get("date"),
        home_team_id=home.get("id"),
        away_team_id=away.get("id"),
        home_team=home.get("name"),
        away_team=away.get("name"),
        status=(fixture.get("status") or {}).get("short"),
        home_goals=goals.get("home"),
        away_goals=goals.get("away"),
        updated_at=_now_iso(),
    )


def _involves_followed(raw: dict, followed_team_ids: set[int]) -> bool:
    teams = raw.get("teams", {})
    ids = {teams.get("home", {}).get("id"), teams.get("away", {}).get("id")}
    return bool(ids & followed_team_ids)


def parse_standings(raw_standings: list[dict]) -> list[dict]:
    """Flatten the /standings payload into one row per team with its group.

    API-Football nests groups under ``response[0].league.standings`` (a list of group tables).
    """
    rows: list[dict] = []
    for entry in raw_standings:
        groups = (entry.get("league") or {}).get("standings") or []
        for group in groups:
            for team in group:
                rows.append(
                    {
                        "group": team.get("group"),
                        "rank": team.get("rank"),
                        "team_id": (team.get("team") or {}).get("id"),
                        "team": (team.get("team") or {}).get("name"),
                        "points": team.get("points"),
                        "goals_diff": team.get("goalsDiff"),
                        "form": team.get("form"),
                    }
                )
    return rows


class LiveDataAgent:
    """Fetches live/finished fixtures and standings, persisting fixtures to `matches`."""

    def __init__(
        self,
        client: ApiFootballClient,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.client = client
        self.session_factory = session_factory

    def _persist(self, raws: list[dict]) -> list[Match]:
        rows = [parse_fixture(r) for r in raws if r.get("fixture", {}).get("id")]
        with session_scope(self.session_factory) as session:
            for row in rows:
                session.merge(row)  # upsert by fixture_id
        return rows

    def refresh_fixtures_by_ids(self, fixture_ids: list[int]) -> list[Match]:
        """Batch-refresh specific fixtures (≤20) and persist them."""
        return self._persist(self.client.get_fixtures_by_ids(fixture_ids))

    def refresh_fixtures_by_date(
        self, date: str, followed_team_ids: list[int] | None = None
    ) -> list[Match]:
        """Pull a whole matchday in one call, optionally keep only followed teams, persist."""
        raws = self.client.get_fixtures_by_date(date)
        if followed_team_ids:
            wanted = set(followed_team_ids)
            raws = [r for r in raws if _involves_followed(r, wanted)]
        return self._persist(raws)

    def fetch_standings(self) -> list[dict]:
        """Return the current 12-group standings snapshot (not persisted; feeds advancement)."""
        return parse_standings(self.client.get_standings())

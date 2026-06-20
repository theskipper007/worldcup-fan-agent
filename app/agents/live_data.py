"""Live data agent — scores, fixtures, standings, rounds. Writes `matches`.

See ../../docs/agents.md (Live data agent). Poll only fixtures a followed team is in, 30–60s.
Batch via /fixtures?ids=… — never loop one request per match.
"""

from __future__ import annotations


def fetch_followed_fixtures(followed_team_ids: list[int], date: str) -> list[dict]:
    """Return finished/in-progress fixtures involving followed teams (one batched call)."""
    raise NotImplementedError


def fetch_standings() -> list[dict]:
    """Return the current 12-group standings snapshot."""
    raise NotImplementedError

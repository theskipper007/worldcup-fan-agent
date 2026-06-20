"""Tactics agent — stat-grounded narrative + player-of-match. Writes `tactical_reports`.

See ../../docs/agents.md (Tactics). Every numeric claim must trace to a pulled stat (recorded in
stat_sources). Player-of-match = highest /fixtures/players rating, NEVER eyeballed.
"""

from __future__ import annotations


def analyze(fixture_id: int) -> dict:
    """Build the tactical report for a finished fixture from real pulled stats."""
    raise NotImplementedError

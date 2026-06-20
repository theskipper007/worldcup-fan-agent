"""Orchestrator agent — routes a request to the specialists and assembles the result.

Claude tool-use. See ../../docs/agents.md (Orchestrator) and ../../docs/architecture.md.
"""

from __future__ import annotations


def run(followed_team_ids: list[int], date: str, language: str = "en") -> dict:
    """Run a digest/predict/analyze cycle for the followed teams on the given date.

    Decides which specialists to invoke, then hands their outputs to the digest generator.
    Holds no API budget logic of its own.
    """
    raise NotImplementedError

"""Digest generator — the fan-facing ~90-second summary. Writes `digests`.

See ../../docs/agents.md (Digest generator). Reads matches/predictions/tactical_reports — makes NO
fresh API calls. Highlights are links/embeds to official sources only.
"""

from __future__ import annotations


def generate(followed_team_ids: list[int], date: str, language: str = "en") -> dict:
    """Assemble the digest (summary + advancement scenarios) from stored rows and persist it."""
    raise NotImplementedError

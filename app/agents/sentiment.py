"""Sentiment agent — injuries + news context feeding the predictor.

See ../../docs/agents.md (Sentiment). Prefer the structured /injuries endpoint over scraped news.
Writes nothing persistent.
"""

from __future__ import annotations


def gather(team_ids: list[int]) -> dict:
    """Return injuries + sentiment context for the predictor's reasoning layer."""
    raise NotImplementedError

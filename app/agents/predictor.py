"""Predictor agent — baseline (/predictions) + reasoning layer; writes `predictions`.

See ../../docs/agents.md (Predictor) and ../../docs/eval.md. Log EVERY prediction, including the
wrong ones. predicted_at must be pre-kickoff. Never overwrite a settled row.
"""

from __future__ import annotations


def predict(fixture_id: int) -> dict:
    """Pull the baseline, layer agent reasoning (sentiment/injuries/tactics), store both."""
    raise NotImplementedError


def settle(fixture_id: int) -> dict:
    """After FT: fill actual result and compute baseline_correct / agent_correct."""
    raise NotImplementedError

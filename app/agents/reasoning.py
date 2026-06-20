"""Reasoning layer for the predictor agent — an open-source model, not a hosted LLM.

The model is served over an **OpenAI-compatible** API (default: local Ollama, model qwen3.5:9b),
so the same code works with Groq / OpenRouter / vLLM by changing ``LLM_BASE_URL`` / ``LLM_API_KEY``
/ ``LLM_MODEL``. A deterministic ``HeuristicReasoner`` is the zero-setup fallback (and the offline
test path).

Each call is **stateless**: ``reason()`` receives only the structured data for that one prediction
(team names, baseline, optional injuries) and builds a fresh two-message prompt. No conversation
history is carried across calls or shared between agents — that keeps token cost flat (one stats
payload + instructions, ~8K is plenty) and the predictions reproducible.

See ../../docs/agents.md (Predictor) and ../../docs/eval.md. The reasoner layers tactical/context
reasoning on top of the API-Football baseline; its output is logged separately for the scoreboard.
"""

from __future__ import annotations

import json
from typing import Protocol

from app.config import Settings, get_settings

# The agent must return exactly this shape (validated below).
PREDICTION_KEYS = ("winner", "home_score", "away_score", "rationale")

SYSTEM_PROMPT = (
    "You are a football match predictor for the 2026 World Cup. You are given a baseline "
    "prediction from a stats provider plus extra context (injuries, form, sentiment). Reconsider "
    "it and return YOUR call. Respond with ONLY a JSON object with keys: "
    'winner ("home"|"draw"|"away"), home_score (int), away_score (int), rationale (one short '
    "sentence citing the inputs you used). Do not include any text outside the JSON."
)


class ReasonerError(RuntimeError):
    """The reasoning model failed or returned an unusable response."""


class Reasoner(Protocol):
    """Turns a prediction context into the agent's call."""

    def reason(self, context: dict) -> dict:  # -> {winner, home_score, away_score, rationale}
        ...


def build_user_prompt(context: dict) -> str:
    """Render the prediction context for the model."""
    b = context.get("baseline", {})
    lines = [
        f"Match: {context.get('home_team', 'Home')} (home) vs {context.get('away_team', 'Away')} (away).",
        "Baseline prediction (API-Football):",
        f"  winner: {b.get('winner')}",
        f"  win probabilities — home {b.get('prob_home')}, draw {b.get('prob_draw')}, away {b.get('prob_away')}",
        f"  advice: {b.get('advice')}",
    ]
    injuries = context.get("injuries")
    if injuries:
        lines.append(f"Injuries / context: {injuries}")
    lines.append('Return the JSON object now.')
    return "\n".join(lines)


def _validate(data: dict) -> dict:
    """Coerce/validate the model output into the prediction contract."""
    if not isinstance(data, dict) or any(k not in data for k in PREDICTION_KEYS):
        raise ReasonerError(f"reasoner output missing keys: {data!r}")
    winner = str(data["winner"]).strip().lower()
    if winner not in {"home", "draw", "away"}:
        raise ReasonerError(f"invalid winner: {data['winner']!r}")
    try:
        home = int(data["home_score"])
        away = int(data["away_score"])
    except (TypeError, ValueError) as exc:
        raise ReasonerError(f"non-integer score: {data!r}") from exc
    return {
        "winner": winner,
        "home_score": home,
        "away_score": away,
        "rationale": str(data["rationale"]).strip(),
    }


class HeuristicReasoner:
    """No-LLM fallback: mirror the baseline winner and derive a plausible scoreline.

    Deterministic, dependency-free — used when REASONER_PROVIDER=heuristic, or as the offline
    path in tests. It never *beats* the baseline (by construction); it keeps the pipeline runnable.
    """

    def reason(self, context: dict) -> dict:
        b = context.get("baseline", {})
        winner = (b.get("winner") or "home").lower()
        if winner == "home":
            home, away = 2, 1
        elif winner == "away":
            home, away = 1, 2
        else:
            home, away = 1, 1
        return _validate(
            {
                "winner": winner,
                "home_score": home,
                "away_score": away,
                "rationale": "Mirrors the API-Football baseline (no reasoning model configured).",
            }
        )


class OpenAICompatibleReasoner:
    """Calls an open-source model over an OpenAI-compatible chat API (default: local Ollama)."""

    def __init__(self, settings: Settings | None = None, client=None) -> None:
        self.settings = settings or get_settings()
        self._client = client  # injectable for tests; built lazily otherwise

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise ReasonerError("the 'openai' package is required for the OSS reasoner") from exc
            self._client = OpenAI(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key or "ollama",
            )
        return self._client

    def _system_prompt(self) -> str:
        # Qwen3 soft-switch: a trailing /no_think disables the model's thinking block for this turn
        # (server-agnostic — works over any OpenAI-compatible endpoint, unlike a template kwarg).
        if not self.settings.llm_enable_thinking:
            return SYSTEM_PROMPT + "\n/no_think"
        return SYSTEM_PROMPT

    def reason(self, context: dict) -> dict:
        client = self._get_client()
        try:
            resp = client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": build_user_prompt(context)},
                ],
                response_format={"type": "json_object"},  # force valid JSON (supported by Ollama)
                max_tokens=self.settings.llm_max_tokens,
                temperature=0.3,
            )
        except Exception as exc:  # network down, model not pulled, etc.
            raise ReasonerError(
                f"reasoning model call failed ({self.settings.llm_base_url}, "
                f"model={self.settings.llm_model}): {exc}. Is Ollama running and the model pulled?"
            ) from exc
        content = resp.choices[0].message.content or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ReasonerError(f"reasoner did not return JSON: {content!r}") from exc
        return _validate(data)


def make_reasoner(settings: Settings | None = None) -> Reasoner:
    """Pick the reasoner from config. Defaults to the local OSS model; 'heuristic' = no LLM."""
    settings = settings or get_settings()
    if settings.reasoner_provider == "heuristic":
        return HeuristicReasoner()
    return OpenAICompatibleReasoner(settings)

# Agent contracts

All agents call API-Football only through the shared rate-limited client
([api-football.md](api-football.md)). Each writes exactly the table named in
[data-model.md](data-model.md). The LLM reasoning layer is an open-source model over an
OpenAI-compatible API (default: local Ollama, `qwen3.5:9b`, thinking off) — see
[`../app/agents/reasoning.py`](../app/agents/reasoning.py). Each call is stateless: only the
structured data for that prediction is passed, never conversation history across agents.

---

## Orchestrator
- **Trigger:** scheduled morning run, or an on-demand user request (predict / analyze / digest).
- **Input:** `{ followed_team_ids: int[], date: ISO-date, language: "en"|"ta"|"zh"|"ar" }`.
- **Does:** decides which specialists to invoke and in what order; assembles their outputs; hands
  the result to the digest generator. Holds no API budget logic of its own.
- **Output:** a rendered digest + updated scoreboard state.

## Live data agent
- **Trigger:** orchestrator; live polling loop for in-progress followed matches (30–60s cadence).
- **Endpoints:** `/fixtures?ids=…` (batched), `/fixtures?live=all` (sparingly), `/standings`,
  `/fixtures/rounds`.
- **Writes:** `matches`.
- **Output:** finished/in-progress fixtures for followed teams + current standings snapshot.
- **Guardrail:** poll only fixtures a followed team is in; never the full live board on a timer.

## Predictor agent
- **Trigger:** orchestrator, **pre-kickoff** for upcoming followed matches; settle pass after FT.
- **Endpoints:** `/predictions?fixture=ID` (baseline), plus context from the sentiment agent.
- **Writes:** `predictions` — stores the baseline AND the agent's layered call AND, after FT,
  the actual result and the two `*_correct` flags.
- **Output:** a prediction row; later, an eval update.
- **Guardrails:** prediction `predicted_at` must be before kickoff; **log every prediction,
  including wrong ones**; never silently overwrite a settled row.

## Tactics agent
- **Trigger:** orchestrator, after a followed match reaches FT.
- **Endpoints:** `/fixtures?id=ID` (events/lineups/statistics), `/fixtures/players?fixture=ID`
  (ratings), `/coachs?team=ID`, `/fixtures/headtohead?h2h=A-B`.
- **Writes:** `tactical_reports`.
- **Output:** stat-grounded narrative + player-of-match.
- **Guardrails:** **every numeric claim must trace to one of those calls** (record sources in
  `stat_sources`); **player-of-match = highest `/fixtures/players` rating**, never the top scorer
  picked by eye.

## Sentiment agent
- **Trigger:** orchestrator, feeding the predictor before a match.
- **Endpoints/tools:** `/injuries?league=1&season=2026` (structured — prefer over scraped news),
  web search for narrative context.
- **Writes:** nothing persistent (feeds predictor inline; may cache).
- **Output:** injuries + sentiment context object for the predictor's reasoning layer.
- **Guardrail:** prefer the structured `/injuries` endpoint over scraped news where both exist.

## Digest generator (not an API agent)
- **Trigger:** orchestrator, after specialists have written their rows.
- **Reads:** `matches`, `predictions`, `tactical_reports` (no fresh API calls).
- **Writes:** `digests`.
- **Output:** the ~90-second fan-facing summary (+ multilingual variant when enabled) +
  advancement scenarios derived from the standings snapshot.
- **Guardrails:** highlights are **links/embeds to official sources only** — never host or
  redistribute footage.

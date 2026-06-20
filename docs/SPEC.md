# World Cup Fan Agent — Specification

> Build-against specs derived from [`../worldcup-agent-plan.md`](../worldcup-agent-plan.md)
> (the canonical narrative). This document is the index; the detail specs below are the
> contracts to implement against.

## Product, in one paragraph

The 2026 World Cup (US/Mexico/Canada) kicks off between 1am–7am for fans in Singapore and
Dubai. The Fan Agent watches the matches you sleep through, produces a ~90-second **morning
digest** for the 2–3 teams you follow, explains *why* results matter (including the expanded
48-team / 12-group advancement picture), and keeps a **public predictor scoreboard** that
honestly logs how well it predicts versus the API-Football baseline.

## Feature ladder (priority checklist)

### P0 — must build first
- [ ] **Live data ingestion** — scores, fixtures, formations, shot/possession stats
- [ ] **Predictor agent + public eval log** — pull `/predictions` baseline, layer agent reasoning,
      log **both** accuracies separately (see [eval.md](eval.md))
- [ ] **Morning digest generator** — the fan-facing product (see [agents.md](agents.md))
- [ ] **Advancement scenario calculator** — powered by the real `/standings` endpoint

### P1 — differentiators (after P0 is stable)
- [ ] **Tactical analysis agent** — narrative grounded in real pulled stats; player-of-match from
      `/fixtures/players` ratings, never eyeballed
- [ ] **Highlights linking** — official sources only (FIFA+, official YouTube); no hosting
- [ ] **Multilingual toggle** — EN + Tamil/Mandarin (SG) or EN + Arabic (Dubai)

### P2 — stretch
- [ ] **Live second-screen companion** — chat Q&A during a live match
- [ ] **Public embeddable widget** — drop the scoreboard/digest into another site

## Detail specs

| Spec | Covers |
|---|---|
| [architecture.md](architecture.md) | Orchestrator + 4 specialist agents, request flow, deploy model |
| [api-football.md](api-football.md) | Endpoint catalog, `league=1&season=2026`, coverage check, **rate-limit ruleset** |
| [data-model.md](data-model.md) | SQLite schema for `matches`, `predictions`, `tactical_reports`, `digests` |
| [agents.md](agents.md) | Per-agent input/output contracts and guardrails |
| [eval.md](eval.md) | Predictor scoreboard: baseline vs agent accuracy, logging discipline |

## Stack (locked)

- **Backend:** Python + FastAPI, Claude API (tool use). Models: default to latest Claude
  (`claude-opus-4-8` for orchestration/reasoning; a smaller model for routing if needed).
- **DB:** SQLite (`fastest to ship`; schema written to migrate to Postgres later).
- **Frontend:** Streamlit.
- **Data:** API-Football free tier (10 req/min) — see the rate-limit ruleset before writing any client.
- **Deploy:** persistent web service (Fly.io / Render), **not** edge/serverless — per-IP rate limiting.

## Non-negotiable guardrails

1. Never host or redistribute highlight footage — link/embed official sources only.
2. Every tactical claim must cite a real pulled stat, never an invented one.
3. Log every prediction honestly, including the wrong ones — the scoreboard's credibility is the point.
4. `/odds` and `/odds/live` are **deliberately out of scope** (keeps "fan companion", not "betting tool").

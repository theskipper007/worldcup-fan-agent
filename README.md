# World Cup Fan Agent ⚽🌙

An agent that watches the 2026 World Cup matches you sleep through (kickoffs land at 1–7am in
Singapore and Dubai), gives you a ~90-second **morning digest** for the 2–3 teams you follow, and
keeps a **public predictor scoreboard** that honestly logs how well it predicts versus the
API-Football baseline.

> **Status: scaffold + specs.** This repo currently contains the full specification and an
> importable project skeleton. No live API/agent logic is implemented yet — that's the next build
> phase, against the specs in [`docs/`](docs/).

## Why

The expanded 48-team / 12-group format is genuinely hard to follow, and reconstructing a night of
matches means scrolling five apps and three group chats. The agent's job: tell you what mattered,
and tell you honestly whether it actually knows what it's talking about.

## Specs

Start at [`docs/SPEC.md`](docs/SPEC.md). Detail specs:

- [Architecture](docs/architecture.md) — orchestrator + 4 specialist agents, request flow, deploy model
- [API-Football integration](docs/api-football.md) — endpoints, the coverage check, the rate-limit ruleset
- [Data model](docs/data-model.md) — SQLite schema
- [Agent contracts](docs/agents.md) — per-agent inputs/outputs/guardrails
- [Predictor scoreboard / eval](docs/eval.md)

The original narrative plan is kept at [`worldcup-agent-plan.md`](worldcup-agent-plan.md).

## Stack

Python + FastAPI · Claude API (tool use) · SQLite · Streamlit · API-Football (free tier).
Deploys as a persistent web service (not serverless — per-IP rate limiting).

## Layout

```
app/         FastAPI backend: orchestrator + specialist agents, shared rate limiter, DB
frontend/    Streamlit UI (digest + public scoreboard)
docs/        Specifications
tests/       Tests
```

## Quickstart (once dependencies are implemented)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in your keys
uvicorn app.main:app --reload          # backend
streamlit run frontend/streamlit_app.py # UI, in another terminal
pytest -q                              # tests
```

## Guardrails

- Never host or redistribute highlight footage — link/embed official sources only.
- Every tactical claim cites a real pulled stat.
- Log every prediction, including the wrong ones.
- `/odds` is deliberately out of scope (fan companion, not betting tool).

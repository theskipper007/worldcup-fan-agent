# World Cup Fan Agent — Project Plan

## The use case

Kickoff times for the 2026 World Cup (hosted across the US, Mexico, and Canada) land between 1am and 7am for most fans in Singapore and Dubai. Reconstructing what happened means scrolling five apps and three group chats every morning. On top of that, the expanded 48-team, 12-group format (top two plus the eight best third-place teams advance) is genuinely hard to follow even for longtime fans.

**The agent's job:** watch the matches you can't stay up for, tell you what mattered, and tell you honestly whether it actually knows what it's talking about.

Target user: a fan following 2–3 teams who wants a 90-second daily digest instead of morning forensics — and, not coincidentally, a hiring manager scanning a portfolio for evidence of real agent engineering rather than a wrapper around an API.

## Features, in priority order

### P0 — must build first (these make the product usable)
1. **Live data ingestion** — scores, fixtures, formations, shot/possession stats
2. **Predictor agent + public eval log** — API-Football ships its own `/predictions` endpoint (predicted winner, score, win/draw/win probabilities). Don't try to beat it from a cold start — pull it as a baseline, layer the predictor agent's reasoning (sentiment, injuries, tactical context) on top, and log **both** the raw baseline accuracy and the agent's accuracy on the public scoreboard. "Our agent beats the baseline by X points" is a far stronger eval artifact than an accuracy number with nothing to compare it to. Start logging immediately so there's a track record by launch.
3. **Morning digest generator** — the actual fan-facing product: followed teams, what happened, why it matters
4. **Advancement scenario calculator** — powered by the real `/standings` endpoint (12 group tables, points, goal difference, form) rather than custom-built logic

### P1 — differentiators (build once P0 is stable)
5. **Tactical analysis agent** — narrative grounded in real pulled stats (formation, possession, shot map, subs, head-to-head history). "Player of the match" pulls from the real `/fixtures/players` per-match rating endpoint (0–10 scores) instead of a placeholder — never just pick the top scorer by eye.
6. **Highlights linking** — links/embeds to official sources (FIFA+, official YouTube) keyed by match and minute. No hosting or redistributing video.
7. **Multilingual output toggle** — English + Tamil/Mandarin (Singapore framing) or English + Arabic (Dubai framing)

### P2 — stretch, only if time allows
8. **Live second-screen companion** — chat Q&A during a match you are watching live
9. **Public embeddable widget** — lets others drop your scoreboard/digest into their own site

## Architecture (summary)

Orchestrator agent (Claude, tool-use) routes between four specialist agents, each mapped to specific API-Football endpoints (`league=1&season=2026` on every call):

| Agent | Endpoints | Notes |
|---|---|---|
| Live data | `/fixtures?live=all`, `/fixtures?ids=ID1-ID2-…` (batch up to 20), `/standings`, `/fixtures/rounds` | Live data refreshes every 15s on API-Football's side — poll on that cadence, not faster |
| Predictor | `/predictions?fixture=ID` (baseline) + own reasoning layer | Logs baseline accuracy and agent accuracy separately |
| Tactics | `/fixtures?id=ID` (embedded events/lineups/statistics), `/fixtures/players?fixture=ID` (player ratings), `/coachs?team=ID`, `/fixtures/headtohead?h2h=A-B` | All numbers must trace back to one of these calls |
| Sentiment | Web search + `/injuries?league=1&season=2026` | Use the structured injuries endpoint over scraped news where both exist — it's more reliable |

Predictor and tactics agents both feed a public output: accuracy log + match reports.

**Before building anything else:** call `/leagues?id=1&season=2026` and inspect the returned `coverage` object. It tells you which data types (lineups, player stats, predictions, odds, etc.) are actually populated for this competition — coverage can be patchy match-to-match early in the tournament, so check before assuming a field will be there.

**Deliberately out of scope:** `/odds` and `/odds/live`. They exist and are easy to wire in, but pulling in betting odds shifts the product's framing from "fan companion" to "betting tool" — not the positioning you want for this portfolio piece.

## Tech stack
- Backend: Python + FastAPI, Claude API with tool use
- DB: Postgres or SQLite — tables for `matches`, `predictions`, `tactical_reports`, `digests`
- Data: API-Football (free tier) as primary source — confirmed fields: `team.logo`, `player.photo`, per-match player ratings via `/fixtures/players`, group standings via `/standings`. openfootball/worldcup.json and football-data.org stay as fallbacks if you hit rate limits.
- Frontend: Streamlit (fastest to ship) or Next.js (more polished, better for a public launch)
- Deploy: a persistent web service on Fly.io or Render — not an edge/serverless function (see rate limiting below)

## Rate limiting (free tier — design around this explicitly)

The free plan is capped at **10 requests per minute**, plus a separate daily cap (check your dashboard for the exact number — it's returned in the `x-ratelimit-requests-limit` / `x-ratelimit-requests-remaining` headers on every response). That's a hard constraint, not a soft guideline: a naive 15-second live-score poll alone would eat 4 of your 10 requests every minute, before the predictor, tactics, or sentiment agents make a single call.

Design choices this forces:
- **One shared rate budget, not one per agent.** Build a small token-bucket/queue layer in the backend that all four agents call through, so two agents never independently decide it's safe to fire at the same moment. Independent `setInterval` polling per agent is exactly how you trip a 429.
- **Batch instead of looping.** Use `/fixtures?ids=ID1-ID2-…` (up to 20 IDs in one call) instead of one request per match — this is the single biggest lever on the free tier.
- **Poll live data less aggressively than the API updates.** API-Football refreshes live fixtures every 15s on their end, but you don't have to match that. Poll every 30–60s, and only for matches a followed team is actually playing in — not the full live board.
- **Cache aggressively for anything that isn't live.** Teams, players, standings, coaches — cache these for minutes to hours, not seconds. They don't need a fresh call on every digest generation.
- **Read the rate-limit headers and back off before you hit 429**, not after. If `X-RateLimit-Remaining` is low, delay non-urgent calls (tactics, sentiment) and protect the budget for live score updates.
- **Retry 429s with exponential backoff**, never a tight retry loop — a 429 means you're already over budget, and hammering it again risks an IP/key-level block, not just a rejected request.
- **Avoid shared-IP serverless hosting** (Lambda, Cloudflare Workers, Vercel/Netlify Functions) for the API-calling backend specifically — rate limiting is enforced per IP as well as per key, so a shared egress IP can get you throttled by someone else's traffic. A standard persistent service (a regular Fly.io/Render web service, not edge functions) keeps you on a more predictable IP.
- If the free tier becomes the actual bottleneck once you're live (not before), the Pro plan moves you to 300 requests/minute — but treat that as a fallback, not a Phase 0 decision.

## Implementation order & timeline

Today is June 21, 2026. The official round-by-round schedule: group stage runs June 11–27 (72 matches), Round of 32 June 28–July 3, Round of 16 July 4–7, quarter-finals July 9–11, semi-finals July 14–15, third-place match and final July 18–19.

| Phase | Days | Work |
|---|---|---|
| 0 | Day 1 | Repo scaffold, API keys, check the `coverage` object on `/leagues?id=1`, DB schema, live data agent working end-to-end |
| 1 | Day 2–3 | Predictor agent (baseline + agent layer) + eval logging — start logging now to build a track record before launch |
| 2 | Day 3–6 | Digest generator + advancement calculator (the core fan-facing feature) |
| 3 | Day 6–9 | Tactics agent + highlights linking |
| 4 | Day 9–11 | Multilingual toggle + frontend polish |
| 5 | June 28–July 3 | Public launch, timed to the Round of 32 |
| 6 | Through July 19 | Daily content cadence, then a post-mortem after the final |

## Guardrails
- Never host or redistribute highlight footage — link/embed official sources only
- Every tactical claim must cite a real pulled stat, never an invented one
- Log every prediction honestly, including the wrong ones — the scoreboard's credibility is the entire point

## Why this works as a portfolio piece
Hiring signals in Singapore and Dubai right now favor deployed agents, eval suites, and repos over credentials alone — this project produces all three, plus a market-specific angle (multilingual output) that ties directly to local hiring priorities (UAE's Arabic-NLP push, Singapore's multilingual base).

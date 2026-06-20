# API-Football integration spec

Primary data source: **API-Football** (free tier). Base URL `https://v3.football.api-sports.io`.
Auth via the `x-apisports-key` header (`API_FOOTBALL_KEY`).

> **Every call MUST include `league=1&season=2026`** (league 1 = the World Cup in API-Football's
> schema). A request without these is a bug.

## Phase-0 coverage check (do this before building anything else)

Call `GET /leagues?id=1&season=2026` and inspect the returned **`coverage`** object. It declares
which data types (lineups, player stats, predictions, odds, events, …) are actually populated for
this competition. Coverage can be patchy match-to-match early in the tournament, so **check before
assuming a field exists**. Cache this result; re-check occasionally, not per request.

## Endpoint catalog

| Agent | Endpoint | Use |
|---|---|---|
| Live data | `GET /fixtures?live=all` | Whole live board (use sparingly) |
| Live data | `GET /fixtures?ids=ID1-ID2-…` | **Batch up to 20 fixtures in one call** — the main lever |
| Live data | `GET /standings` | 12 group tables: points, GD, form (feeds advancement calc) |
| Live data | `GET /fixtures/rounds` | Round-by-round schedule |
| Predictor | `GET /predictions?fixture=ID` | Baseline: predicted winner, score, W/D/L probabilities |
| Tactics | `GET /fixtures?id=ID` | Embedded events, lineups, statistics for one match |
| Tactics | `GET /fixtures/players?fixture=ID` | **Per-match player ratings (0–10)** → player-of-match |
| Tactics | `GET /coachs?team=ID` | Coach/manager context |
| Tactics | `GET /fixtures/headtohead?h2h=A-B` | Head-to-head history |
| Sentiment | `GET /injuries?league=1&season=2026` | Structured injuries (prefer over scraped news) |

**Out of scope (deliberately):** `/odds`, `/odds/live`. Easy to wire in, but they reframe the
product from "fan companion" to "betting tool". Do not add them.

## Rate-limit ruleset — design around this, it is a hard constraint

Free tier = **10 requests / minute**, plus a separate daily cap. Every response returns
`x-ratelimit-requests-limit` / `x-ratelimit-requests-remaining` (daily) and the per-minute
`X-RateLimit-Limit` / `X-RateLimit-Remaining` headers — read them on **every** response.

Requirements (MUST unless noted):

1. **One shared rate budget for all four agents.** A single token-bucket / queue layer in the
   backend that every API call passes through (`app/rate_limiter.py`). Two agents must never
   independently decide it's safe to fire. Per-agent `setInterval`-style polling is forbidden.
2. **Batch, don't loop.** Use `/fixtures?ids=ID1-ID2-…` (≤20 IDs) instead of one request per match.
   This is the single biggest lever on the free tier.
3. **Poll live data less aggressively than the API updates.** API-Football refreshes live fixtures
   every 15s; poll every **30–60s**, and **only for matches a followed team is in** — not the full board.
4. **Cache aggressively for non-live data.** Teams, players, standings, coaches, coverage → cache
   minutes-to-hours, not seconds. No fresh call per digest generation.
5. **Back off *before* 429.** If per-minute `X-RateLimit-Remaining` is low, delay non-urgent calls
   (tactics, sentiment) and protect the budget for live scores.
6. **Retry 429 with exponential backoff** (SHOULD: jitter), never a tight retry loop — a 429 means
   you're already over budget and hammering risks an IP/key-level block.
7. **Stay on a stable IP.** Persistent service, not shared-IP serverless (see
   [architecture.md](architecture.md) → deploy model).

If the free tier becomes the *actual* bottleneck once live (not before), the Pro plan moves to
300 req/min — treat as a fallback, not a Phase-0 decision.

## Fallback sources

`openfootball/worldcup.json` and `football-data.org` are read-only fallbacks if API-Football
rate limits bite. Confirmed API-Football fields to rely on: `team.logo`, `player.photo`,
per-match player ratings via `/fixtures/players`, group standings via `/standings`.

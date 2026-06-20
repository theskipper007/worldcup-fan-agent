# Data model (SQLite)

The canonical DDL lives in [`../app/db/schema.sql`](../app/db/schema.sql); this document explains
intent and ownership. SQLAlchemy models in `app/db/models.py` mirror the same shape. Written to
migrate cleanly to Postgres later (no SQLite-only types; ISO-8601 text timestamps).

## Tables

### `matches` — written by the **live data agent**
One row per fixture for `league=1, season=2026`.

| Column | Type | Notes |
|---|---|---|
| `fixture_id` | INTEGER PK | API-Football fixture id |
| `round` | TEXT | e.g. "Group A - 1", "Round of 32" |
| `kickoff_utc` | TEXT | ISO-8601 UTC |
| `home_team_id` / `away_team_id` | INTEGER | |
| `home_team` / `away_team` | TEXT | display names |
| `status` | TEXT | NS / 1H / HT / 2H / FT / … |
| `home_goals` / `away_goals` | INTEGER NULL | null until played |
| `updated_at` | TEXT | last refresh |

### `predictions` — written by the **predictor agent** (eval source of truth)
One row per fixture. Holds **both** the API-Football baseline and the agent's layered prediction,
plus the actual result, so accuracy can be computed for each independently (see [eval.md](eval.md)).

| Column | Type | Notes |
|---|---|---|
| `fixture_id` | INTEGER PK→matches | |
| `predicted_at` | TEXT | when prediction was made (must be pre-kickoff) |
| `baseline_winner` | TEXT | from `/predictions` (`home`/`draw`/`away`) |
| `baseline_home_score` / `baseline_away_score` | INTEGER NULL | baseline scoreline |
| `baseline_prob_home/draw/away` | REAL | baseline probabilities |
| `agent_winner` | TEXT | agent's call after reasoning layer |
| `agent_home_score` / `agent_away_score` | INTEGER NULL | agent scoreline |
| `agent_rationale` | TEXT | short reasoning (cites the inputs used) |
| `actual_winner` | TEXT NULL | filled after FT |
| `actual_home_score` / `actual_away_score` | INTEGER NULL | filled after FT |
| `baseline_correct` / `agent_correct` | INTEGER NULL | 1/0, winner hit, computed at settle |

### `tactical_reports` — written by the **tactics agent**
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `fixture_id` | INTEGER→matches | |
| `formation_home` / `formation_away` | TEXT | from `/fixtures?id=ID` lineups |
| `possession_home` / `possession_away` | INTEGER NULL | percent |
| `shots_home` / `shots_away` | INTEGER NULL | |
| `player_of_match_id` | INTEGER NULL | highest `/fixtures/players` rating, **not** eyeballed |
| `player_of_match_rating` | REAL NULL | 0–10 |
| `narrative` | TEXT | every claim traces to a pulled stat |
| `stat_sources` | TEXT | JSON list of endpoints the numbers came from (audit trail) |
| `created_at` | TEXT | |

### `digests` — written by the **digest generator**
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `digest_date` | TEXT | the matchday being summarized |
| `followed_teams` | TEXT | JSON list of team ids |
| `language` | TEXT | `en` / `ta` / `zh` / `ar` |
| `body` | TEXT | the ~90-second summary |
| `created_at` | TEXT | |

## Ownership rule

Each table has exactly one writer agent (above). The digest generator and the Streamlit UI are
**readers** of `matches` / `predictions` / `tactical_reports` and the **writer** of `digests`.

-- World Cup Fan Agent — canonical SQLite schema.
-- Mirrors ../../docs/data-model.md. Kept Postgres-portable: no SQLite-only types,
-- ISO-8601 text timestamps. One writer agent per table (see docs/agents.md).

-- Written by the live data agent.
CREATE TABLE IF NOT EXISTS matches (
    fixture_id    INTEGER PRIMARY KEY,
    round         TEXT,
    kickoff_utc   TEXT,
    home_team_id  INTEGER,
    away_team_id  INTEGER,
    home_team     TEXT,
    away_team     TEXT,
    status        TEXT,
    home_goals    INTEGER,
    away_goals    INTEGER,
    updated_at    TEXT
);

-- Written by the predictor agent. Holds baseline AND agent prediction AND actual result,
-- so each accuracy can be computed independently (see docs/eval.md).
CREATE TABLE IF NOT EXISTS predictions (
    fixture_id           INTEGER PRIMARY KEY REFERENCES matches(fixture_id),
    predicted_at         TEXT,            -- must be pre-kickoff
    baseline_winner      TEXT,            -- home | draw | away
    baseline_home_score  INTEGER,
    baseline_away_score  INTEGER,
    baseline_prob_home   REAL,
    baseline_prob_draw   REAL,
    baseline_prob_away   REAL,
    agent_winner         TEXT,
    agent_home_score     INTEGER,
    agent_away_score     INTEGER,
    agent_rationale      TEXT,
    actual_winner        TEXT,
    actual_home_score    INTEGER,
    actual_away_score    INTEGER,
    baseline_correct     INTEGER,         -- 1/0, computed at settle
    agent_correct        INTEGER          -- 1/0, computed at settle
);

-- Written by the tactics agent. Every numeric claim traces to a pulled stat (stat_sources).
CREATE TABLE IF NOT EXISTS tactical_reports (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id               INTEGER REFERENCES matches(fixture_id),
    formation_home           TEXT,
    formation_away           TEXT,
    possession_home          INTEGER,
    possession_away          INTEGER,
    shots_home               INTEGER,
    shots_away               INTEGER,
    player_of_match_id       INTEGER,     -- highest /fixtures/players rating, not eyeballed
    player_of_match_rating   REAL,        -- 0–10
    narrative                TEXT,
    stat_sources             TEXT,        -- JSON list of endpoints (audit trail)
    created_at               TEXT
);

-- Written by the digest generator (reads matches/predictions/tactical_reports).
CREATE TABLE IF NOT EXISTS digests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_date     TEXT,
    followed_teams  TEXT,                 -- JSON list of team ids
    language        TEXT,                 -- en | ta | zh | ar
    body            TEXT,
    created_at      TEXT
);

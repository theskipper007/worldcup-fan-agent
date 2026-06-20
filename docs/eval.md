# Predictor scoreboard (public eval)

The scoreboard is the project's credibility artifact. It logs how well the agent predicts versus
the API-Football baseline — honestly, including losses.

## The core idea

API-Football's `/predictions` endpoint already ships a prediction (winner, score, W/D/L
probabilities). **Don't try to beat it from a cold start.** Pull it as the **baseline**, layer the
predictor agent's reasoning (sentiment, injuries, tactical context) on top, and log **both**
accuracies separately. The headline metric is comparative:

> "Our agent beats the baseline by **X points** of winner accuracy"

— a far stronger eval artifact than a bare accuracy number with nothing to compare against.

## Logging discipline (start NOW, before launch)

- Write a `predictions` row **before kickoff** for every followed upcoming match (`predicted_at`
  must be pre-kickoff — this is what makes the log credible).
- After FT, the predictor's settle pass fills `actual_*` and computes `baseline_correct` /
  `agent_correct`. Never overwrite a settled row.
- **Log every prediction, including the wrong ones.** Suppressing misses destroys the scoreboard's
  entire reason to exist.
- Start logging from day 1 so there's a real track record by the public launch (timed to the
  Round of 32, June 28).

## Metrics

| Metric | Definition |
|---|---|
| **Winner hit-rate (baseline)** | `mean(baseline_correct)` over settled rows |
| **Winner hit-rate (agent)** | `mean(agent_correct)` over settled rows |
| **Lift** | agent hit-rate − baseline hit-rate (the headline) |
| **Exact scoreline (baseline / agent)** | share where predicted home+away goals both match actual |
| **Brier score** (optional) | calibration of the probability outputs |

Slice by stage (group vs knockout) once there's enough volume.

## Surfacing

The Streamlit UI exposes a **public scoreboard** view: the two hit-rates side by side, the lift,
a recent-predictions table (prediction, actual, hit/miss for both baseline and agent), and the
sample size. All sourced from the `predictions` table — no recomputation hidden from the user.

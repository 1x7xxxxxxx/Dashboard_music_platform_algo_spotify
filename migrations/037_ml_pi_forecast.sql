-- 037 — Add `pi_forecast_7d` to ml_song_predictions.
-- The Popularity Index regressor (machine_learning/train.py, v2_noscaler) is now
-- wired into ml_inference.score_song. It predicts the Spotify Popularity Index
-- (0-100) from raw 28-day volume + followers + age (R²=0.937, MAE=1.9 PI points).
-- PI is the gate of every algorithm (RR/Radio/DW thresholds rise with PI), so the
-- forecast drives the "Road to Algorithms" diagnostic. Idempotent: safe to re-run.
ALTER TABLE ml_song_predictions
    ADD COLUMN IF NOT EXISTS pi_forecast_7d INTEGER;

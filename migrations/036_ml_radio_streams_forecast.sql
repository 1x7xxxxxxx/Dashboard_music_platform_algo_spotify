-- 036 — Add `radio_streams_forecast_7d` to ml_song_predictions.
-- The Radio volume regressor (MLflow exp 6) is now wired into ml_inference.score_song,
-- mirroring the existing dw_/rr_streams_forecast_7d columns. The forecast is a
-- conservative FLOOR (the regressor under-predicts viral hits, R²=0.63) — see
-- algo_knowledge.ALGO_REGRESSOR_METRICS["RADIO"]. Idempotent: safe to re-run.
ALTER TABLE ml_song_predictions
    ADD COLUMN IF NOT EXISTS radio_streams_forecast_7d INTEGER;

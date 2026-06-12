-- 060_ml_outcome_labeling.sql
-- ML outcome-labelling loop (roadmap ML #2): turn daily predictions into training labels.
--
-- ml_song_predictions logs P(DW/RR/Radio) per song per day, but the model is never
-- told whether it was RIGHT. To accumulate live training labels we need the realized
-- DW/RR/Radio 28-day streams observed AFTER the prediction. S4A exposes no source
-- split via API/CSV (ADR-004) -> captured by manual entry, exactly like
-- s4a_song_nonalgo_streams (migration 052).
--
-- Two tables:
--   1. s4a_song_algo_outcomes  -- manual capture of realized DW/RR/Radio 28d streams
--      per song (dated snapshot, latest recorded_at wins). Written by the Saisie S4A view.
--   2. ml_prediction_outcomes  -- training-ready labelled pairs: each prediction joined
--      to the outcome observed >= horizon days later, binned to 0/1 with the SAME
--      thresholds as training (DW>137, RR>130, Radio>639; machine_learning/train.py:45).
--      Written by the ml_outcome_labeling DAG.
-- Idempotent.

-- 1. Manual capture of realized algorithmic-playlist 28-day streams per song.
CREATE TABLE IF NOT EXISTS s4a_song_algo_outcomes (
    artist_id          INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    song               TEXT    NOT NULL,
    dw_streams_28d     INTEGER NOT NULL DEFAULT 0,
    rr_streams_28d     INTEGER NOT NULL DEFAULT 0,
    radio_streams_28d  INTEGER NOT NULL DEFAULT 0,
    collected_at       TIMESTAMPTZ DEFAULT now(),
    recorded_at        DATE    NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (artist_id, song, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_s4a_algo_outcomes_artist_song
    ON s4a_song_algo_outcomes (artist_id, song);

-- 2. Training-ready labelled pairs (prediction <-> realized outcome).
CREATE TABLE IF NOT EXISTS ml_prediction_outcomes (
    id                 SERIAL PRIMARY KEY,
    prediction_id      INTEGER NOT NULL REFERENCES ml_song_predictions(id) ON DELETE CASCADE,
    artist_id          INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    song               VARCHAR(255) NOT NULL,
    prediction_date    DATE NOT NULL,
    observed_at        DATE NOT NULL,            -- recorded_at of the outcome snapshot used
    horizon_days       INTEGER NOT NULL,         -- observed_at - prediction_date
    dw_streams_28d     INTEGER NOT NULL DEFAULT 0,
    rr_streams_28d     INTEGER NOT NULL DEFAULT 0,
    radio_streams_28d  INTEGER NOT NULL DEFAULT 0,
    y_dw               SMALLINT NOT NULL,         -- realized DW 28d > 137
    y_rr               SMALLINT NOT NULL,         -- realized RR 28d > 130
    y_radio            SMALLINT NOT NULL,         -- realized Radio 28d > 639
    model_version      VARCHAR(50) NOT NULL,
    labeled_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_ml_prediction_outcome UNIQUE (prediction_id)
);

CREATE INDEX IF NOT EXISTS idx_ml_outcomes_artist
    ON ml_prediction_outcomes (artist_id);
CREATE INDEX IF NOT EXISTS idx_ml_outcomes_model
    ON ml_prediction_outcomes (model_version);

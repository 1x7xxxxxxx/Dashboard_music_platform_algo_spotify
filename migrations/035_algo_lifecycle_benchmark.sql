-- Migration 035: algo_lifecycle_benchmark — GLOBAL cohort lifecycle curves.
--
-- Stores, per algorithm (DW / RR / Radio) and per song-age-in-weeks bin, the
-- distribution (quartiles) of the standardization ratio = a song's algo streams
-- divided by the mean of its weight category (follower decile for DW/RR,
-- popularity bucket for Radio). 1.0 = on par with its category; >1.0 over-
-- performs; <1.0 under-performs. Powers the "Cycle de vie & Benchmark" tab.
--
-- This table is GLOBAL (no artist_id) and READ-ONLY at runtime — it is therefore
-- intentionally NOT registered in _ALLOWED_TABLES (which only guards upsert/insert
-- writes). DDL mirrors src/database/benchmark_schema.py.
--
-- The seed below is PROVISIONAL: it encodes the qualitative lifecycle shapes
-- documented in the user's notes (machine_learning/) — Radio long-tail
-- (valley wk5-10 / resurrection wk25-100+), Release Radar cliff after wk5-6,
-- Discover Weekly no-expiration with high tails at any age. `total_stream_median`
-- is left NULL so the live overlay stays honest (age marker only, no fabricated
-- position). Replace this INSERT with the real output of
-- `python machine_learning/export_lifecycle_benchmark.py data_anon.csv` (same
-- dataset_version 'v1' → ON CONFLICT overwrites) once the dataset is available.

CREATE TABLE IF NOT EXISTS algo_lifecycle_benchmark (
    id                   SERIAL PRIMARY KEY,
    algorithm            TEXT NOT NULL,
    weight_category_type TEXT NOT NULL,
    age_week_bin         TEXT NOT NULL,
    age_week_bin_order   SMALLINT NOT NULL,
    ratio_min            DOUBLE PRECISION,
    ratio_q1             DOUBLE PRECISION,
    ratio_median         DOUBLE PRECISION,
    ratio_q3             DOUBLE PRECISION,
    ratio_max            DOUBLE PRECISION,
    total_stream_median  DOUBLE PRECISION,
    sample_count         INTEGER NOT NULL,
    dataset_version      TEXT NOT NULL DEFAULT 'v1',
    exported_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (algorithm, age_week_bin, dataset_version)
);

CREATE INDEX IF NOT EXISTS idx_algo_lifecycle_lookup
    ON algo_lifecycle_benchmark (dataset_version, algorithm, age_week_bin_order);

INSERT INTO algo_lifecycle_benchmark
    (algorithm, weight_category_type, age_week_bin, age_week_bin_order,
     ratio_min, ratio_q1, ratio_median, ratio_q3, ratio_max,
     total_stream_median, sample_count, dataset_version) VALUES
    -- Radio — long tail: high at launch, valley of death (wk5-10), resurrection (wk25+)
    ('RADIO', 'popularity_bucket', '0-5',   1, 0.10, 0.45, 0.75, 1.30, 3.5, NULL, 1200, 'v1'),
    ('RADIO', 'popularity_bucket', '5-10',  2, 0.02, 0.10, 0.22, 0.55, 2.0, NULL, 1100, 'v1'),
    ('RADIO', 'popularity_bucket', '10-25', 3, 0.03, 0.20, 0.45, 0.95, 2.8, NULL, 1500, 'v1'),
    ('RADIO', 'popularity_bucket', '25-50', 4, 0.05, 0.40, 0.80, 1.50, 3.5, NULL, 1400, 'v1'),
    ('RADIO', 'popularity_bucket', '50-100',5, 0.08, 0.55, 1.05, 2.00, 4.0, NULL, 1300, 'v1'),
    ('RADIO', 'popularity_bucket', '100+',  6, 0.10, 0.60, 1.10, 2.20, 4.2, NULL,  900, 'v1'),
    -- Release Radar — explosion wk0-5, then cliff to ~0 forever after wk5-6
    ('RR', 'follower_decile', '0-5',   1, 0.30, 1.20, 3.00, 6.50, 20.0, NULL, 1300, 'v1'),
    ('RR', 'follower_decile', '5-10',  2, 0.00, 0.05, 0.15, 0.40,  1.5, NULL, 1200, 'v1'),
    ('RR', 'follower_decile', '10-25', 3, 0.00, 0.02, 0.08, 0.20,  0.9, NULL, 1500, 'v1'),
    ('RR', 'follower_decile', '25-50', 4, 0.00, 0.01, 0.05, 0.15,  0.7, NULL, 1400, 'v1'),
    ('RR', 'follower_decile', '50-100',5, 0.00, 0.01, 0.04, 0.12,  0.6, NULL, 1200, 'v1'),
    ('RR', 'follower_decile', '100+',  6, 0.00, 0.00, 0.03, 0.10,  0.5, NULL,  800, 'v1'),
    -- Discover Weekly — no expiration: median below 1.0 (engagement gate), high tails at any age
    ('DW', 'follower_decile', '0-5',   1, 0.02, 0.25, 0.60, 1.40, 15.0, NULL, 1300, 'v1'),
    ('DW', 'follower_decile', '5-10',  2, 0.02, 0.20, 0.50, 1.20, 14.0, NULL, 1200, 'v1'),
    ('DW', 'follower_decile', '10-25', 3, 0.02, 0.18, 0.48, 1.15, 16.0, NULL, 1500, 'v1'),
    ('DW', 'follower_decile', '25-50', 4, 0.01, 0.15, 0.45, 1.10, 18.0, NULL, 1400, 'v1'),
    ('DW', 'follower_decile', '50-100',5, 0.01, 0.15, 0.42, 1.05, 20.0, NULL, 1100, 'v1'),
    ('DW', 'follower_decile', '100+',  6, 0.01, 0.12, 0.40, 1.00, 20.0, NULL,  700, 'v1')
ON CONFLICT (algorithm, age_week_bin, dataset_version) DO UPDATE SET
    weight_category_type = EXCLUDED.weight_category_type,
    age_week_bin_order   = EXCLUDED.age_week_bin_order,
    ratio_min            = EXCLUDED.ratio_min,
    ratio_q1             = EXCLUDED.ratio_q1,
    ratio_median         = EXCLUDED.ratio_median,
    ratio_q3             = EXCLUDED.ratio_q3,
    ratio_max            = EXCLUDED.ratio_max,
    total_stream_median  = EXCLUDED.total_stream_median,
    sample_count         = EXCLUDED.sample_count,
    exported_at          = CURRENT_TIMESTAMP;

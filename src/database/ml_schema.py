"""Schéma PostgreSQL pour les prédictions ML (scoring quotidien)."""

ML_SCHEMA = {
    'ml_song_predictions': """
        CREATE TABLE IF NOT EXISTS ml_song_predictions (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            song VARCHAR(255) NOT NULL,
            prediction_date DATE NOT NULL DEFAULT CURRENT_DATE,
            days_since_release INTEGER,
            streams_7d INTEGER,
            streams_28d INTEGER,
            dw_probability FLOAT,
            rr_probability FLOAT,
            radio_probability FLOAT,
            dw_streams_forecast_7d INTEGER,
            rr_streams_forecast_7d INTEGER,
            radio_streams_forecast_7d INTEGER,
            pi_forecast_7d INTEGER,
            model_version VARCHAR(50) DEFAULT 'v1',
            features_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_ml_prediction UNIQUE(artist_id, song, prediction_date, model_version)
        );

        CREATE INDEX IF NOT EXISTS idx_ml_predictions_artist
        ON ml_song_predictions(artist_id);

        CREATE INDEX IF NOT EXISTS idx_ml_predictions_song_date
        ON ml_song_predictions(artist_id, song, prediction_date DESC);

        CREATE INDEX IF NOT EXISTS idx_ml_predictions_date
        ON ml_song_predictions(prediction_date DESC);
    """,
    'ml_prediction_outcomes': """
        CREATE TABLE IF NOT EXISTS ml_prediction_outcomes (
            id SERIAL PRIMARY KEY,
            prediction_id INTEGER NOT NULL REFERENCES ml_song_predictions(id) ON DELETE CASCADE,
            artist_id INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
            song VARCHAR(255) NOT NULL,
            prediction_date DATE NOT NULL,
            observed_at DATE NOT NULL,
            horizon_days INTEGER NOT NULL,
            dw_streams_28d INTEGER NOT NULL DEFAULT 0,
            rr_streams_28d INTEGER NOT NULL DEFAULT 0,
            radio_streams_28d INTEGER NOT NULL DEFAULT 0,
            y_dw SMALLINT NOT NULL,
            y_rr SMALLINT NOT NULL,
            y_radio SMALLINT NOT NULL,
            model_version VARCHAR(50) NOT NULL,
            labeled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_ml_prediction_outcome UNIQUE(prediction_id)
        );

        CREATE INDEX IF NOT EXISTS idx_ml_outcomes_artist
        ON ml_prediction_outcomes(artist_id);

        CREATE INDEX IF NOT EXISTS idx_ml_outcomes_model
        ON ml_prediction_outcomes(model_version);
    """
}

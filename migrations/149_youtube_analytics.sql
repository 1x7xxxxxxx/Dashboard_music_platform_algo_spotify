-- 149 — YouTube Analytics : trois mesures que la Data API ne rend pas (R511, R394).
--
-- La Data API v3 (clé d'API, lecture publique) rend un `subscriberCount` arrondi à trois
-- chiffres significatifs, aucune durée de visionnage, aucune source de trafic. La YouTube
-- Analytics API les rend, mais exige l'OAuth du PROPRIÉTAIRE de la chaîne : un
-- `refresh_token` par locataire, chiffré dans `artist_credentials` (platform
-- 'youtube_analytics'), minté par tools/youtube_analytics_authorize.py.
--
-- Additive only (CREATE TABLE IF NOT EXISTS) — idempotent, safe to replay.
--
-- Trois tables, une par forme de rapport :
--   * video_window  — UN rapport `dimensions=video` sur une fenêtre (28 jours finissant
--     3 jours avant la collecte : Analytics consolide avec ~2-3 jours de retard). Un
--     instantané par fenêtre, pas une boucle par vidéo : une requête au lieu de N.
--   * channel_daily — `dimensions=day` : vues, minutes vues, abonnés gagnés/perdus EXACTS.
--   * traffic_daily — `dimensions=day,insightTrafficSourceType`.
-- Le locataire est dans chaque clé primaire ; un upsert ne réécrit jamais `artist_id`.

CREATE TABLE IF NOT EXISTS youtube_analytics_video_window (
    artist_id          INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    video_id           VARCHAR(64) NOT NULL,
    window_end         DATE NOT NULL,
    window_days        SMALLINT NOT NULL,
    views              BIGINT,
    minutes_watched    BIGINT,
    subscribers_gained INTEGER,
    subscribers_lost   INTEGER,
    collected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (artist_id, video_id, window_end, window_days)
);

CREATE TABLE IF NOT EXISTS youtube_analytics_channel_daily (
    artist_id          INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    day                DATE NOT NULL,
    views              BIGINT,
    minutes_watched    BIGINT,
    subscribers_gained INTEGER,
    subscribers_lost   INTEGER,
    collected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (artist_id, day)
);

CREATE TABLE IF NOT EXISTS youtube_analytics_traffic_daily (
    artist_id       INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    day             DATE NOT NULL,
    source_type     VARCHAR(64) NOT NULL,
    views           BIGINT,
    minutes_watched BIGINT,
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (artist_id, day, source_type)
);

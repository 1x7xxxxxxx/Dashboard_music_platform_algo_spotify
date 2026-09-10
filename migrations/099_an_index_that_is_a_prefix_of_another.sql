-- 099 — Retirer les index dont un autre index fait déjà le travail.
--
-- CE QUI A ÉTÉ MESURÉ (production, 2026-09-10)
-- --------------------------------------------
-- 385 index, 28 Mo. 232 n'ont JAMAIS été parcourus — et le compteur fonctionne :
-- l'index le plus lu affiche 59 418 parcours, et `pg_stat_database.stats_reset` est
-- vide, donc ces zéros couvrent toute la vie de la base, pas une fenêtre récente.
--
-- 232 « jamais lus » n'est PAS 232 à supprimer : 107 d'entre eux servent une clé
-- primaire ou une contrainte d'unicité. Ceux-là ne sont pas là pour accélérer une
-- lecture, ils sont là pour rendre un doublon impossible — les compter comme du
-- poids mort, c'est proposer de retirer une contrainte d'intégrité au motif que
-- personne ne l'a interrogée. Ce dépôt a déjà payé trois fois le prix d'une clé de
-- conflit manquante.
--
-- CE QUE CETTE MIGRATION RETIRE, ET SUR QUELLE PREUVE
-- ---------------------------------------------------
-- Uniquement la classe DÉMONTRABLE : un index non unique, non partiel, jamais
-- parcouru, dont la liste de colonnes est un PRÉFIXE STRICT de celle d'un autre
-- index de la même table. Le planificateur peut toujours utiliser l'index le plus
-- large là où le plus étroit conviendrait ; le plus étroit n'apporte donc rien qu'un
-- coût de maintenance à chaque écriture nocturne. Ce n'est pas une opinion sur
-- l'usage, c'est une propriété des colonnes.
--
-- 15 index. Le gain n'est pas l'espace (~250 Ko) : c'est le travail d'écriture retiré
-- de chaque upsert de la nuit, sur des tables que les DAGs réécrivent intégralement.
--
-- CE QU'ELLE NE RETIRE PAS
-- ------------------------
-- Les 110 autres « jamais lus mais pas redondants » — dont les deux plus lourds,
-- `idx_s4a_timeline_song_date` (1,7 Mo) et `idx_soundcloud_daily_date` (1,3 Mo).
-- Aucune propriété ne prouve qu'ils sont inutiles : seule leur absence d'usage
-- passé le suggère, et une requête d'admin rare suffirait à les justifier.
-- `make index-report` les liste avec leur poids et le DDL pour les recréer ; la
-- décision est humaine, pas automatique.
--
-- Réversible : chaque `DROP INDEX` ci-dessous a son `CREATE` en commentaire.

-- apple_songs_history — couvert par uq_apple_history_artist_song_date
DROP INDEX IF EXISTS idx_apple_history_artist;
-- CREATE INDEX idx_apple_history_artist ON apple_songs_history (artist_id);

-- artist_credentials — couvert par artist_credentials_artist_id_platform_key
DROP INDEX IF EXISTS idx_artist_credentials_artist;
-- CREATE INDEX idx_artist_credentials_artist ON artist_credentials (artist_id);

-- artist_wrapped — couvert par idx_artist_wrapped_year
DROP INDEX IF EXISTS idx_artist_wrapped_artist;
-- CREATE INDEX idx_artist_wrapped_artist ON artist_wrapped (artist_id);

-- campaign_track_mapping — couvert par campaign_track_mapping_artist_campaign_track_key
DROP INDEX IF EXISTS idx_ctm_artist_id;
-- CREATE INDEX idx_ctm_artist_id ON campaign_track_mapping (artist_id);

-- distrokid_monthly_revenue — couvert par idx_distrokid_revenue_artist_period
DROP INDEX IF EXISTS idx_distrokid_revenue_artist;
-- CREATE INDEX idx_distrokid_revenue_artist ON distrokid_monthly_revenue (artist_id);

-- distrokid_sales_detail — couvert par idx_distrokid_sales_period
DROP INDEX IF EXISTS idx_distrokid_sales_artist;
-- CREATE INDEX idx_distrokid_sales_artist ON distrokid_sales_detail (artist_id);

-- imusician_monthly_revenue — couvert par idx_imusician_revenue_artist_period
DROP INDEX IF EXISTS idx_imusician_revenue_artist;
-- CREATE INDEX idx_imusician_revenue_artist ON imusician_monthly_revenue (artist_id);

-- meta_insights — couvert par idx_meta_insights_ad_date
DROP INDEX IF EXISTS idx_meta_insights_ad;
-- CREATE INDEX idx_meta_insights_ad ON meta_insights (ad_id);

-- s4a_song_algo_outcomes — couvert par s4a_song_algo_outcomes_pkey
DROP INDEX IF EXISTS idx_s4a_algo_outcomes_artist_song;
-- CREATE INDEX idx_s4a_algo_outcomes_artist_song ON s4a_song_algo_outcomes (artist_id, song);

-- s4a_song_discovery_mode — couvert par s4a_song_discovery_mode_pkey
DROP INDEX IF EXISTS idx_s4a_discovery_mode_artist_song;
-- CREATE INDEX idx_s4a_discovery_mode_artist_song ON s4a_song_discovery_mode (artist_id, song);

-- s4a_song_nonalgo_streams — couvert par s4a_song_nonalgo_streams_pkey
DROP INDEX IF EXISTS idx_s4a_nonalgo_streams_artist_song;
-- CREATE INDEX idx_s4a_nonalgo_streams_artist_song ON s4a_song_nonalgo_streams (artist_id, song);

-- s4a_song_playlist_adds — couvert par idx_s4a_playlist_adds_artist_song
DROP INDEX IF EXISTS idx_s4a_song_playlist_adds_artist_song;
-- CREATE INDEX idx_s4a_song_playlist_adds_artist_song ON s4a_song_playlist_adds (artist_id, song);

-- s4a_song_playlists — couvert par s4a_song_playlists_artist_id_song_title_key
DROP INDEX IF EXISTS idx_s4a_playlists_artist_song;
-- CREATE INDEX idx_s4a_playlists_artist_song ON s4a_song_playlists (artist_id, song);

-- sacem_statement — couvert par sacem_statement_artist_id_line_date_libelle_mouvement_eur_s_key
DROP INDEX IF EXISTS idx_sacem_statement_artist_date;
-- CREATE INDEX idx_sacem_statement_artist_date ON sacem_statement (artist_id, line_date);

-- track_release_reference — couvert par track_release_reference_artist_id_match_key_key
DROP INDEX IF EXISTS idx_track_release_ref_artist;
-- CREATE INDEX idx_track_release_ref_artist ON track_release_reference (artist_id);

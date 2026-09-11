-- 100 — Deux tables gardaient l'unicité sur l'identifiant de plateforme seul.
--
-- La migration 064 a corrigé cette classe sur `youtube_videos` et
-- `youtube_channels`, après que deux artistes bêta se soient vu voler leurs
-- lignes. Le balayage du 2026-09-11, fait en chiffrant la montée en charge, a
-- trouvé que **deux tables lui avaient échappé** :
--
--     youtube_comments   UNIQUE (comment_id)
--     youtube_playlists  UNIQUE (playlist_id)
--
-- Le mécanisme est celui que 064 décrit. `youtube_daily.py:232` écrit les
-- commentaires avec `conflict_columns=['comment_id']` : un second locataire
-- collectant un commentaire déjà vu n'obtient PAS sa propre ligne — son
-- `ON CONFLICT` tombe sur la ligne du premier et en écrase les compteurs.
-- Aucun vol de propriété ici (`artist_id` n'est pas dans `update_columns`,
-- correctif de 064 appliqué côté code), mais une disparition silencieuse des
-- données du second, et une corruption de celles du premier.
--
-- POURQUOI MAINTENANT, alors que la collecte de commentaires est désactivée
-- (`collect_comments=False`) et que les deux tables comptent **0 ligne en
-- production** : précisément pour cela. À zéro ligne, l'échange de contrainte
-- ne migre aucune donnée. Le jour où ces tables seront peuplées, le même
-- correctif demandera de décider quoi faire des lignes déjà fusionnées entre
-- locataires — et cette décision-là n'a pas de bonne réponse.
--
-- CE QUI N'EST PAS TOUCHÉ, et c'est délibéré :
--   `ml_prediction_outcomes UNIQUE (prediction_id)` ressemble à la même forme
--   et n'en est pas. `prediction_id` référence `ml_song_predictions(id)`, une
--   clé de substitution SERIAL déjà unique globalement : « un résultat par
--   prédiction » est la sémantique voulue. Y ajouter `artist_id` autoriserait
--   deux résultats pour une même prédiction. Le garde
--   `tests/test_uniqueness_names_its_tenant.py` porte cette exemption avec sa
--   raison, pour qu'on ne la « corrige » pas plus tard.
--
-- Les noms d'index suivent ceux de 064 (`uq_<table>_artist_<objet>`), et
-- `init_db.sql` / `src/database/youtube_schema.py` les créent désormais
-- directement : rejouer ce fichier sur une base neuve est un no-op.
--
-- Idempotent : sûr à rejouer (`make migrate` rejoue chaque fichier).

BEGIN;

-- ── youtube_comments ────────────────────────────────────────────────────────
ALTER TABLE youtube_comments DROP CONSTRAINT IF EXISTS unique_comment_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_comments_artist_comment
    ON youtube_comments (artist_id, comment_id);

-- ── youtube_playlists ───────────────────────────────────────────────────────
ALTER TABLE youtube_playlists DROP CONSTRAINT IF EXISTS unique_playlist_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_playlists_artist_playlist
    ON youtube_playlists (artist_id, playlist_id);

COMMIT;

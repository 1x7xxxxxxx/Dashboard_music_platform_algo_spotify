-- ═══════════════════════════════════════════════════════════════════════════
-- 120 — Les abonnés, et de QUELLE horloge ils viennent
-- ═══════════════════════════════════════════════════════════════════════════
-- Deux sources donnent le nombre d'abonnés Spotify, et elles ne s'arrêtent pas au
-- même moment — mesuré le 2026-09-14 :
--
--   • le CSV S4A  : 889 jours d'historique, **figé au 2026-06-07** (import épisodique)
--   • l'API Spotify : `artist_history`, **jusqu'au 2026-09-13** (DAG quotidien)
--
-- Les fusionner en une seule série ferait passer un CHANGEMENT DE SOURCE pour une
-- inflexion de la courbe. `source` est donc une DIMENSION : elle va en légende,
-- jamais dans une somme. C'est la même règle qu'ADR-021 pose pour les horloges qui
-- produisent une date.
--
-- CE QUE CETTE VUE RÉPARE AU PASSAGE
-- -----------------------------------
-- `artist_history` n'a **ni contrainte d'unicité ni colonne `date`** : 170 lignes
-- pour 44 jours distincts chez le locataire 1 (doublons intra-jour hérités ; 1/j
-- depuis le 2026-09-10). Lu tel quel, un GROUP BY par jour compterait plusieurs fois
-- le même relevé. La règle « un relevé par jour, le DERNIER » descend donc ICI, en
-- SQL — exactement ce que `v_soundcloud_track_latest` a fait pour SoundCloud
-- (migration 107).
--
-- Cela ferme le défaut côté LECTURE, pas côté écriture : poser
-- `UNIQUE (artist_id, (collected_at::date))` demande un dédoublonnage préalable ET
-- une modification du collecteur — autre rayon d'explosion, autre tâche. La vue
-- protège toutes les surfaces en attendant, et continuera de les protéger après.
--
-- LE PONT DE LOCATAIRE, QUI N'EST PAS ÉVIDENT
-- --------------------------------------------
-- `artist_history.artist_id` est l'identifiant **SPOTIFY** (VARCHAR), pas le
-- locataire SaaS (INTEGER). C'est le piège que `.claude/rules/python.md` nomme :
-- on raisonne sur le TYPE, jamais sur le nom. `saas_artists.spotify_artist_id`
-- (migration 039) est le seul pont. Idempotent.

CREATE OR REPLACE VIEW v_spotify_followers_daily AS
    -- L'HISTORIQUE : le CSV S4A. Profond, et figé à la dernière campagne d'import.
    SELECT artist_id,
           day,
           followers_level AS followers,
           's4a_csv'::text AS source
      FROM v_s4a_audience_daily
     WHERE followers_level IS NOT NULL
       AND followers_level > 0
    UNION ALL
    -- LA FRAÎCHEUR : l'API. Un relevé par jour, le dernier — voir en-tête.
    -- Le DISTINCT ON est ENCAPSULÉ : dans une branche d'UNION, un ORDER BY nu
    -- s'applique à l'union entière et Postgres refuse la construction.
    SELECT * FROM (
        SELECT DISTINCT ON (sa.id, h.collected_at::date)
               sa.id                  AS artist_id,
               h.collected_at::date   AS day,
               h.followers::bigint    AS followers,
               'spotify_api'::text    AS source
          FROM artist_history h
          JOIN saas_artists sa ON sa.spotify_artist_id = h.artist_id
         WHERE h.followers IS NOT NULL
           AND h.followers > 0
         ORDER BY sa.id, h.collected_at::date, h.collected_at DESC
    ) api;

COMMENT ON VIEW v_spotify_followers_daily IS
    'Couche OR (ADR-019) : les abonnés Spotify AVEC LEUR SOURCE. Deux horloges — le '
    'CSV S4A s''arrête au dernier import, l''API court au jour le jour — et les '
    'rabouter ferait passer un changement de source pour une inflexion. `source` est '
    'une DIMENSION : en légende, jamais dans une somme. Le DISTINCT ON ferme côté '
    'lecture l''absence de contrainte d''unicité sur artist_history (170 lignes pour '
    '44 jours) ; le pont de locataire est saas_artists.spotify_artist_id, car '
    'artist_history.artist_id est l''identifiant SPOTIFY et non le locataire.';

-- ═══════════════════════════════════════════════════════════════════════════
-- 130 — L'indice de popularité (PI), au grain de la page Spotify
-- ═══════════════════════════════════════════════════════════════════════════
-- POURQUOI UNE VUE PLUTÔT QU'UNE REQUÊTE DANS LA PAGE
-- ----------------------------------------------------
-- `spotify_s4a_combined` ne lit que des vues or, et un garde le vérifie
-- (`test_the_spotify_page_reads_only_the_gold_layer`). Le PI vit dans
-- `track_popularity_history`, dont la clé est le `track_id` SPOTIFY et le
-- `track_name` de l'API — deux espaces de noms que la page ne connaît pas : elle
-- raisonne en `song`, le titre S4A, celui du NOM DE FICHIER du CSV.
--
-- LE RATTACHEMENT PASSE PAR L'IDENTIFIANT, PAS PAR LE NOM
-- --------------------------------------------------------
-- `track_platform_link` porte, pour la plateforme 'spotify', un `platform_ref_id`
-- qui EST le `track_id` Spotify — mesuré le 2026-09-21 : 11 liens confirmés, tous
-- avec un ref_id. La jointure est donc stricte et sur un identifiant stable, jamais
-- sur un titre : `track_name` porte « ? » et `song` porte « _ », et les rapprocher
-- par le nom est exactement ce qui perdait 59 % des écoutes en migration 119.
--
-- Mesuré le 2026-09-21 sur le locataire 1 :
--     track_popularity_history           582 lignes (dont des titres de référence)
--     après jointure aux liens confirmés 471 lignes, 11 titres, 2025-11-23 → 2026-09-20
--
-- CE QUE LA PAGE Y GAGNE, ET QUI N'ÉTAIT NULLE PART
-- --------------------------------------------------
-- Le PI est relevé par l'API TOUS LES JOURS ; le CSV S4A s'importe au moment d'une
-- sortie et s'arrête. Mesuré le même jour : les écoutes S4A s'arrêtent au
-- 2026-06-07, le PI court jusqu'au 2026-09-20 — **105 jours** où le seul signal
-- vivant du titre est son PI. La courbe de détail par titre montrait un titre qui
-- « s'arrête » ; il ne s'arrêtait pas, il n'était plus importé.
--
-- Le PI est aussi la PORTE de chaque algorithme (ADR / Road to Algo : RR, Radio et
-- Discover Weekly ont chacun leur seuil de PI). Un titre qui bouge avec un PI de 9
-- et un titre qui bouge avec un PI de 45 n'appellent pas la même décision, et rien
-- sur cette page ne permettait de les distinguer.

CREATE OR REPLACE VIEW v_spotify_track_pi_daily AS
    -- MATERIALIZED pour la même raison qu'en migration 119 : les 11 lignes de
    -- correspondance se calculent une fois et se hachent contre le fait, au lieu
    -- d'être appliquées après la jointure à tout l'historique de popularité.
    WITH linked AS MATERIALIZED (
        SELECT sp.artist_id,
               sp.platform_ref_id AS spotify_track_id,
               sp.match_key,
               s4a.platform_title AS song,
               trr.title,
               trr.release_date
          FROM track_platform_link sp
          JOIN track_platform_link s4a
            ON s4a.artist_id = sp.artist_id
           AND s4a.match_key = sp.match_key
           AND s4a.platform  = 's4a'
           AND s4a.status    = 'confirmed'
          JOIN track_release_reference trr
            ON trr.artist_id = sp.artist_id
           AND trr.match_key = sp.match_key
         WHERE sp.platform = 'spotify'
           AND sp.status   = 'confirmed'
           AND sp.platform_ref_id IS NOT NULL
    )
    SELECT p.artist_id,
           k.song,
           k.match_key,
           k.title,
           k.release_date,
           p.date AS day,
           p.popularity::int AS popularity
      FROM track_popularity_history p
      JOIN linked k
        ON k.artist_id        = p.artist_id
       AND k.spotify_track_id = p.track_id;

COMMENT ON VIEW v_spotify_track_pi_daily IS
    'Couche OR (ADR-019) : l''indice de popularité Spotify (0-100) au grain '
    '(locataire, titre S4A, jour). Le rattachement passe par le platform_ref_id du '
    'LIEN CONFIRMÉ track_platform_link — le track_id Spotify, un identifiant stable — '
    'jamais par le nom : track_name porte « ? » et song porte « _ ». Relevé par l''API '
    'tous les jours, il continue là où le CSV S4A s''arrête : 105 jours d''écart '
    'mesurés le 2026-09-21.';

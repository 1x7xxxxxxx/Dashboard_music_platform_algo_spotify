-- ═══════════════════════════════════════════════════════════════════════════
-- 121 — Le niveau d'abonnés Instagram, et la règle qui le définit
-- ═══════════════════════════════════════════════════════════════════════════
-- Dernière lecture de bronze dans la PORTE (`period_side_metrics.py`), et la seule
-- que R108 laissait derrière elle. Son critère de clôture était explicite : « le
-- compte du cliquet du bronze ne change pas quand on retire `period_side_metrics.py`
-- de `_NOT_A_SURFACE` ». Mesuré le 2026-09-14 : le delta valait **3** avant le
-- registre des dimensions, **1** après — cette vue le met à **0**.
--
-- CE QUI EST UNE RÈGLE ICI, ET QUI VIVAIT DANS UNE SOUS-REQUÊTE
-- -------------------------------------------------------------
-- La porte calculait le GAIN d'abonnés sur une période par quatre sous-requêtes
-- imbriquées, et elles portaient deux décisions métier que rien ne nommait :
--
--   1. le niveau d'un JOUR est le `MAX(followers_count)` de ce jour — parce que le
--      collecteur peut relever plusieurs fois, et qu'un niveau ne se somme pas ;
--   2. le gain d'une période est le niveau du DERNIER jour mesuré moins celui du
--      PREMIER — pas « aujourd'hui moins il y a 30 jours », qui suppose une mesure
--      ces jours-là.
--
-- Écrites dans une sous-requête, ces deux règles sont invisibles à tout garde et se
-- recopient à la prochaine surface qui voudra le même chiffre. C'est exactement la
-- forme qu'ADR-019 vise, et le dépôt connaît le prix : trois totaux YouTube
-- incompatibles avant la migration 097.
--
-- `collected_at` est un TIMESTAMP dont le défaut est `CURRENT_DATE` : le grain réel
-- est le jour, et la vue le dit plutôt que de laisser chaque appelant le redécouvrir
-- par un `::date`. `followers_count` est un NIVEAU — MAX, jamais SUM. Idempotent.

CREATE OR REPLACE VIEW v_instagram_followers_daily AS
    SELECT artist_id,
           collected_at::date              AS day,
           MAX(followers_count)::bigint    AS followers,
           MAX(follows_count)::bigint      AS follows,
           MAX(media_count)::bigint        AS media
      FROM instagram_daily_stats
     WHERE artist_id IS NOT NULL
       AND collected_at IS NOT NULL
     GROUP BY artist_id, collected_at::date;

COMMENT ON VIEW v_instagram_followers_daily IS
    'Couche OR (ADR-019) : les niveaux Instagram au grain (locataire, jour). '
    'followers/follows/media sont des NIVEAUX — MAX du jour, jamais SUM : le '
    'collecteur peut relever plusieurs fois par jour, et additionner deux relevés '
    'du même compte n''a aucun sens. Le GAIN d''une période se lit comme le niveau '
    'du dernier jour mesuré moins celui du premier — jamais « aujourd''hui moins '
    'il y a 30 jours », qui suppose une mesure ces jours-là.';

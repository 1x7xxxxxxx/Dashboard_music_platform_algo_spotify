-- 101 — La couche OR s'étend à la dépense Meta.
--
-- ADR-019 : une métrique, une définition. `v_platform_totals` (migration 097) l'a
-- appliqué aux écoutes ; la DÉPENSE n'avait aucune définition unique, et le balayage
-- croisé du 2026-09-11 a compté **dix fichiers** qui l'agrègent eux-mêmes
-- (`_collectors.py`, `meta_creatives.py`, `meta_ads_overview.py`, `kpi_helpers.py`,
-- `_tab_budget_roi.py`, …). C'est la situation exacte qui avait donné trois totaux
-- YouTube incompatibles avant 097.
--
-- Le déclencheur immédiat est plus modeste et plus net : la page Breakdowns doit
-- annoncer QUELLE PART de la dépense sa ventilation couvre — mesuré 2 348 € sur
-- 3 088 €, soit 76 %, parce que Meta n'attribue pas tout à une dimension. Pour le
-- dire, elle a besoin du dénominateur, et le lire dans la table brute lui faisait
-- franchir la frontière du bronze : le cliquet `test_the_bronze_boundary_only_tightens`
-- a compté 125 couples contre un plafond de 124, et il a eu raison.
--
-- Pourquoi une VUE et pas une table : même raison qu'en 097. Ces agrégats sont
-- calculés à la LECTURE ; matérialiser n'en retirerait aucun et créerait un graphe de
-- dépendances qu'ADR-014 a écarté (62 Mo, tout tient en cache, `read=0`).
--
-- `ad_account_id` est dans la clé : un artiste peut avoir plusieurs comptes
-- publicitaires (ADR-013), et une dépense agrégée tous comptes confondus serait
-- fausse dès qu'un filtre de compte est posé. Un appelant qui veut le total de
-- l'artiste somme les lignes ; il ne peut pas se tromper dans l'autre sens.

CREATE OR REPLACE VIEW v_meta_spend_totals AS
    SELECT artist_id,
           ad_account_id,
           COALESCE(SUM(spend), 0)::numeric      AS spend,
           COALESCE(SUM(results), 0)::bigint     AS results,
           COALESCE(SUM(impressions), 0)::bigint AS impressions,
           MIN(day_date)                         AS first_day,
           MAX(day_date)                         AS last_day
      FROM meta_insights_performance_day
     WHERE artist_id IS NOT NULL
     GROUP BY artist_id, ad_account_id;

COMMENT ON VIEW v_meta_spend_totals IS
    'Couche OR (ADR-019) : la dépense Meta, une définition et une seule. '
    'Grain (artist_id, ad_account_id). Toute surface qui affiche une dépense totale '
    'lit ici plutôt que meta_insights_performance_day.';

-- ═══════════════════════════════════════════════════════════════════════════
-- 108 — Meta : la colonne que la vue or avait perdue, et la maille AD SET
-- ═══════════════════════════════════════════════════════════════════════════
-- ⚠️ DÉFAUT VIVANT, mesuré le 2026-09-12 contre la base.
--
-- La migration 106 a fait descendre la jointure `meta_insights × meta_ads` dans
-- `v_meta_creative_daily`. Le repointage a été fait colonne par colonne sur la
-- liste du SELECT — et personne n'a regardé le WHERE. Or trois requêtes de
-- `meta_creatives.py` filtrent sur `ad_account_id`, que la vue ne porte pas :
--
--     ERROR: column "ad_account_id" does not exist
--
-- Ce n'est pas latent. `account_clause()` n'ajoute son fragment que lorsqu'un
-- locataire CHOISIT un compte publicitaire précis — donc la page Créatives tombe
-- pour tout locataire multi-comptes, c'est-à-dire exactement la population
-- qu'ADR-013 est allé chercher. Un locataire mono-compte ne voit jamais rien.
--
-- Et deux autres requêtes du même fichier joignent `meta_ads`, `meta_adsets` et
-- `meta_campaigns`, qui portent TOUTES les trois `ad_account_id`, sous un filtre
-- non qualifié :
--
--     ERROR: column reference "ad_account_id" is ambiguous
--
-- Une vue or n'a qu'une seule colonne de ce nom : lire la vue fait disparaître
-- l'ambiguïté par construction, au lieu de la corriger cinq fois.
--
-- `optimization_goal` entre en même temps : le classement CPR de la page ne
-- l'affiche que pour les objectifs de conversion, et c'est la seule raison pour
-- laquelle cette requête joignait encore `meta_adsets`. Une créative appartient à
-- un ad set et un seul, donc l'ajouter au GROUP BY ne coupe aucune ligne.
-- Les deux colonnes neuves sont AJOUTÉES EN FIN DE LISTE, et ce n'est pas une
-- question de goût : `CREATE OR REPLACE VIEW` refuse de renommer une colonne
-- existante, donc glisser `ad_account_id` en deuxième position obligerait à un
-- `DROP VIEW`. Un DROP sur une vue que quelque chose lit casse ce quelque chose,
-- et la migration ne serait plus rejouable sans risque. L'ordre des colonnes
-- d'une vue n'a aucun lecteur ici : tout le code les nomme.
CREATE OR REPLACE VIEW v_meta_creative_daily AS
    SELECT mi.artist_id,
           ma.ad_name                        AS creative_name,
           mc.campaign_name                  AS campaign_name,
           mi.date::date                     AS day,
           COALESCE(SUM(mi.spend), 0)::numeric       AS spend,
           COALESCE(SUM(mi.impressions), 0)::bigint  AS impressions,
           COALESCE(SUM(mi.clicks), 0)::bigint       AS clicks,
           COALESCE(SUM(mi.reach), 0)::bigint        AS reach,
           COALESCE(SUM(mi.conversions), 0)::bigint  AS conversions,
           AVG(mi.frequency)                         AS frequency,
           AVG(mi.ctr)                               AS ctr,
           ma.ad_account_id                          AS ad_account_id,
           ads.optimization_goal                     AS optimization_goal,
           -- Deux attributs, pas deux mesures : constants dans le groupe, ils sont
           -- là pour que le classement CPR de la page cesse de rejoindre
           -- `meta_campaigns` et `meta_ads` rien que pour les lire.
           MAX(mc.start_time)                        AS campaign_start,
           MAX(ma.created_time)                      AS creative_created,
           -- ⚠️ UNE MOYENNE NE SE RÉ-AGRÈGE PAS. `ctr` ci-dessus est la moyenne
           -- du JOUR ; en refaire la moyenne sur plusieurs jours ne donne pas la
           -- moyenne des lignes, parce qu'un nom de créative couvre plusieurs
           -- `ad_id` et que leur nombre varie d'un jour à l'autre — 274 couples
           -- (créative, jour) sont dans ce cas, mesurés le 2026-09-12.
           --
           -- La vue expose donc la SOMME et le COMPTE : le lecteur qui veut la
           -- moyenne sur une période fait `SUM(ctr_sum) / SUM(ctr_n)` et obtient
           -- exactement le nombre qu'une lecture des lignes brutes donnerait.
           -- C'est la seule façon de descendre ce grain sans déplacer un chiffre
           -- affiché.
           SUM(mi.ctr)                               AS ctr_sum,
           COUNT(mi.ctr)                             AS ctr_n,
           SUM(mi.frequency)                         AS frequency_sum,
           COUNT(mi.frequency)                       AS frequency_n
      FROM meta_insights mi
      JOIN meta_ads ma ON ma.ad_id = mi.ad_id AND ma.artist_id = mi.artist_id
      -- LEFT : une créative dont la campagne a disparu du catalogue Meta reste une
      -- créative, et ses dépenses restent dépensées. Un INNER la ferait disparaître
      -- du total sans rien dire — la forme de défaut que ce dépôt paie le plus cher.
      LEFT JOIN meta_campaigns mc ON mc.campaign_id = ma.campaign_id
                                 AND mc.artist_id = ma.artist_id
      LEFT JOIN meta_adsets ads ON ads.adset_id = ma.adset_id
                               AND ads.artist_id = ma.artist_id
     WHERE mi.artist_id IS NOT NULL
     GROUP BY mi.artist_id, ma.ad_account_id, ma.ad_name, mc.campaign_name,
              ads.optimization_goal, mi.date::date;

COMMENT ON VIEW v_meta_creative_daily IS
    'Couche OR (ADR-019) : la performance Meta au grain (locataire, créative, '
    'jour). Porte la jointure vers meta_ads et meta_adsets, y compris leur '
    'artist_id — elle était recopiée trois fois, et il suffit qu''une l''oublie '
    'pour mélanger deux locataires. Porte aussi ad_account_id : sans lui, un '
    'locataire multi-comptes faisait tomber la page Créatives (migration 108).';

-- ── META, maille AD SET ───────────────────────────────────────────────────
-- L'onglet « Ciblage vs Performance » recopiait la chaîne
-- `meta_adsets → meta_ads → meta_insights` avec le locataire nommé une seule
-- fois, sur la PREMIÈRE table :
--
--     JOIN meta_ads a       ON a.adset_id = s.adset_id
--     JOIN meta_insights mi ON mi.ad_id   = a.ad_id
--     WHERE s.artist_id = %s
--
-- Deux locataires partageant un `adset_id` ou un `ad_id` mélangeaient donc leurs
-- dépenses. C'est mot pour mot la classe que le commentaire de la migration 106
-- décrit — recopiée une quatrième fois dans un autre fichier, ce qui est la
-- démonstration que le commentaire ne garde rien.
CREATE OR REPLACE VIEW v_meta_adset_daily AS
    SELECT mi.artist_id,
           s.ad_account_id,
           s.adset_id,
           s.adset_name,
           s.optimization_goal,
           s.gender,
           s.publisher_platforms,
           s.age_min,
           s.age_max,
           mi.date::date                             AS day,
           COALESCE(SUM(mi.spend), 0)::numeric       AS spend,
           COALESCE(SUM(mi.conversions), 0)::bigint  AS conversions,
           COALESCE(SUM(mi.impressions), 0)::bigint  AS impressions,
           COALESCE(SUM(mi.clicks), 0)::bigint       AS clicks,
           COALESCE(SUM(mi.reach), 0)::bigint        AS reach
      FROM meta_insights mi
      JOIN meta_ads a  ON a.ad_id = mi.ad_id AND a.artist_id = mi.artist_id
      JOIN meta_adsets s ON s.adset_id = a.adset_id AND s.artist_id = a.artist_id
     WHERE mi.artist_id IS NOT NULL
     GROUP BY mi.artist_id, s.ad_account_id, s.adset_id, s.adset_name,
              s.optimization_goal, s.gender, s.publisher_platforms,
              s.age_min, s.age_max, mi.date::date;

COMMENT ON VIEW v_meta_adset_daily IS
    'Couche OR (ADR-019) : la performance Meta au grain (locataire, ad set, jour), '
    'avec les attributs de ciblage. Le locataire est nommé sur CHAQUE jointure — '
    'la requête qu''elle remplace ne le nommait que sur meta_adsets.';

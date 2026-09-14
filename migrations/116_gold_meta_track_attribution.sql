-- ═══════════════════════════════════════════════════════════════════════════
-- 116 — « Quelle part de ma dépense Meta est rattachable à un titre ? »
-- ═══════════════════════════════════════════════════════════════════════════
-- Arbitrage R107 §3, tranché le 2026-09-14. La question posée — « faut-il faire
-- apparaître les 24 % que Meta n'attribue à aucune dimension » — a été déplacée par
-- la mesure : la couverture des breakdowns est DÉJÀ recalculée et expliquée à chaque
-- rendu (`meta_breakdowns._render_coverage`), alors qu'un trou plus grand n'était dit
-- nulle part. Mesuré sur l'artiste 1 : **zéro** campagne rattachée à un titre, quand
-- six plateformes sur sept portent leurs onze titres liés dans `track_platform_link`.
--
-- Pourquoi une VUE et pas trois `COUNT(*)` dans la page
-- -----------------------------------------------------
-- La première version de l'encart comptait les liens depuis `meta_ads_overview.py`,
-- en lisant `track_platform_link` directement. `tests/test_the_bronze_boundary_only_
-- tightens.py` l'a refusée dans l'heure : 109 couples (surface, table de bronze)
-- contre un plafond de 108. Le cliquet avait raison, et pas seulement sur la forme —
-- « rattachable » EST une définition métier (quel statut de lien compte, quelle
-- plateforme, quel locataire), et une définition écrite dans une page finit par
-- diverger de celle écrite dans la suivante. C'est ADR-019, et c'est exactement la
-- classe qui a fait afficher trois totaux YouTube incompatibles.
--
-- Ce que la vue rend, au grain du LOCATAIRE
-- -----------------------------------------
--   campaigns        — campagnes distinctes connues (v_meta_campaign_daily)
--   linked_campaigns — celles rattachées à un titre par un lien CONFIRMÉ
--   spend            — la dépense totale, telle que v_meta_spend_totals la définit
--
-- `status = 'confirmed'` est le seul statut qui compte : un lien `rejected` est une
-- décision explicite de NE PAS rattacher, et un lien proposé n'est pas un lien. Ce
-- prédicat est désormais écrit ici, une fois.
--
-- Le rattachement se fait sur `platform_ref_id` quand il est renseigné, et sur le
-- nom de campagne sinon — les deux voies qu'utilise la page de mapping. Un locataire
-- sans aucune campagne rend une ligne à zéro plutôt qu'aucune ligne : l'absence de
-- rattachement est un FAIT à afficher, pas une donnée manquante. Idempotent.

CREATE OR REPLACE VIEW v_meta_track_attribution AS
    WITH campaigns AS (
        SELECT artist_id, campaign_name
          FROM v_meta_campaign_daily
         WHERE artist_id IS NOT NULL
         GROUP BY artist_id, campaign_name
    ),
    links AS (
        SELECT artist_id, platform_ref_id, platform_title
          FROM track_platform_link
         WHERE platform = 'meta' AND status = 'confirmed'
    )
    SELECT c.artist_id,
           COUNT(*)::bigint AS campaigns,
           COUNT(*) FILTER (
               WHERE EXISTS (
                   SELECT 1 FROM links l
                    WHERE l.artist_id = c.artist_id
                      AND (l.platform_ref_id = c.campaign_name
                           OR l.platform_title = c.campaign_name)))::bigint
               AS linked_campaigns
      FROM campaigns c
     GROUP BY c.artist_id;

COMMENT ON VIEW v_meta_track_attribution IS
    'Couche OR (ADR-019) : combien de campagnes Meta ce locataire porte, et combien '
    'sont rattachées à un titre par un lien CONFIRMÉ. Répond à « cette section '
    'peut-elle dire ce qu''un titre m''a coûté ». Le prédicat status = ''confirmed'' '
    'et la façon de rapprocher une campagne d''un lien sont écrits ICI, une seule '
    'fois. R107 §3, tranché le 2026-09-14.';

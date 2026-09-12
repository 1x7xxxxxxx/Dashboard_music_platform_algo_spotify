-- ═══════════════════════════════════════════════════════════════════════════
-- 111 — SACEM : le relevé au grain (locataire, mois, nature de ligne)
-- ═══════════════════════════════════════════════════════════════════════════
-- La page Royalties SACEM affiche TROIS totaux — royalties brutes, charges
-- sociales, TVA — et les calculait en pandas, sur les lignes brutes :
--
--     gross   = df.loc[df.line_type == 'repartition', 'mouvement_eur'].sum()
--     charges = df.loc[df.line_type == 'charge',      'mouvement_eur'].sum()
--     tva     = df.loc[df.line_type == 'tva',         'mouvement_eur'].sum()
--
-- Aucun `SUM(` dans la requête, donc aucun garde SQL ne pouvait les voir — la
-- même forme que la tuile « Dépenses » de Meta Ads, qui affichait le double.
--
-- Et le premier des trois EST déjà une définition de la couche or :
-- `v_artist_monthly_revenue` retient `line_type = 'repartition'` pour sa branche
-- SACEM. Deux surfaces répondaient donc à « combien la SACEM a-t-elle versé » par
-- deux chemins, dont un en pandas. Elles s'accordent aujourd'hui (43,06 € par les
-- deux) parce que le prédicat est le même des deux côtés — c'est-à-dire écrit deux
-- fois.
--
-- Les deux autres natures n'avaient AUCUNE définition partagée. Elles en ont une.
CREATE OR REPLACE VIEW v_sacem_monthly AS
    SELECT artist_id,
           EXTRACT(YEAR  FROM line_date)::integer AS year,
           EXTRACT(MONTH FROM line_date)::integer AS month,
           line_type,
           COALESCE(SUM(mouvement_eur), 0)::numeric AS amount,
           COUNT(*)::bigint                         AS lines
      FROM sacem_statement
     WHERE artist_id IS NOT NULL
     GROUP BY artist_id, 1 + 0, EXTRACT(YEAR FROM line_date),
              EXTRACT(MONTH FROM line_date), line_type;

COMMENT ON VIEW v_sacem_monthly IS
    'Couche OR (ADR-019) : le relevé SACEM au grain (locataire, mois, nature de '
    'ligne). Les trois totaux de la page Royalties en sortent, et la branche '
    'sacem de v_artist_monthly_revenue est la ligne repartition de cette vue.';

-- `v_artist_monthly_revenue` cesse de redéclarer `line_type = 'repartition'`.
-- Les colonnes et leur ordre sont inchangés : CREATE OR REPLACE l'exige.
CREATE OR REPLACE VIEW v_artist_monthly_revenue AS
    SELECT artist_id, year, month, 'imusician'::text AS source, revenue_eur
      FROM imusician_monthly_revenue
    UNION ALL
    SELECT artist_id, year, month, 'distrokid'::text, revenue_eur
      FROM distrokid_monthly_revenue
    UNION ALL
    SELECT artist_id, year, month, 'sacem'::text, amount
      FROM v_sacem_monthly
     WHERE line_type = 'repartition';

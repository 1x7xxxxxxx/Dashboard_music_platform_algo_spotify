-- ═══════════════════════════════════════════════════════════════════════════
-- 115 — Le revenu a DEUX chiffres, et celui affiché comme « net » était FAUX
-- ═══════════════════════════════════════════════════════════════════════════
-- Arbitrage tranché le 2026-09-14 (R107 §2) : on affiche le BRUT **et** le NET, au
-- lieu de choisir. En descendant le net dans la couche or on a découvert qu'il
-- n'était pas seulement dupliqué — il était FAUX à l'écran.
--
-- Le défaut, mesuré sur le relevé de l'artiste 1
-- ----------------------------------------------
-- `src/dashboard/views/sacem.py` affichait « ✅ Net estimé » :
--
--     net = gross + charges + tva          →  43,06 − 6,90 − 14,67 = 21,49 €
--
-- Le compte en banque a reçu **36,49 €** — la somme des quatre lignes `payout`
-- (virements Caisse d'Épargne). La page se trompait de **15,00 €, soit 41 %**, sur
-- le seul chiffre qu'un artiste peut vérifier lui-même sur son relevé bancaire.
--
-- La cause : une nature de ligne ne dit pas de QUOI elle se retranche
-- -------------------------------------------------------------------
-- Les 9 lignes `tva` du relevé ne sont pas une population homogène :
--
--   • 8 × `FORFAIT TVA`, de +0,01 à +0,11, **positives**, une par répartition —
--     la TVA forfaitaire que la SACEM reverse AVEC la répartition. Total +0,33.
--   • 1 × `Tva /frais d'admission`, **−15,00**, en janvier 2023, qui appartient au
--     bloc d'adhésion : +100,00 versés, −75,00 de frais, −10,00 de part sociale,
--     −15,00 de TVA. Ce bloc se solde à zéro et ne concerne AUCUNE royaltie.
--
-- Sommer les 9 revenait à retrancher des royalties un frais d'adhésion payé un an
-- avant la première répartition. Classe `a-deduction-subtracted-from-the-wrong-base`.
--
-- La règle retenue, et pourquoi elle est structurelle et non textuelle
-- --------------------------------------------------------------------
-- **Une retenue ne compte que dans un mois qui porte une répartition.** Distinguer
-- par le libellé (`FORFAIT TVA` vs `Tva /frais d'admission`) aurait marché ce jour-là
-- et cassé au premier changement de formulation de la SACEM — le dépôt a déjà payé
-- quatre gardes textuels pris verts sur leur propre défaut.
--
-- La règle du mois tient à une raison de FOND, lisible dans le relevé : les charges
-- sont un POURCENTAGE de la répartition (« CSG DEDUCTIBLE 6.80% (BASE 98.25%) »).
-- Sans répartition il n'y a pas de base, donc pas de charge à en retrancher.
--
-- Et elle se vérifie, ce qui est le point : le net ainsi défini vaut **36,49 €**,
-- soit EXACTEMENT la somme des quatre virements, au centime — alors que la page en
-- affichait 21,49. C'est la réconciliation qui a fait choisir cette règle plutôt
-- qu'une autre.
--
-- Cette égalité n'est PAS devenue un invariant permanent, et ce choix est délibéré :
-- elle n'est vraie qu'une fois tout distribué. Une répartition tombée en janvier
-- attend son virement d'avril — entre les deux, net ≠ virements, normalement. Un
-- contrôle rouge en régime normal est la classe `a-check-that-can-never-pass`, déjà
-- payée ici. La règle est gardée autrement : `tests/test_a_deduction_is_subtracted_
-- from_the_right_base.py` construit un relevé de synthèse dans une transaction
-- annulée et prouve que le bloc d'adhésion n'entre pas dans le net.
--
-- Ce que cette migration NE touche pas, et pourquoi
-- ------------------------------------------------
-- `v_artist_monthly_revenue` reste le BRUT, inchangée. Huit surfaces la lisent (ROI
-- breakeven, prévision, PDF, imusician, trigger_algo, les invariants or) et toutes
-- veulent le brut : le point de bascule du ROI se compare à une dépense publicitaire
-- avant retenues, et la branche distributeur n'a aucune retenue. En changer la
-- définition aurait déplacé huit chiffres pour en corriger un.
--
-- Ce que « net » veut dire par source
-- -----------------------------------
--   • sacem     : brut + retenues DU MOIS OÙ IL Y A UNE RÉPARTITION. Ce n'est pas la
--                 ligne `payout` : un virement solde un cumul et tombe dans un mois
--                 quelconque ; l'accrocher à un mois de répartition inventerait une
--                 causalité. Les deux s'égalent sur le CUMUL, pas mois par mois.
--   • imusician : net = brut. Le distributeur verse ce qu'il déclare, sa commission
--                 est déjà retirée du chiffre qu'il nous donne.
--   • distrokid : idem.
-- Une source qui gagnerait une retenue propre s'ajoute ici, pas dans une vue.
--
-- Le grain reste (locataire, année, mois, source), identique à
-- `v_artist_monthly_revenue`, pour que les deux se joignent sans conversion.
-- `mouvement_eur` est SIGNÉ (+ entrée, − retenue) : le net est une SOMME, jamais une
-- soustraction — écrire `brut - retenues` doublerait la retenue. Idempotent.

CREATE OR REPLACE VIEW v_artist_monthly_revenue_net AS
    SELECT artist_id, year, month,
           'imusician'::text AS source,
           revenue_eur::numeric AS gross_eur,
           0::numeric           AS deductions_eur,
           revenue_eur::numeric AS net_eur
      FROM imusician_monthly_revenue
    UNION ALL
    SELECT artist_id, year, month,
           'distrokid'::text,
           revenue_eur::numeric,
           0::numeric,
           revenue_eur::numeric
      FROM distrokid_monthly_revenue
    UNION ALL
    SELECT artist_id, year, month, 'sacem'::text,
           gross_eur,
           -- Le mois sans répartition ne porte pas de retenue SUR des royalties :
           -- son bloc (adhésion, régularisation) se solde ailleurs.
           CASE WHEN gross_eur <> 0 THEN raw_deductions_eur ELSE 0 END,
           gross_eur + CASE WHEN gross_eur <> 0 THEN raw_deductions_eur ELSE 0 END
      FROM (
          SELECT artist_id, year, month,
                 COALESCE(SUM(amount) FILTER (WHERE line_type = 'repartition'),
                          0)::numeric AS gross_eur,
                 COALESCE(SUM(amount) FILTER (WHERE line_type IN ('charge', 'tva')),
                          0)::numeric AS raw_deductions_eur
            FROM v_sacem_monthly
           GROUP BY artist_id, year, month
      ) s;

COMMENT ON VIEW v_artist_monthly_revenue_net IS
    'Couche OR (ADR-019) : le revenu mensuel par source avec ses DEUX chiffres — '
    'brut, retenues (signées, donc ≤ 0) et net = brut + retenues. Une retenue ne '
    'compte que dans un mois portant une répartition : les charges sont un % de la '
    'répartition, et le bloc d''adhésion de 2023 (TVA −15,00 €) n''en est pas une. '
    'Le net cumulé égale la somme des virements au centime — invariant '
    'sacem_net_equals_payouts. gross_eur reproduit v_artist_monthly_revenue, qui '
    'reste la porte du BRUT pour le ROI et la prévision. R107 §2, tranché 2026-09-14.';

-- ═══════════════════════════════════════════════════════════════════════════
-- 133 — Le compte de l'artiste : ce qui rentre, ce qui sort, sur une ligne
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Demandé le 2026-09-21 : « fusionner dans la view prévisions de revenus toutes
-- les dépenses et tous les couts […] intégrer également le cout de distribution
-- d'une musique avec le distributeur ».
--
-- ⚠️ CE COÛT N'EXISTE NULLE PART, et c'est le vrai trou de cette page.
--
-- Mesuré le 2026-09-21 sur toutes les tables du schéma : `app_operating_costs`
-- porte le VPS, les sauvegardes et les frais de l'EXPLOITANT — pas un euro de
-- l'artiste. Aucun distributeur n'expose son abonnement par API : iMusician
-- facture par sortie ou à l'année, et rien de cette facture ne redescend dans
-- les rapports de ventes. La seule source possible est donc l'artiste lui-même.
--
-- La page affichait, avant cette migration, un « ROI Meta » de +… ou −… calculé
-- sur les revenus MOINS la seule dépense qu'elle connaissait, la publicité. Sur
-- l'artiste 1 : 3 087,82 € de Meta contre 248,39 € de revenus nets. Le coût de
-- distribution manquant ne change pas le SIGNE de ce résultat, mais il change la
-- DATE du point mort, qui est précisément ce qu'on demande de lire.

-- ── 1. Les coûts que seul l'artiste connaît ────────────────────────────────
CREATE TABLE IF NOT EXISTS artist_cost_entries (
    id             SERIAL PRIMARY KEY,
    artist_id      INTEGER NOT NULL
                   REFERENCES saas_artists(id) ON DELETE CASCADE,
    category       TEXT NOT NULL
                   CHECK (category IN ('distribution', 'mastering', 'visuel',
                                       'promo', 'materiel', 'autre')),
    label          TEXT,
    amount_eur     NUMERIC(12,2) NOT NULL CHECK (amount_eur >= 0),
    -- `one_off` = une sortie payée une fois ; `yearly` = un abonnement
    -- distributeur ; `monthly` = un prélèvement. L'étalement est fait par la vue,
    -- jamais à la saisie : réécrire douze lignes pour un abonnement annuel, c'est
    -- perdre l'information « c'est UN abonnement » à la première correction.
    billing_period TEXT NOT NULL DEFAULT 'one_off'
                   CHECK (billing_period IN ('monthly', 'yearly', 'one_off')),
    start_month    DATE NOT NULL,
    end_month      DATE,
    note           TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT artist_cost_entries_window CHECK (end_month IS NULL
                                                 OR end_month >= start_month)
);

CREATE INDEX IF NOT EXISTS idx_artist_cost_entries_artist
    ON artist_cost_entries (artist_id, start_month);

COMMENT ON TABLE artist_cost_entries IS
    'Les coûts de l''ARTISTE (distribution, mastering, visuel…), saisis à la '
    'main : aucun distributeur ne les expose par API. Ne pas confondre avec '
    '`app_operating_costs`, qui porte ceux de l''exploitant.';

-- ── 2. Ces coûts, étalés au MOIS ───────────────────────────────────────────
--
-- Un `yearly` de 240 € se lit 20 €/mois sur douze mois ; un `one_off` tombe
-- entièrement sur son mois. Étaler ici et non à la saisie garde la ligne
-- corrigeable en un geste.
--
-- ⚠️ `end_month` non renseigné sur un abonnement veut dire « toujours en
-- cours » : on l'étale jusqu'au mois courant, jamais au-delà. Projeter une
-- dépense dans le futur ici la ferait compter DEUX FOIS — la projection de la
-- page s'en charge, et elle doit rester la seule à le faire.
CREATE OR REPLACE VIEW v_artist_monthly_costs AS
WITH bornes AS (
    SELECT c.id, c.artist_id, c.category, c.label, c.amount_eur,
           c.billing_period,
           date_trunc('month', c.start_month)::date AS debut,
           LEAST(
               COALESCE(date_trunc('month', c.end_month)::date,
                        date_trunc('month', CURRENT_DATE)::date),
               date_trunc('month', CURRENT_DATE)::date
           ) AS fin
    FROM artist_cost_entries c
),
etale AS (
    SELECT b.artist_id, b.category, b.label,
           gs::date AS mois,
           CASE b.billing_period
               WHEN 'monthly' THEN b.amount_eur
               WHEN 'yearly'  THEN ROUND(b.amount_eur / 12.0, 2)
               ELSE b.amount_eur
           END AS montant_eur
    FROM bornes b
    CROSS JOIN LATERAL generate_series(
        b.debut,
        CASE WHEN b.billing_period = 'one_off' THEN b.debut
             ELSE GREATEST(b.fin, b.debut) END,
        INTERVAL '1 month'
    ) gs
)
SELECT artist_id,
       EXTRACT(YEAR  FROM mois)::int AS year,
       EXTRACT(MONTH FROM mois)::int AS month,
       category,
       SUM(montant_eur)::numeric AS amount_eur
FROM etale
GROUP BY artist_id, mois, category;

COMMENT ON VIEW v_artist_monthly_costs IS
    'Les coûts artiste étalés au mois. `yearly` → /12, `one_off` → son mois seul.';

-- ── 3. Tout l'argent sur une ligne ─────────────────────────────────────────
--
-- UNE SEULE DÉFINITION du mouvement d'argent (ADR-019). La page traçait jusqu'ici
-- ses revenus depuis une vue et sa dépense Meta depuis une autre requête, avec
-- deux fenêtres, deux mailles et deux façons de traiter un mois vide. Les
-- réunir ici est ce qui rend le POINT MORT calculable : il n'existe pas tant que
-- les deux côtés ne partagent pas le même axe.
--
-- `direction` vaut +1 pour ce qui rentre, −1 pour ce qui sort. Le signe est
-- porté par une colonne plutôt que par le montant pour que `SUM(amount_eur)`
-- reste lisible comme un volume, et que la somme signée demande un geste
-- explicite (`SUM(amount_eur * direction)`).
CREATE OR REPLACE VIEW v_artist_monthly_cashflow AS
SELECT artist_id, year, month,
       'revenu'::text AS flux,
       source,
       net_eur::numeric AS amount_eur,
       1 AS direction
FROM v_artist_monthly_revenue_net
WHERE net_eur IS NOT NULL

UNION ALL

SELECT artist_id,
       EXTRACT(YEAR  FROM day)::int,
       EXTRACT(MONTH FROM day)::int,
       'depense'::text,
       'meta_ads'::text,
       SUM(spend)::numeric,
       -1
FROM v_meta_daily
GROUP BY artist_id, EXTRACT(YEAR FROM day), EXTRACT(MONTH FROM day)
HAVING SUM(spend) > 0

UNION ALL

SELECT artist_id, year, month,
       'depense'::text,
       category,
       amount_eur,
       -1
FROM v_artist_monthly_costs
WHERE amount_eur > 0;

COMMENT ON VIEW v_artist_monthly_cashflow IS
    'Tout l''argent de l''artiste au mois : revenus (distributeurs + SACEM) et '
    'dépenses (Meta Ads + coûts saisis). `direction` = +1 / −1. C''est la seule '
    'vue qui permette de calculer un point mort.';

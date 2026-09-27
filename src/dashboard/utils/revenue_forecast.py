"""Revenue-forecast math + data loaders (pure, testable).

Type: Utility
Uses: PostgresHandler (read-only SELECTs)
Depends on: pandas, dateutil
Persists in: — (read-only)

Extracted from views/revenue_forecast.py (refactor R6) so the forecasting math
is deterministic and unit-testable, decoupled from the Streamlit rendering.
"""

import pandas as pd

from src.utils.tenant_kind import non_human_tenant


# ── Data loaders (read-only) ────────────────────────────────────────────────

def load_subscriptions(db) -> pd.DataFrame:
    return db.fetch_df("""
        SELECT
            sa.name            AS artist_name,
            sp.name            AS plan,
            sp.price_monthly   AS price,
            asub.status,
            asub.cancel_at_period_end,
            asub.current_period_start,
            asub.current_period_end
        FROM artist_subscriptions asub
        JOIN subscription_plans sp  ON sp.id  = asub.plan_id
        JOIN saas_artists        sa  ON sa.id  = asub.artist_id
        -- R220: the admin MRR counts customers — never the canary or the sandbox
        -- (its Stripe test subscription survives every sandbox reset).
        WHERE NOT {non_human}
        ORDER BY sp.price_monthly DESC, sa.name
    """.format(non_human=non_human_tenant("sa")))


def load_artist_revenues(db, artist_id: int) -> pd.DataFrame:
    """Monthly music revenue per artist: iMusician + DistroKid + SACEM gross royalties
    (REPARTITION), summed per year/month — same revenue base as the ROI Breakeven.
    `revenue_eur` is the total; `sacem_eur` is the SACEM portion (kept distinct so the
    projection chart can plot SACEM's evolution as its own line)."""
    return db.fetch_df(
        """
        SELECT year, month, SUM(revenue_eur) AS revenue_eur,
               COALESCE(SUM(revenue_eur) FILTER (WHERE source = 'sacem'), 0) AS sacem_eur
        FROM v_artist_monthly_revenue
        WHERE artist_id = %s
        GROUP BY year, month
        ORDER BY year ASC, month ASC
        """,
        (artist_id,),
    )


# ── `load_artist_revenue_by_source` A ÉTÉ RETIRÉE le 2026-09-21 ─────────────
#
# Elle lisait `v_artist_monthly_revenue` — le BRUT — sous un nom qui dit
# seulement « revenue ». Son unique appelante affichait donc **43,06 €** de
# SACEM dans un tiroir, sous une figure qui en dessinait **36,49 €** depuis
# `v_artist_monthly_revenue_net`. Les deux nombres étaient justes ; l'écart est
# 6,57 € de charges et de TVA, et rien à l'écran ne disait lequel on regardait.
#
# Le retrait est le remède DURABLE, pas le renommage : tant que la fonction
# existe, le prochain appelant reproduira l'écart sans le voir. Ce qui compte
# pour un point mort est le net — ce qui arrive réellement sur le compte — et il
# se lit dans `v_artist_monthly_cashflow` (migration 133), la seule vue qui pose
# les revenus et les dépenses sur le même axe.
#
# Garde : `tests/test_the_money_has_one_definition.py`.


def load_artists(db) -> pd.DataFrame:
    return db.fetch_df(
        "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
    )


# ── Forecast math (pure) ─────────────────────────────────────────────────────

def ltv_global(arpu, churn_pct):
    """Classic LTV = ARPU / monthly churn rate (0 when churn is 0)."""
    return arpu / (churn_pct / 100) if churn_pct > 0 else 0.0


def ltv_scenarios(plans, durations):
    """LTV per (plan, retention-duration) = price × duration, rounded to cents."""
    return [
        {'Plan': plan_name, 'Durée (mois)': d, 'LTV (€)': round(default_price * d, 2)}
        for plan_name, default_price in plans
        for d in durations
    ]

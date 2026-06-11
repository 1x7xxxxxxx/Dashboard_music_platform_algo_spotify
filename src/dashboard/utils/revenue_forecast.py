"""Revenue-forecast math + data loaders (pure, testable).

Type: Utility
Uses: PostgresHandler (read-only SELECTs)
Depends on: pandas, dateutil
Persists in: — (read-only)

Extracted from views/revenue_forecast.py (refactor R6) so the forecasting math
is deterministic and unit-testable, decoupled from the Streamlit rendering.
"""
from datetime import datetime

import pandas as pd
from dateutil.relativedelta import relativedelta


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
        ORDER BY sp.price_monthly DESC, sa.name
    """)


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


def load_artist_revenue_by_source(db, artist_id: int) -> dict:
    """Total music revenue per source for an artist: {iMusician, DistroKid, SACEM}."""
    rows = db.fetch_query(
        "SELECT source, COALESCE(SUM(revenue_eur), 0) FROM v_artist_monthly_revenue "
        "WHERE artist_id = %s GROUP BY source",
        (artist_id,),
    )
    m = {r[0]: float(r[1] or 0) for r in (rows or [])}
    return {'iMusician': m.get('imusician', 0.0),
            'DistroKid': m.get('distrokid', 0.0),
            'SACEM': m.get('sacem', 0.0)}


def load_artists(db) -> pd.DataFrame:
    return db.fetch_df(
        "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY name"
    )


# ── Forecast math (pure) ─────────────────────────────────────────────────────

def project_mrr(mrr_0, growth_rate_pct, months, *, enterprise_on=False,
                ent_price=0.0, ent_per_month=0.0, mrr_target=None, start=None):
    """Compound monthly-growth MRR/ARR projection.

    Returns {'months': [labels], 'mrr': [...], 'arr': [...], 'target_month': int|None}.
    `target_month` is the first month index whose MRR reaches `mrr_target`.
    """
    if start is None:
        start = datetime.today().replace(day=1)
    mrr_vals, arr_vals, months_list = [], [], []
    target_month = None
    for t in range(months + 1):
        mrr_t = mrr_0 * ((1 + growth_rate_pct / 100) ** t)
        if enterprise_on:
            mrr_t += ent_price * min(t * ent_per_month, t * ent_per_month)
        arr_t = mrr_t * 12
        mrr_vals.append(round(mrr_t, 2))
        arr_vals.append(round(arr_t, 2))
        months_list.append((start + relativedelta(months=t)).strftime('%Y-%m'))
        if mrr_target is not None and target_month is None and mrr_t >= mrr_target:
            target_month = t
    return {'months': months_list, 'mrr': mrr_vals, 'arr': arr_vals,
            'target_month': target_month}


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

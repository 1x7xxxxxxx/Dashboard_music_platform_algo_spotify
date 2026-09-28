"""⚙️ Paramètres de mes campagnes — how each campaign was set up, beside what it produced.

Type: Feature
Uses: meta_campaigns, meta_adsets, meta_ads (the SETTINGS — attributes, never summed),
      v_meta_campaign_daily (the OUTCOME — gold), utils.ratios, utils.filters.account
Triggers: app routing (`meta_campaign_settings`) — Premium
Persists in: nothing

R272 (owner notes L129, L134 : « une vue qui regroupe les paramètres de campagne et les
budgets ») — code-critic verdict (c) BUILD. The settings were spread over three Meta
screens (campaign, ad set, ad) and the outcome over a fourth: the question « which set-up
worked » needed four tabs and a memory. Here one row per campaign carries its objective,
budget, dates, the audience and placements of its ad sets, the calls to action of its ads —
and, from the gold layer, what it spent and what one outbound click cost.

The settings are ATTRIBUTES read as they are; every number that sums comes from
`v_meta_campaign_daily`, and every ratio from `utils.ratios` (R258).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils import formats, view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ratios import per_series

_SETTINGS = """
SELECT c.campaign_name, c.objective, c.status, c.daily_budget, c.lifetime_budget,
       c.start_time::date AS debut, c.end_time::date AS fin,
       string_agg(DISTINCT s.optimization_goal, ' · ') AS optimisation,
       string_agg(DISTINCT s.countries::text, ' · ') AS pays,
       string_agg(DISTINCT concat_ws('–', s.age_min, s.age_max), ' · ') AS ages,
       string_agg(DISTINCT s.publisher_platforms::text, ' · ') AS plateformes,
       string_agg(DISTINCT s.instagram_positions::text, ' · ') AS emplacements,
       bool_or(s.advantage_audience::text IN ('1', 'true', 't')) AS advantage,
       string_agg(DISTINCT a.call_to_action, ' · ') AS appel_action
  FROM meta_campaigns c
  LEFT JOIN meta_adsets s ON s.artist_id = c.artist_id AND s.campaign_id = c.campaign_id
  LEFT JOIN meta_ads a ON a.artist_id = c.artist_id AND a.campaign_id = c.campaign_id
 WHERE c.artist_id = %s
 GROUP BY c.campaign_name, c.objective, c.status, c.daily_budget, c.lifetime_budget,
          c.start_time, c.end_time
"""

_OUTCOME = """
SELECT campaign_name, SUM(spend) AS depense, SUM(link_clicks) AS clics,
       SUM(custom_conversions) AS clics_sortants
  FROM v_meta_campaign_daily
 WHERE artist_id = %s
 GROUP BY campaign_name
"""


def campaign_table(settings: pd.DataFrame, outcome: pd.DataFrame) -> pd.DataFrame:
    """One row per campaign: its settings, then what it produced. Pure."""
    df = settings.merge(outcome, on="campaign_name", how="left", validate="many_to_one")
    df["cpr"] = per_series(df["depense"], df["clics_sortants"])
    df["cpc"] = per_series(df["depense"], df["clics"])
    # Budgets are stored in EUROS — the collector converts Meta's cents (measured on the
    # base, 2026-09-28: 4.00, 20.00 — and `v_meta_active_budget` reads them as they are).
    for col in ("daily_budget", "lifetime_budget"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("depense", ascending=False, na_position="last")


def show() -> None:
    st.title(t("meta_campaign_settings.title", "⚙️ Paramètres de mes campagnes"))
    st.caption(t("meta_campaign_settings.intro",
                 "Comment chaque campagne a été réglée — objectif, budget, audience, "
                 "emplacements, bouton — à côté de ce qu'elle a produit. La question : "
                 "quel réglage a le mieux marché ?"))
    with view_session() as (db, artist_id):
        settings = db.fetch_df(_SETTINGS, (artist_id,))
        outcome = db.fetch_df(_OUTCOME, (artist_id,))
    if settings is None or settings.empty:
        st.info(t("meta_campaign_settings.empty",
                  "Aucune campagne Meta collectée pour l'instant. Elles arrivent avec la "
                  "collecte Meta du matin, une fois ton compte publicitaire connecté."))
        return
    df = campaign_table(settings, outcome if outcome is not None else pd.DataFrame(
        columns=["campaign_name", "depense", "clics", "clics_sortants"]))
    labels = {
        "campaign_name": t("meta_campaign_settings.col_campaign", "Campagne"),
        "objective": t("meta_campaign_settings.col_objective", "Objectif"),
        "status": t("meta_campaign_settings.col_status", "Statut"),
        "daily_budget": t("meta_campaign_settings.col_daily", "Budget/jour (€)"),
        "lifetime_budget": t("meta_campaign_settings.col_lifetime", "Budget total (€)"),
        "debut": t("meta_campaign_settings.col_start", "Début"),
        "fin": t("meta_campaign_settings.col_end", "Fin"),
        "optimisation": t("meta_campaign_settings.col_goal", "Optimisation"),
        "pays": t("meta_campaign_settings.col_countries", "Pays"),
        "ages": t("meta_campaign_settings.col_ages", "Âges"),
        "plateformes": t("meta_campaign_settings.col_platforms", "Plateformes"),
        "emplacements": t("meta_campaign_settings.col_positions", "Emplacements"),
        "advantage": t("meta_campaign_settings.col_advantage", "Advantage+"),
        "appel_action": t("meta_campaign_settings.col_cta", "Bouton"),
        "depense": t("meta_campaign_settings.col_spend", "Dépense (€)"),
        "cpr": t("meta_campaign_settings.col_cpr", "Coût / clic sortant (€)"),
        "cpc": t("meta_campaign_settings.col_cpc", "Coût / clic (€)"),
    }
    formats.table(df[list(labels)].rename(columns=labels))
    st.caption(t("meta_campaign_settings.note",
                 "Les réglages sont ceux de Meta, tels quels ; la dépense et les coûts "
                 "viennent de la couche or, la même que « Publicité Meta Ads ». Un coût "
                 "« — » : la campagne n'a eu aucun clic de ce type."))


if __name__ == "__main__":
    show()

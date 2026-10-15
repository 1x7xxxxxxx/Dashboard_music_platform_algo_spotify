"""The panels of « Tes meilleurs réglages », read once for any set of campaigns (R598).

Type: Utility
Uses: src.dashboard.utils.best_settings, src.dashboard.views.meta_creatives (_QUERY_CREATIVES,
      _par_hook), src.dashboard.views.meta_breakdowns (_breakdown_frame, _panel)
Triggers: views/trigger_algo/_settings.py
Depends on: v_meta_creative_daily, v_meta_ad_daily, the Meta performance breakdowns
Persists in: nothing

R598 (owner, 2026-10-15) — « déplace les meilleurs réglages dans Prédiction algos, avec la
photo des réglages Meta optimaux ». The tool left the cross view for the page that asks
« how do I trigger the algorithms »: there the campaigns are the ones run for the releases
being judged, and the photo pools them into ONE best value per setting. The cross view
had them since R557; this reverses that move, at the owner's request.

A panel is RAW here — (label, frame, value column, spend column, results column) — so the
same rows give both the per-campaign bars (`by_campaign`) and the pooled photo (`photo`):
the CPR of a pooled value is Σspend / Σresults again, never a mean of the campaigns' CPRs.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils import best_settings
from src.dashboard.utils.i18n import t

# R557 — the two settings the ad set holds and the breakdowns do not: button and objective.
# `v_meta_ad_daily` carries no conversions, so these are priced per AD click (said in the
# caption). Two literals, not one template: `tools/dev/gold_coverage.py` reads the view name
# from each query's text. Classe : `a-join-that-multiplies-the-grain`.
_Q_AXE = {
    "cta": """
        SELECT call_to_action AS valeur, COUNT(DISTINCT ad_id) AS ads,
               SUM(spend) AS depense, SUM(clicks) AS clics,
               SUM(impressions) AS impressions, campaign_name
          FROM v_meta_ad_daily
         WHERE artist_id = %s GROUP BY 1, campaign_name
    """,
    "objectif": """
        SELECT objective AS valeur, COUNT(DISTINCT ad_id) AS ads,
               SUM(spend) AS depense, SUM(clicks) AS clics,
               SUM(impressions) AS impressions, campaign_name
          FROM v_meta_ad_daily
         WHERE artist_id = %s GROUP BY 1, campaign_name
    """,
}

Panel = tuple[str, pd.DataFrame, str, str, str]


def creatives(db, artist_id: int) -> pd.DataFrame:
    """Every creative × campaign of the tenant, all accounts, all time."""
    from src.dashboard.views.meta_creatives import _QUERY_CREATIVES
    return db.fetch_df(_QUERY_CREATIVES.format(acct=""), (artist_id,))


def raw_panels(db, artist_id: int, campaigns: list[str],
               df: pd.DataFrame | None = None) -> list[Panel]:
    """Every setting's rows for `campaigns`, each row naming its `campaign_name`."""
    from src.dashboard.views.meta_creatives import _par_hook
    df = creatives(db, artist_id) if df is None else df
    d = df[df["campaign_name"].isin(campaigns)] if not df.empty else df
    hooks = pd.concat([_par_hook(g).assign(campaign_name=k)
                       for k, g in d.groupby("campaign_name", sort=False)] or [pd.DataFrame()])
    out: list[Panel] = [
        (t("meta_creatives.bs_creative", "Créative"), d, "creative_name", "total_spend",
         "total_results"),
        (t("meta_creatives.bs_hook", "Accroche"), hooks, "hook", "total_spend",
         "total_results")]
    return out + _breakdown_panels(db, artist_id, campaigns) + _ad_panels(db, artist_id,
                                                                         campaigns)


def _breakdown_panels(db, artist_id: int, campaigns: list[str]) -> list[Panel]:
    """Country, placement, platform, age — Meta's breakdowns, one read per campaign."""
    from src.dashboard.views.meta_breakdowns import _breakdown_frame, _panel
    frames = []
    for c in campaigns:
        bd = _breakdown_frame(db, artist_id, "performance", "campaign", "campaign_name", c,
                              "", ())
        # psycopg2 returns SUM() as Decimal (object dtype): `_panel` keeps only numeric
        # columns when it folds placements into platforms, and would drop the spend.
        for col in ("spend", "results"):
            if col in bd:
                bd[col] = pd.to_numeric(bd[col], errors="coerce")
        frames.append((c, bd))
    out: list[Panel] = []
    for panel, label in (("country", t("meta_creatives.bs_country", "Pays")),
                         ("placement", t("meta_creatives.bs_placement", "Placement")),
                         ("platform", t("meta_creatives.bs_platform", "Plateforme")),
                         ("age", t("meta_creatives.bs_age", "Âge"))):
        parts = [_panel(bd, panel).assign(campaign_name=c) for c, bd in frames if not bd.empty]
        out.append((label, pd.concat(parts) if parts else pd.DataFrame(), "dim_label",
                    "spend", "results"))
    return out


def _ad_panels(db, artist_id: int, campaigns: list[str]) -> list[Panel]:
    """The settings chosen per ad: CTA and campaign objective."""
    out: list[Panel] = []
    for axe, label in (("cta", t("meta_creatives.bs_cta", "Bouton d'action (€/clic)")),
                       ("objectif", t("meta_creatives.bs_objective", "Objectif (€/clic)"))):
        f = db.fetch_df(_Q_AXE[axe], (artist_id,))
        f = f[f["campaign_name"].isin(campaigns)] if not f.empty else f
        out.append((label, f, "valeur", "depense", "clics"))
    return out


def by_campaign(raw: list[Panel]) -> list[tuple[str, pd.DataFrame]]:
    """One ranking per campaign, stacked (`best_settings.rank_by`) — the figure's input."""
    return [(label, best_settings.rank_by(f, col, "campaign_name", s, r))
            for label, f, col, s, r in raw]


def photo(raw: list[Panel]) -> pd.DataFrame:
    """The pooled photo: one row per setting, its best value, or « pas assez de données ».

    Pure. A setting needs two reliable values across the pooled campaigns
    (`best_settings.best`), the same discipline as the bars."""
    rows = []
    for label, f, col, s, r in raw:
        b = best_settings.best(best_settings.rank(f, col, s, r))
        rows.append({
            "parametre": label,
            "meilleure": b["valeur"] if b else t("best_settings.not_enough",
                                                 "pas assez de données"),
            "cpr": round(b["cpr"], 3) if b else None,
            "eviter": b["eviter"] if b else None,
            "facteur": round(b["facteur"], 1) if b and b["facteur"] else None})
    return pd.DataFrame(rows, columns=["parametre", "meilleure", "cpr", "eviter", "facteur"])

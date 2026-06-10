"""Vue Breakdowns Meta — pays / placement / âge à tous les grains.

Type: Feature
Uses: get_db_connection, get_artist_id, require_plan, utils.geo, utils.charts
Depends on: meta_insights_{performance,engagement}[_ad|_adset]_{country,placement,age}
Persists in: read-only

Les tables breakdown sont des AGRÉGATS sur toute la plage (pas de dimension date) :
le filtrage se fait par entité (campagne / adset / créative), pas par période.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.geo import iso2_to_iso3, iso2_to_name
from src.dashboard.utils.charts import pareto_spend_cpr
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin, require_plan


# Grain is derived from the deepest specific selection in the campaign→adset→ad cascade.
_GRAIN_FR = {"campaign": "Campagne", "adset": "Adset", "ad": "Créative"}

# label → (dim_key, [dimension columns])
_DIMS = {
    "Pays":      ("country", ["country"]),
    "Placement": ("placement", ["platform", "placement"]),
    "Âge":       ("age", ["age_range"]),
}
_FAMILIES = {"Performance": "performance", "Engagement": "engagement"}
_ENG_COLS = ["page_interactions", "post_reactions", "comments",
             "saves", "shares", "link_clicks", "post_likes"]

# Allowlist of every breakdown table this view may query (rule #8 — table names are
# composed below, so the final name is asserted against this fixed set).
_ALLOWED = frozenset(
    f"meta_insights_{fam}_{infix}{dim}"
    for fam in ("performance", "engagement")
    for infix in ("", "ad_", "adset_")
    for dim in ("country", "placement", "age")
)


def _table_name(family: str, grain: str, dim: str) -> str:
    name = f"meta_insights_{family}_{dim}" if grain == "campaign" \
        else f"meta_insights_{family}_{grain}_{dim}"
    if name not in _ALLOWED:
        raise ValueError(f"breakdown table not allowed: {name}")
    return name


def _dim_label(df, dim_key):
    if dim_key == "country":
        return df['country'].map(iso2_to_name)
    if dim_key == "placement":
        return df['platform'].fillna('?') + " / " + df['placement'].fillna('?')
    return df['age_range']


def _render_performance(df, dim_key, entity_label):
    df = df.copy()
    for c in ('spend', 'results', 'impressions', 'reach'):
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    total_spend, total_res = df['spend'].sum(), df['results'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric(t("meta_breakdowns.total_spend", "Dépense totale"), f"{total_spend:,.2f} €")
    c2.metric(t("meta_breakdowns.results", "Résultats"), f"{int(total_res):,}")
    c3.metric(t("meta_breakdowns.avg_cpr", "CPR moyen"), f"{total_spend / total_res:,.2f} €" if total_res else "—")

    df['dim_label'] = _dim_label(df, dim_key)

    if dim_key == "country":
        geo = df.copy()
        geo['iso3'] = geo['country'].map(iso2_to_iso3)
        geo = geo.dropna(subset=['iso3'])
        if not geo.empty:
            fig = px.choropleth(
                geo, locations='iso3', color='spend', hover_name='dim_label',
                color_continuous_scale='YlOrRd',
                labels={'spend': t("meta_breakdowns.spend_eur", "Dépense (€)")},
            )
            fig.update_layout(margin={'l': 0, 'r': 0, 't': 10, 'b': 0},
                              geo={'showframe': False})
            st.plotly_chart(fig, width="stretch")

    fig = pareto_spend_cpr(
        df, 'dim_label',
        t("meta_breakdowns.pareto_title", "Dépense & CPR — {entity}").format(entity=entity_label))
    if fig is not None:
        st.plotly_chart(fig, width="stretch")


def _render_engagement(df, dim_key, entity_label):
    df = df.copy()
    for c in _ENG_COLS:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df['dim_label'] = _dim_label(df, dim_key)
    df['total'] = df[_ENG_COLS].sum(axis=1)
    df = df.sort_values('total', ascending=False).head(15)
    if df['total'].sum() == 0:
        st.info(t("meta_breakdowns.no_engagement", "Aucune interaction d'engagement sur cette sélection."))
        return

    if dim_key == "country":
        geo = df.copy()
        geo['iso3'] = geo['country'].map(iso2_to_iso3)
        geo = geo.dropna(subset=['iso3'])
        if not geo.empty:
            fig = px.choropleth(geo, locations='iso3', color='total', hover_name='dim_label',
                                color_continuous_scale='Blues',
                                labels={'total': t("meta_breakdowns.interactions", "Interactions")})
            fig.update_layout(margin={'l': 0, 'r': 0, 't': 10, 'b': 0}, geo={'showframe': False})
            st.plotly_chart(fig, width="stretch")

    var_col = t("meta_breakdowns.type", "Type")
    val_col = t("meta_breakdowns.volume", "Volume")
    melted = df.melt(id_vars='dim_label', value_vars=_ENG_COLS,
                     var_name=var_col, value_name=val_col)
    fig = px.bar(melted, x='dim_label', y=val_col, color=var_col,
                 title=t("meta_breakdowns.engagement_title", "Engagement — {entity}").format(entity=entity_label),
                 labels={'dim_label': ''})
    fig.update_layout(barmode='stack', height=420)
    st.plotly_chart(fig, width="stretch")


def show() -> None:
    if not require_plan('premium'):
        return

    st.title(t("meta_breakdowns.title", "🌍 Breakdowns Meta"))
    st.caption(t(
        "meta_breakdowns.subtitle",
        "Pays / placement / âge à tous les grains (campagne · adset · créative). "
        "Données agrégées sur tout l'historique — **pas de filtre par période** "
        "(les breakdowns Meta n'ont pas de dimension date)."
    ))

    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error(t("meta_breakdowns.invalid_session", "Session invalide.")); st.stop()
        artist_id = 1

    d1, d2 = st.columns(2)
    dim_label = d1.selectbox(
        t("meta_breakdowns.dimension", "Dimension"), list(_DIMS.keys()),
        format_func=lambda lbl: t(f"meta_breakdowns.dim.{_DIMS[lbl][0]}", lbl))
    family_label = d2.selectbox(
        t("meta_breakdowns.metric", "Métrique"), list(_FAMILIES.keys()),
        format_func=lambda lbl: t(f"meta_breakdowns.family.{_FAMILIES[lbl]}", lbl))
    dim_key, _ = _DIMS[dim_label]
    family = _FAMILIES[family_label]

    db = get_db_connection()
    if db is None:
        st.error(t("meta_breakdowns.db_unavailable", "Base de données inaccessible."))
        return
    try:
        # Entities listed most-recent-first (last launched on top), via each table's
        # recency column — start_time for campaigns/adsets, created_time for ads.
        camps = db.fetch_df(
            "SELECT campaign_id, campaign_name FROM meta_campaigns "
            "WHERE artist_id = %s AND campaign_name IS NOT NULL "
            "ORDER BY start_time DESC NULLS LAST, campaign_name",
            (artist_id,),
        )
        adsets = db.fetch_df(
            "SELECT adset_id, adset_name, campaign_id FROM meta_adsets "
            "WHERE artist_id = %s AND adset_name IS NOT NULL "
            "ORDER BY start_time DESC NULLS LAST, adset_name",
            (artist_id,),
        )
        ads = db.fetch_df(
            "SELECT ad_id, ad_name, adset_id, campaign_id FROM meta_ads "
            "WHERE artist_id = %s AND ad_name IS NOT NULL "
            "ORDER BY created_time DESC NULLS LAST, ad_name",
            (artist_id,),
        )

        # Cascade : Campagne → Adset → Créative. Each level is scoped to the one above.
        # "Toutes"/"Tous" stay internal sentinel values; only their display is translated.
        _all_f = lambda c: t("meta_breakdowns.all_f", "Toutes") if c == "Toutes" else c  # noqa: E731
        f1, f2, f3 = st.columns(3)
        camp_sel = f1.selectbox(t("meta_breakdowns.campaign", "Campagne"),
                                ["Toutes"] + camps['campaign_name'].tolist(), key="bd_camp",
                                format_func=_all_f)
        camp_ids = (camps[camps['campaign_name'] == camp_sel]['campaign_id'].tolist()
                    if camp_sel != "Toutes" else None)

        adsets_f = adsets if camp_ids is None else adsets[adsets['campaign_id'].isin(camp_ids)]
        adset_sel = f2.selectbox(t("meta_breakdowns.adset", "Adset"),
                                 ["Tous"] + adsets_f['adset_name'].tolist(), key="bd_adset",
                                 format_func=lambda c: t("meta_breakdowns.all_m", "Tous") if c == "Tous" else c)
        adset_id = (adsets_f[adsets_f['adset_name'] == adset_sel]['adset_id'].iloc[0]
                    if adset_sel != "Tous" else None)

        if adset_id is not None:
            ads_f = ads[ads['adset_id'] == adset_id]
        elif camp_ids is not None:
            ads_f = ads[ads['campaign_id'].isin(camp_ids)]
        else:
            ads_f = ads
        ad_sel = f3.selectbox(t("meta_breakdowns.creative", "Créative"),
                              ["Toutes"] + ads_f['ad_name'].tolist(), key="bd_ad",
                              format_func=_all_f)
        ad_id = (ads_f[ads_f['ad_name'] == ad_sel]['ad_id'].iloc[0]
                 if ad_sel != "Toutes" else None)

        # Grain = deepest specific level chosen.
        if ad_id is not None:
            grain_key, entity_col, entity_val, entity_label = "ad", "ad_id", ad_id, ad_sel
        elif adset_id is not None:
            grain_key, entity_col, entity_val, entity_label = "adset", "adset_id", adset_id, adset_sel
        elif camp_sel != "Toutes":
            grain_key, entity_col, entity_val, entity_label = "campaign", "campaign_name", camp_sel, camp_sel
        else:
            grain_key, entity_col, entity_val, entity_label = (
                "campaign", None, None, t("meta_breakdowns.all_campaigns", "Toutes campagnes"))

        st.caption(t(
            "meta_breakdowns.grain_caption",
            "Grain courant : **{grain}** · données agrégées sur tout "
            "l'historique (pas de filtre par période)."
        ).format(grain=t(f"meta_breakdowns.grain.{grain_key}", _GRAIN_FR[grain_key])))

        table = _table_name(family, grain_key, dim_key)
        params = [artist_id]
        where_entity = ""
        if entity_val is not None:
            where_entity = f" AND {entity_col} = %s"
            params.append(entity_val)

        dim_cols = ", ".join(_DIMS[dim_label][1])
        if family == "performance":
            metrics = "SUM(spend) AS spend, SUM(results) AS results, " \
                      "SUM(impressions) AS impressions, SUM(reach) AS reach"
        else:
            metrics = ", ".join(f"SUM({c}) AS {c}" for c in _ENG_COLS)
        df = db.fetch_df(
            f"SELECT {dim_cols}, {metrics} FROM {table} "
            f"WHERE artist_id = %s{where_entity} GROUP BY {dim_cols}",
            tuple(params),
        )
    finally:
        db.close()

    if df is None or df.empty:
        st.info(t(
            "meta_breakdowns.no_data",
            "Aucune donnée pour cette sélection. Si le grain est Adset/Créative, "
            "vérifiez qu'une collecte complète a bien tourné."
        ))
        return

    if family == "performance":
        _render_performance(df, dim_key, entity_label)
    else:
        _render_engagement(df, dim_key, entity_label)

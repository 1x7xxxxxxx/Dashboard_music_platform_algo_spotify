"""Vue Breakdowns Meta — pays, placement, plateforme et âge CÔTE À CÔTE, à tous les grains.

Type: Feature
Uses: get_db_connection, get_artist_id, utils.geo, utils.charts
Depends on: meta_insights_{performance,engagement}[_ad|_adset]_{country,placement,age}
Persists in: read-only

Les tables breakdown sont des AGRÉGATS sur toute la plage (pas de dimension date) :
le filtrage se fait par entité (campagne / adset / créative), pas par période.

R208 (2026-09-27) — le propriétaire : « les répartitions placement / âge / plateforme sur une
même vue ». Un sélecteur de dimension montrait une répartition à la fois, et comparer où
l'euro rend le mieux demandait de basculer trois fois. Les quatre sont lues en UNE requête
(`UNION ALL`, cliquet d'allers-retours) et dessinées en grille ; la plateforme est dérivée
de la table placement (Meta rend la plateforme avec chaque placement).
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils import view_session, charts
from src.dashboard.utils.filters import (
    account_clause,
    account_scope,
    table_carries_account,
)
from src.dashboard.utils.geo import iso2_to_iso3, iso2_to_name
from src.dashboard.utils.charts import pareto_spend_cpr
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import cpr_help, outbound_help


# Grain is derived from the deepest specific selection in the campaign→adset→ad cascade.
_GRAIN_FR = {"campaign": "Campagne", "adset": "Adset", "ad": "Créative"}

# dim_key → [dimension columns] — the three breakdown tables Meta returns.
_DIMS = {
    "country":   ["country"],
    "placement": ["platform", "placement"],
    "age":       ["age_range"],
}
# The four panels, in reading order. `platform` has no table: it is summed from placement.
_PANELS = (("country", "Pays"), ("placement", "Placement"),
           ("platform", "Plateforme"), ("age", "Âge"))
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


def _panel(df, panel: str):
    """The rows of one panel, with its display label in `dim_label`."""
    if panel == "platform":
        part = df[df['dim'] == "placement"].copy()
        part['k'] = part['platform'].fillna('?')
        num = [c for c in part.columns if c not in ('dim', 'k', 'platform', 'dim_label')
               and pd.api.types.is_numeric_dtype(part[c])]
        part = part.groupby('k', as_index=False)[num].sum(min_count=1)
    else:
        part = df[df['dim'] == panel].copy()
    if panel == "country":
        part['dim_label'] = part['k'].map(iso2_to_name).fillna(part['k'])
    elif panel == "placement":
        # « feed » exists on Facebook AND Instagram: without its platform, two placements
        # share one bar and the CPR line zigzags between them (seen on the render).
        # Meta repeats the platform inside the placement (« instagram_reels »): drop it,
        # the label would otherwise overflow the half-width panel.
        plat, place = part['platform'].fillna('?'), part['k'].fillna('?')
        part['dim_label'] = [f"{p} / {q[len(p) + 1:] if q.startswith(p + '_') else q}"
                             for p, q in zip(plat, place)]
    else:
        part['dim_label'] = part['k'].fillna('?')
    return part


def _render_performance(df):
    df = df.copy()
    for c in ('spend', 'results', 'impressions', 'reach'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    # The tiles read ONE dimension (country): the four breakdowns cover the same spend,
    # so summing all panels would count every euro up to four times.
    base = df[df['dim'] == "country"]
    if base.empty:
        base = df[df['dim'] == df['dim'].iloc[0]]
    total_spend, total_res = base['spend'].sum(), base['results'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric(t("meta_breakdowns.total_spend", "Dépense totale"), f"{total_spend:,.2f} €")
    # R146 — « Résultats » nommait un clic sortant comme un aboutissement.
    c2.metric(t("meta_breakdowns.results", "Clics sortants"), f"{int(total_res):,}",
              help=outbound_help())
    c3.metric(t("meta_breakdowns.avg_cpr", "CPR moyen"),
              f"{total_spend / total_res:,.2f} €" if total_res else "—",
              help=cpr_help())

    for row in (_PANELS[:2], _PANELS[2:]):
        cols = st.columns(2)
        for col, (panel, label) in zip(cols, row):
            with col:
                fig = pareto_spend_cpr(
                    _panel(df, panel), 'dim_label',
                    t(f"meta_breakdowns.dim.{panel}", label), top_n=8)
                if fig is None:
                    st.caption(t("meta_breakdowns.panel_empty",
                                 "{dim} — aucune donnée sur cette sélection.").format(
                                     dim=t(f"meta_breakdowns.dim.{panel}", label)))
                else:
                    fig.update_layout(height=360, margin={'t': 40, 'l': 60, 'r': 60, 'b': 90})
                    charts.plotly_chart(fig, width="stretch")

    geo = _panel(df, "country")
    geo['iso3'] = geo['k'].map(iso2_to_iso3)
    geo = geo.dropna(subset=['iso3'])
    if not geo.empty:
        # R246 (fiches 25-27) : sur la même vue que placement, âge, plateforme — dépliée.
        st.markdown("**" + t("meta_breakdowns.map", "🗺️ Carte de la dépense par pays") + "**")
        with st.container():
            fig = px.choropleth(
                geo, locations='iso3', color='spend', hover_name='dim_label',
                color_continuous_scale='YlOrRd',
                labels={'spend': t("meta_breakdowns.spend_eur", "Dépense (€)")},
            )
            fig.update_layout(margin={'l': 0, 'r': 0, 't': 10, 'b': 0},
                              geo={'showframe': False})
            charts.plotly_chart(fig, width="stretch")


def _render_engagement(df):
    df = df.copy()
    for c in _ENG_COLS:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    df['total'] = df[_ENG_COLS].sum(axis=1)
    if df['total'].sum() == 0:
        st.info(t("meta_breakdowns.no_engagement", "Aucune interaction d'engagement sur cette sélection."))
        return
    var_col = t("meta_breakdowns.type", "Type")
    val_col = t("meta_breakdowns.volume", "Volume")
    for row in (_PANELS[:2], _PANELS[2:]):
        cols = st.columns(2)
        for col, (panel, label) in zip(cols, row):
            part = _panel(df, panel)
            part['total'] = part[_ENG_COLS].sum(axis=1)
            part = part[part['total'] > 0].sort_values('total', ascending=False).head(8)
            with col:
                if part.empty:
                    st.caption(t("meta_breakdowns.panel_empty",
                                 "{dim} — aucune donnée sur cette sélection.").format(
                                     dim=t(f"meta_breakdowns.dim.{panel}", label)))
                    continue
                melted = part.melt(id_vars='dim_label', value_vars=_ENG_COLS,
                                   var_name=var_col, value_name=val_col)
                fig = px.bar(melted, y='dim_label', x=val_col, color=var_col,
                             orientation='h',
                             title=t(f"meta_breakdowns.dim.{panel}", label),
                             labels={'dim_label': ''})
                fig.update_layout(barmode='stack', height=340,
                                  legend={'orientation': 'h', 'y': -0.2},
                                  margin={'t': 40, 'l': 10, 'r': 10})
                charts.plotly_chart(fig, width="stretch")

    geo = _panel(df, "country")
    geo['iso3'] = geo['k'].map(iso2_to_iso3)
    geo = geo.dropna(subset=['iso3'])
    if not geo.empty:
        # R246 (fiches 25-27) : sur la même vue que placement, âge, plateforme — dépliée.
        st.markdown("**" + t("meta_breakdowns.map_engagement", "🗺️ Carte des interactions par pays") + "**")
        with st.container():
            fig = px.choropleth(geo, locations='iso3', color='total', hover_name='dim_label',
                                color_continuous_scale='Blues',
                                labels={'total': t("meta_breakdowns.interactions", "Interactions")})
            fig.update_layout(margin={'l': 0, 'r': 0, 't': 10, 'b': 0}, geo={'showframe': False})
            charts.plotly_chart(fig, width="stretch")


def show() -> None:
    # Gratuite depuis le 2026-09-26 (ADR-029) : cette page lit tes données, elle ne prédit
    # rien. Le verrou `require_plan('premium')` est retiré avec la ligne de `_FREE_FEATURES`.

    st.title(t("meta_breakdowns.title", "🌍 Breakdowns Meta"))
    st.caption(t(
        "meta_breakdowns.subtitle",
        "Pays, placement, plateforme et âge côte à côte, à tous les grains (campagne · adset · créative). "
        "Données agrégées sur tout l'historique — **pas de filtre par période** "
        "(les breakdowns Meta n'ont pas de dimension date)."
    ))

    family_label = st.selectbox(
        t("meta_breakdowns.metric", "Métrique"), list(_FAMILIES.keys()),
        format_func=lambda lbl: t(f"meta_breakdowns.family.{_FAMILIES[lbl]}", lbl))
    family = _FAMILIES[family_label]

    with view_session() as (db, artist_id):
        _acct, _acct_params = account_clause(
            account_scope(db, artist_id, key="meta_breakdowns_acct"))

        # Entities listed most-recent-first (last launched on top), via each table's
        # recency column — start_time for campaigns/adsets, created_time for ads.
        camps = db.fetch_df(
            "SELECT campaign_id, campaign_name FROM meta_campaigns "
            f"WHERE artist_id = %s{_acct} AND campaign_name IS NOT NULL "
            "ORDER BY start_time DESC NULLS LAST, campaign_name",
            (artist_id, *_acct_params),
        )
        adsets = db.fetch_df(
            "SELECT adset_id, adset_name, campaign_id FROM meta_adsets "
            f"WHERE artist_id = %s{_acct} AND adset_name IS NOT NULL "
            "ORDER BY start_time DESC NULLS LAST, adset_name",
            (artist_id, *_acct_params),
        )
        ads = db.fetch_df(
            "SELECT ad_id, ad_name, adset_id, campaign_id FROM meta_ads "
            f"WHERE artist_id = %s{_acct} AND ad_name IS NOT NULL "
            "ORDER BY created_time DESC NULLS LAST, ad_name",
            (artist_id, *_acct_params),
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
            "Grain courant : **{grain}** ({entity}) · données agrégées sur tout "
            "l'historique (pas de filtre par période)."
        ).format(grain=t(f"meta_breakdowns.grain.{grain_key}", _GRAIN_FR[grain_key]),
                 entity=entity_label))

        if family == "performance":
            metrics = "SUM(spend) AS spend, SUM(results) AS results, " \
                      "SUM(impressions) AS impressions, SUM(reach) AS reach"
        else:
            metrics = ", ".join(f"SUM({c}) AS {c}" for c in _ENG_COLS)
        # THE THREE BREAKDOWNS IN ONE ROUND TRIP (R208). Each table is normalised to
        # (dim, k, platform, metrics…) and the three are stacked with UNION ALL: the
        # round-trip ratchet refuses one query per panel, and the four panels are read
        # together anyway.
        #
        # Les tables à la maille AD/ADSET n'ont pas `ad_account_id` (migration 076)
        # et n'en ont pas besoin : leur clé est un id Meta, globalement unique, donc
        # deux comptes ne peuvent pas y entrer en collision. Ajouter le prédicat
        # quand même ferait échouer la requête sur « colonne inconnue ».
        parts, params = [], []
        for dim_key, dim_cols in _DIMS.items():
            table = _table_name(family, grain_key, dim_key)
            _acct_tbl = _acct if table_carries_account(table) else ""
            k_expr = ("placement" if dim_key == "placement" else dim_cols[0])
            p_expr = "platform" if dim_key == "placement" else "NULL::text"
            where_entity = f" AND {entity_col} = %s" if entity_val is not None else ""
            parts.append(
                f"SELECT '{dim_key}'::text AS dim, {k_expr}::text AS k, {p_expr} AS platform, "
                f"{metrics} FROM {table} "
                f"WHERE artist_id = %s{_acct_tbl}{where_entity} GROUP BY {', '.join(dim_cols)}")
            params += [artist_id, *(_acct_params if _acct_tbl else ())]
            if entity_val is not None:
                params.append(entity_val)
        inner = " UNION ALL ".join(parts)
        # La dépense TOTALE voyage dans la même requête, en sous-requête scalaire.
        #
        # Elle lit `v_meta_spend_totals` (migration 101), la définition OR de la
        # dépense, et non la table brute — « combien a-t-on dépensé » est une règle
        # métier. La sous-requête est posée AUTOUR des agrégats, pas dedans.
        if family == "performance":
            sql = (f"SELECT b.*, "
                   f"(SELECT COALESCE(SUM(spend), 0) FROM v_meta_spend_totals "
                   f" WHERE artist_id = %s{_acct}) AS _spend_total, "
                   f"(SELECT COALESCE(SUM(results), 0) FROM v_meta_spend_totals "
                   f" WHERE artist_id = %s{_acct}) AS _results_total "
                   f"FROM ({inner}) b")
            args = (tuple(params) + (artist_id, *_acct_params)
                    + (artist_id, *_acct_params))
        else:
            sql, args = inner, tuple(params)
        df = db.fetch_df(sql, args)

    if df is None or df.empty:
        st.info(t(
            "meta_breakdowns.no_data",
            "Aucune donnée pour cette sélection. Si le grain est Adset/Créative, "
            "vérifiez qu'une collecte complète a bien tourné."
        ))
        return

    if family == "performance":
        # Coverage is judged on ONE breakdown (country): every panel covers the same
        # spend, so summing the four would count each euro up to four times.
        _render_coverage(df[df['dim'] == "country"])
        _render_performance(
            df.drop(columns=["_spend_total", "_results_total"], errors="ignore"))
    else:
        _render_engagement(df)


def _render_coverage(df) -> None:
    """Quelle PART de la dépense cette ventilation couvre, mesurée à chaque rendu.

    Meta n'attribue pas toute la dépense à une dimension : les impressions dont il
    ignore le pays, l'âge ou le placement n'apparaissent dans aucune ligne du
    breakdown. Mesuré en production le 2026-09-11 sur l'artiste 1 : **2 348 €** dans
    la ventilation par pays contre **3 088 €** de dépense totale — **76 %**, et les
    ventilations par âge et par placement tombent sur la même part.

    Ce n'est pas notre défaut, c'est celui de la source. Ce qui SERAIT notre défaut,
    c'est de ne pas le dire : le lecteur qui additionne les barres trouve 740 € de
    moins que le chiffre de l'onglet d'à côté, et ce dépôt a déjà payé trois fois
    pour deux nombres sans explication.

    La part est RECALCULÉE, jamais écrite en dur : elle dépend du compte, de la
    campagne et de la période collectée, et une constante deviendrait fausse à la
    première nouvelle campagne.
    """
    parts = []
    for col, total_col, unit in (("spend", "_spend_total", " €"),
                                 ("results", "_results_total", "")):
        if col not in df.columns or total_col not in df.columns:
            continue
        shown = float(df[col].fillna(0).sum())
        total = float(df[total_col].iloc[0] or 0)
        if total <= 0 or shown <= 0 or shown >= total * 0.995:
            continue
        parts.append(t(
            "meta_breakdowns.coverage_part",
            "**{shown}{unit}** sur **{total}{unit}** ({pct} %)"
        ).format(shown=f"{shown:,.0f}".replace(",", "\u202f"),
                 total=f"{total:,.0f}".replace(",", "\u202f"),
                 unit=unit, pct=f"{100 * shown / total:.0f}"))
    if not parts:
        return
    st.caption(t(
        "meta_breakdowns.coverage",
        "ⓘ Cette ventilation porte {parts}. Meta n'attribue pas tout à une "
        "dimension — les impressions dont il ignore le pays, l'âge ou le placement "
        "ne sont dans aucune barre. L'écart n'est pas une donnée manquante de notre "
        "côté."
    ).format(parts=" et ".join(parts)))

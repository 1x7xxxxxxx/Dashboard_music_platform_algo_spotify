from dataclasses import dataclass
from typing import Callable

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils import view_session, charts
from src.dashboard.utils.filters import account_clause
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import disclosure_caption
from src.dashboard.utils.ratios import per
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.campaign_pair import day0_cumulative, render_day0
from src.dashboard.utils.meta_filter_bar import (
    BAR_FULL, BAR_UNDATED, MetaFilters, filter_bar,
    say_instagram_is_outside)

def _render_scope_notice(db, artist_id) -> None:
    """Ce que CE compte permet de répondre, et ce qu'il ne permet pas. Mesuré.

    Arbitrage R107 §3, tranché le 2026-09-14. La question posée était « faut-il faire
    apparaître les 24 % de dépense que Meta n'attribue à aucune dimension ». La mesure
    a déplacé la question : la couverture des breakdowns est DÉJÀ recalculée et
    expliquée à chaque rendu (`meta_breakdowns._render_coverage`), alors qu'un trou
    plus grand n'était dit nulle part.

    Mesuré sur l'artiste 1 le 2026-09-14 : **zéro** campagne rattachée à un titre,
    quand six plateformes sur sept portent leurs onze titres liés. La section ne peut
    donc pas répondre à « combien ce titre m'a coûté » — et rien ne le disait. Un
    lecteur qui voit des campagnes nommées comme ses morceaux suppose l'inverse.

    Le compte vient de `v_meta_track_attribution` (migration 116) : le prédicat qui
    décide qu'un lien compte est une règle métier, pas une requête d'affichage.

    Le constat est CALCULÉ par locataire, jamais écrit en dur : un artiste dont les
    campagnes sont rattachées doit lire l'autre phrase, pas celle-ci. C'est la même
    règle que la couverture des breakdowns — une constante deviendrait fausse à la
    première campagne étiquetée.
    """
    row = db.fetch_query(
        "SELECT COALESCE(SUM(spend), 0), MIN(first_day), MAX(last_day) "
        "FROM v_meta_spend_totals WHERE artist_id = %s", (artist_id,))
    if not row or not row[0] or not row[0][2]:
        return                     # aucune dépense connue : rien à cadrer
    spend, first_day, last_day = float(row[0][0] or 0), row[0][1], row[0][2]

    # `v_meta_track_attribution` (migration 116), pas deux COUNT(*) ici. La première
    # version lisait `track_platform_link` en brut et le cliquet du bronze l'a
    # refusée dans l'heure — à raison : « rattachable » est une définition métier
    # (quel statut de lien compte, comment on rapproche une campagne d'un lien), et
    # une définition écrite dans une page diverge de celle écrite dans la suivante.
    attrib = db.fetch_query(
        "SELECT campaigns, linked_campaigns FROM v_meta_track_attribution "
        "WHERE artist_id = %s", (artist_id,))
    campaigns, linked = (attrib[0][0], attrib[0][1]) if attrib else (0, 0)

    # L'espace fine sur le SEUL nombre. Appliquée à la phrase entière, elle mangeait
    # aussi la virgule de « campagne(s), du … » — un remplacement de séparateur qui
    # déborde sur la ponctuation est la version typographique du garde textuel.
    period = t("meta_ads_overview.scope_period",
               "**{spend} €** sur **{campaigns}** campagne(s), du {start} au {end}."
               ).format(spend=f"{spend:,.0f}".replace(",", "\u202f"),
                        campaigns=campaigns,
                        start=format_date(first_day) if first_day else "?",
                        end=format_date(last_day))

    if linked:
        answer = t("meta_ads_overview.scope_linked",
                   " **{linked}** campagne(s) sont rattachées à un titre : le coût par "
                   "titre est lisible pour celles-là, et pour elles seules.")\
            .format(linked=linked)
    else:
        answer = t("meta_ads_overview.scope_unlinked",
                   " Aucune campagne n'est rattachée à un titre — cette section répond "
                   "donc à « combien ai-je dépensé, et qui cela a-t-il touché », pas à "
                   "« combien ce titre m'a coûté ». Un nom de campagne qui ressemble à "
                   "un morceau n'est pas un rattachement.")

    st.caption(f"ⓘ {period}{answer}")


# R378 (V8, V29, V30, V35, V36, V70 — owner's screen review, 2026-10-05): ONE page, the
# « 🔀 Vue croisée », carries every reading that crosses two sources as a section. R476
# (owner W13, W2, W5, W6, W7, W11 — ADR-032) made it the whole funnel: the releases (from
# Hypeddit, Spotify and Apple Music) and the revenue (from the distributors) joined it, and
# the sections became a REGISTRY — `Section(label, render, bar)`, where `bar` is the set of
# filters the section reads (`meta_filter_bar.BAR_*`), so the bar draws those and states
# the rest instead of guessing from a section name. The page key stays
# `meta_ads_overview`: it is the Free-plan key (`stripe_schema._FREE_FEATURES`), so no plan
# or migration moves. A segmented control rather than `st.tabs`: tabs run every body on
# each rerun — one section is rendered at a time. The old routes are aliases to this page
# and open the section they named.


@dataclass(frozen=True)
class Section:
    label: Callable[[], str]
    render: Callable[..., None]          # (db, artist_id, bar: MetaFilters | None)
    bar: frozenset[str] | None           # None = no bar at all (Instagram, organic)


# R554 (ADR-033 decision 2, owner's Y2 of 2026-10-13) — seven sections became five, read
# top to bottom: WHEN (chronology), HOW MUCH at each step (funnel), WHICH creative and
# setting, WHO (audiences), and the organic side. A section answers one question; the
# figures that answered none left with the commit (fiches 27, 30, 32, 34).


def _render_chrono(db, artist_id, bar: MetaFilters) -> None:
    """📈 Chronologie — R555: ONE figure on the calendar (fiches 42, 43, 29), then the
    effect of each campaign (fiche 28) and the releases at equal age (fiches 2, 6): age is
    another x axis, so it is another figure (ADR-033)."""
    from src.dashboard.views.spotify_s4a_combined import render_release_cohort

    _render_timeline(db, artist_id, bar)
    _render_effect_duration(db, artist_id)
    st.markdown("---")
    render_release_cohort(db, " AND artist_id = %s", (artist_id,), overlays=True,
                          key="cross_release_pick", log_days=True)


def _render_timeline(db, artist_id, bar: MetaFilters) -> None:
    """The one chronology (R555), with the verdict on the last campaign above it."""
    import datetime as _dt

    from src.dashboard.utils import chronology, meta_impact

    st.subheader(t("meta_ads_overview.timeline_header",
                   "📈 Tout sur une seule horloge — pub, écoutes, audience"))
    scope_sql, scope_params, _ = _campaign_scope(bar)
    frames = chronology.load(db, artist_id, scope_sql, scope_params)
    camps = meta_impact.campaigns(frames["all_spend"])
    aud = frames["audience"]
    if camps and not aud.empty:
        listeners = pd.Series(pd.to_numeric(aud["listeners"], errors="coerce").values,
                              index=pd.to_datetime(aud["day"])).dropna()
        st.markdown(f"**{meta_impact.verdict(listeners, camps, _dt.date.today()).text}**")
    fig = chronology.figure(frames, chronology.default_range(frames, bar.window))
    if fig is None:
        st.info(t("meta_ads_overview.no_time_data", "Pas de données temporelles."))
        return
    charts.plotly_chart(fig, width="stretch")


def _render_effect_duration(db, artist_id) -> None:
    """Fiche 28, redefined (R555): the streams around EACH campaign's first euro, one
    curve per campaign — how long an effect lasts, hence when to judge and relaunch.

    The owner did not read « vague de 2 / 3 campagnes » (2026-10-13): the grouping is
    gone from the screen. Overlapping campaigns share the same days, so their curves
    share the same streams — the caption says it, as an association, not a cause."""
    fig, dropped = _effect_figure(db, artist_id)
    if fig is None:
        return
    with secondary_analyses(t("meta_ads_overview.effect_header",
                              "⏱️ Combien de temps dure l'effet de chaque campagne"),
                            expanded=False):
        charts.plotly_chart(fig, width="stretch")
        st.caption(t(
            "meta_ads_overview.effect_caption",
            "Une courbe par campagne, calée sur son premier euro (jour 0). 100 = la moyenne "
            "des écoutes Spotify des 28 jours avant elle ; la courbe dit combien de jours "
            "elle reste au-dessus. Une courbe qui monte AVANT le jour 0 est une sortie, pas "
            "la pub. Deux campagnes qui tournent en même temps partagent les mêmes écoutes : "
            "c'est une association, pas la preuve que chacune les a causées. {d} campagne(s) "
            "sans base mesurée (moins de 10 écoutes par jour avant elle) ne sont pas "
            "tracées.").format(d=dropped))


_EFFECT_SHOWN = 5   # the latest campaigns drawn on arrival; older ones wait in the legend


def _effect_figure(db, artist_id) -> tuple[go.Figure | None, int]:
    """(figure, campaigns left out) — `meta_impact.event_study`, one start per campaign."""
    from src.dashboard.utils import meta_impact
    from src.dashboard.utils.platform_colors import DISTINCT

    spend = db.fetch_df("SELECT ad_account_id, campaign_name, day, spend FROM v_meta_daily "
                        "WHERE artist_id = %s", (artist_id,))
    streams = db.fetch_df("SELECT day, SUM(streams) AS streams FROM v_s4a_song_daily "
                          "WHERE artist_id = %s AND song NOT ILIKE %s GROUP BY day",
                          (artist_id, "%1x7xxxxxxx%"))
    if spend.empty or streams.empty:
        return None, 0
    series = streams.set_index(pd.to_datetime(streams["day"]))["streams"].astype(float)
    camps = meta_impact.campaigns(spend)
    es = meta_impact.event_study(
        series, [(f"{c.name} · {format_date(c.start)}", c.start) for c in camps])
    if es.empty:
        return None, len(camps)
    labels = list(dict.fromkeys(es["wave"]))
    fig = go.Figure()
    for i, lab in enumerate(labels):
        g = es[es["wave"] == lab]
        fig.add_trace(go.Scatter(
            x=g["offset"], y=g["index"], mode="lines", name=lab,
            visible=True if i >= len(labels) - _EFFECT_SHOWN else "legendonly",
            line=dict(color=DISTINCT[i % len(DISTINCT)], width=2)))
    fig.add_hline(y=100, line_dash="dot", line_color="#999")
    fig.add_vline(x=0, line_dash="dash", line_color="#999")
    fig.update_layout(
        height=380,
        xaxis_title=t("meta_ads_overview.effect_x", "jours depuis le premier euro de la campagne"),
        yaxis_title=t("meta_ads_overview.effect_y", "écoutes / jour (100 = les 28 jours avant)"))
    return fig, len(camps) - len(labels)


def _render_funnel_section(db, artist_id, bar: MetaFilters) -> None:
    """🛤️ Entonnoir — budget → impressions → clicks → smart link → platforms → streams →
    revenue (R556), then the totals per campaign, the comparison and the agency accounts.
    The Hypeddit campaigns compared (fiches 22, 23) left: two campaigns in the bar draw
    two funnels side by side."""
    from src.dashboard.utils.campaign_compare import render as render_compare
    from src.dashboard.views.meta_extra_accounts import render_extra_ad_accounts
    from src.dashboard.views.meta_x_spotify import render_funnel

    render_funnel(db, artist_id, bar)
    st.markdown("---")
    _render_campaign_totals(db, artist_id, bar)
    render_compare(db, artist_id, *bar.acct())
    st.markdown("---")
    # Les comptes d'agence se déclarent ICI depuis le 2026-09-05, plus dans
    # Credentials : cette page répond à « que veux-tu suivre », l'autre à
    # « comment te connecter ».
    render_extra_ad_accounts(db, artist_id)


def _render_creatives(db, artist_id, bar: MetaFilters) -> None:
    from src.dashboard.views.meta_creatives import render as render_creatives
    render_creatives(db, artist_id, bar)
    # R568 — the goal Pareto left: the « Optimisation de l'ad set » panel of best_settings
    # (meta_creatives._ad_setting_panels) reads the same view.


def _render_audiences(db, artist_id, bar: MetaFilters) -> None:
    from src.dashboard.views.meta_breakdowns import render as render_breakdowns
    from src.dashboard.views.meta_x_spotify import render_countries
    render_breakdowns(db, artist_id, bar)
    # « Par pays » — who saw the ads, where, against the streams of that country.
    st.markdown("---")
    render_countries(db, artist_id, *bar.acct())


def _render_instagram(db, artist_id, bar: None) -> None:
    say_instagram_is_outside()
    from src.dashboard.views.instagram import render as render_instagram
    render_instagram(db, artist_id)


SECTIONS: dict[str, Section] = {
    "chrono": Section(lambda: t("meta_ads_overview.section_chrono", "📈 Chronologie"),
                      _render_chrono, BAR_FULL),
    "entonnoir": Section(lambda: t("meta_ads_overview.section_funnel", "🛤️ Entonnoir"),
                         _render_funnel_section, BAR_FULL),
    "creas": Section(lambda: t("meta_ads_overview.section_creas", "🎨 Créas & réglages"),
                     _render_creatives, BAR_FULL),
    "audiences": Section(lambda: t("meta_ads_overview.section_audiences", "🌍 Audiences"),
                         _render_audiences, BAR_UNDATED),
    "instagram": Section(lambda: t("meta_ads_overview.section_instagram", "📸 Instagram"),
                         _render_instagram, None),
    # R553 (ADR-033 decision 1) : « 💶 Revenus » left for the Trésorerie page (`imusician`).
}
DEFAULT_SECTION = "entonnoir"
# The old page key → the section it used to be. Read on arrival only, so a click on the
# control afterwards is never overridden.
ALIAS_SECTION = {"meta_x_spotify": "entonnoir", "meta_creatives": "creas",
                 "meta_breakdowns": "audiences", "instagram": "instagram"}
SECTION_KEY = "meta_overview_section"


def _section_label(key: str) -> str:
    return SECTIONS[key].label()


def arrival_section(alias: str | None) -> str | None:
    """The section an old page key opens — app.py sets the alias on the arriving run only,
    so a click on the control afterwards is never overridden."""
    return ALIAS_SECTION.get(alias) if alias else None


def show(section: str | None = None):
    """`section` opens that section on a fresh session — the former pages' `show()`."""
    st.title(t("meta_ads_overview.title_cross",
               "🔀 Vue croisée — Meta × Hypeddit × Spotify × Insta × Shazam × Revenus"))
    from src.dashboard.routes import ALIAS_ARRIVAL_KEY

    landing = arrival_section(st.session_state.get(ALIAS_ARRIVAL_KEY))
    # The default goes through the state, not `default=`: a widget given both warns on
    # screen (« created with a default value but also had its value set »).
    if landing:
        st.session_state[SECTION_KEY] = landing
    if st.session_state.get(SECTION_KEY) not in SECTIONS:
        st.session_state[SECTION_KEY] = section if section in SECTIONS else DEFAULT_SECTION
    section = st.segmented_control(
        t("meta_ads_overview.section", "Vue"), list(SECTIONS),
        format_func=_section_label, key=SECTION_KEY) or DEFAULT_SECTION

    # R399 — ONE connection, opened here and handed to the section (rule 9); declared for
    # the creatives' fragments (`fragment_db`). ONE filter bar, read by every section.
    from src.dashboard.utils.fragment_db import page_db_scope

    entry = SECTIONS[section]
    with view_session() as (db, artist_id), page_db_scope(db, artist_id):
        bar = None
        if entry.bar is not None:
            bar = filter_bar(db, artist_id, entry.bar)
            _render_glossary()
            st.markdown("---")
        entry.render(db, artist_id, bar)


# R554 — the owner asked what five words of this page mean (2026-10-13). Each is written
# ONCE here, folded under the filter bar of every Meta section, never on a chart.
_GLOSSARY = (
    ("clic_sortant", "**Clic sortant** — le clic qui quitte ton smart link Hypeddit vers une "
     "plateforme (Spotify, Apple…). Hypeddit le renvoie à Meta par sa CAPI : c'est le "
     "« résultat » du CPR."),
    ("frequence", "**Fréquence** — impressions ÷ personnes touchées : combien de fois, en "
     "moyenne, une même personne a vu la pub."),
    ("engagement", "**Engagement** — réactions + commentaires + partages + enregistrements "
     "sur la pub."),
    ("etape", "**% de l'étape d'avant** — la part des gens de l'étape précédente qui ont "
     "atteint celle-ci (1,1 % = 11 sur 1 000)."),
    ("cout_unitaire", "**Coût à l'unité** — la dépense divisée par le nombre à cette étape "
     "(0,127 € l'unité = 1 € pour ~8 clics)."),
    ("cpr", "**CPR** — coût par résultat : dépense ÷ clics sortants."),
)


def _render_glossary() -> None:
    with st.expander(t("meta_ads_overview.glossary", "📖 Les mots de cette page"),
                     expanded=False):
        st.markdown("\n".join(f"- {t(f'meta_ads_overview.gloss.{k}', fr)}"
                               for k, fr in _GLOSSARY))


def _nan(v):
    """The panels draw NaN as a gap; `per` says « undefined » with None."""
    return float("nan") if v is None else v


# Les six mesures de la performance globale. (libellé, colonne ou calcul, format)
# `derive` reçoit la ligne agrégée d'une campagne et rend le ratio — jamais une
# moyenne de ratios : un CPM est `Σdépense / Σimpressions × 1000`, pas la moyenne
# des CPM quotidiens.
_PERF_PANNEAUX = [
    ("Dépenses (€)",  lambda r: r['spend'],                                      "{:,.0f}"),
    ("Impressions",   lambda r: r['impressions'],                                "{:,.0f}"),
    ("Clics lien",    lambda r: r['link_clicks'],                                "{:,.0f}"),
    # R258 — the ratios come from ONE definition (`utils.ratios.per`), NaN when undefined.
    ("CPM (€)",       lambda r: _nan(per(r['spend'], r['impressions'], 1000)),    "{:,.2f}"),
    ("CPC (€)",       lambda r: _nan(per(r['spend'], r['link_clicks'])),          "{:,.2f}"),
    # R146 — « CPR » garde le mot de Meta (l'artiste le retrouve tel quel dans le
    # Gestionnaire de publicités) mais ne voyage plus jamais sans sa limite : la
    # légende sous la figure dit que le résultat est un clic sortant.
    ("CPR (€)",       lambda r: _nan(per(r['spend'], r['custom_conversions'])),   "{:,.2f}"),
]


def _perf_pies(d: pd.DataFrame, court: list[str]) -> go.Figure:
    """Three pies — spend, impressions, link clicks — one slice per campaign (R567)."""
    from plotly.subplots import make_subplots

    from src.dashboard.utils.platform_colors import DISTINCT
    vols = _PERF_PANNEAUX[:3]
    fig = make_subplots(rows=1, cols=3, specs=[[{"type": "domain"}] * 3],
                        subplot_titles=[t(f"meta_ads_overview.perf.{i}", lab)
                                        for i, (lab, _f, _fmt) in enumerate(vols)])
    colors = [DISTINCT[i % len(DISTINCT)] for i in range(len(court))]
    for i, (lab, calc, _fmt) in enumerate(vols):
        fig.add_trace(go.Pie(
            labels=court, values=[float(calc(r)) for _, r in d.iterrows()], hole=0.35,
            sort=False, marker={"colors": colors}, textinfo="value",
            texttemplate="%{value:,.0f}", hovertemplate=f"%{{label}}<br>{lab} : "
            "%{value:,.0f} (%{percent})<extra></extra>", showlegend=i == 0), 1, i + 1)
    fig.update_layout(height=360, margin={'l': 10, 'r': 10, 't': 60, 'b': 20})
    return fig


def _perf_costs(d: pd.DataFrame, court: list[str]) -> go.Figure:
    """CPM, CPC, CPR per campaign — grouped bars, cheapest CPR on the left (R567)."""
    costs = _PERF_PANNEAUX[3:]
    vals = {lab: [float(calc(r)) for _, r in d.iterrows()] for lab, calc, _f in costs}
    order = sorted(range(len(court)), key=lambda i: (pd.isna(vals[costs[2][0]][i]),
                                                     vals[costs[2][0]][i]))
    fig = go.Figure()
    for j, (lab, _calc, fmt) in enumerate(costs):
        ys = [vals[lab][i] for i in order]
        fig.add_trace(go.Bar(
            x=[court[i] for i in order], y=ys,
            name=t(f"meta_ads_overview.perf.{j + 3}", lab), marker_color=_COST_INK[j],
            text=[fmt.format(v).replace(",", " ") if pd.notna(v) else "—" for v in ys],
            textposition="outside", cliponaxis=False))
    fig.update_layout(barmode="group", height=360, yaxis_title="€",
                      margin={'l': 10, 'r': 10, 't': 30, 'b': 20})
    return fig


_COST_INK = ("#9E9E9E", "#616161", "#212121")   # CPM, CPC, CPR — one grey ramp, one unit


def _render_global_perf(df_perf: pd.DataFrame) -> None:
    """La performance globale, CAMPAGNE PAR CAMPAGNE (R567 : camemberts, plus de barres).

    Owner, 2026-10-15: « les barres → des camemberts par campagne ». The three VOLUMES
    (€, impressions, clicks) are shares of a whole: one pie each, a slice per campaign,
    the real value written on it. The three COSTS are not shares — a pie of CPMs means
    nothing — so they stay bars, cheapest campaign on the left (Pareto).
    """
    d = df_perf.dropna(subset=['campaign_name']).copy()
    if d.empty:
        return
    d = d.sort_values('spend', ascending=False)
    from src.dashboard.utils.labels import unique_short_labels
    court = unique_short_labels(d['campaign_name'].tolist(), 34)
    charts.plotly_chart(_perf_pies(d, court), width="stretch")
    charts.plotly_chart(_perf_costs(d, court), width="stretch")

    if not (d['custom_conversions'] > 0).any():
        st.caption(t("meta_ads_overview.capi_required",
                     "CPR vide : il demande la CAPI (évènements serveur) — "
                     "aucune conversion personnalisée n'est remontée ici."))
    else:
        # R146 — la limite s'affiche quand le chiffre EST là. L'ancien message ne
        # parlait que du cas vide : la seule fois où le CPR ne trompait personne.
        st.caption(disclosure_caption())


# One row per campaign from the gold view, aggregated BEFORE anything joins it (class
# `a-join-that-multiplies-the-grain`, 2026-09-26). R567: the engagement tiles and the
# summary table that joined a second frame left the page — only this query remains.
def _perf_query(campaign_in: str) -> str:
    """Performance per campaign, from the gold view: one row per campaign_name."""
    return (
        "SELECT campaign_name, SUM(spend) AS spend, SUM(results) AS results, "
        "SUM(custom_conversions) AS custom_conversions, SUM(lp_views) AS lp_views, "
        "SUM(impressions) AS impressions, SUM(reach) AS reach, "
        "AVG(frequency) AS frequency, SUM(link_clicks) AS link_clicks "
        f"FROM v_meta_campaign_daily WHERE artist_id = %s{campaign_in} "
        "GROUP BY campaign_name ORDER BY SUM(spend) DESC"
    )


def _render_pair_day0(db, artist_id: int, account, first: str, second: str) -> None:
    """R350 — two campaigns at a comparable scale: each on ITS day 0 (first euro spent).

    Totals of a 30 € test and a 750 € release cannot share a calendar or a bar; on one
    clock, the cumulative spend, clicks and the running CPC read side by side. The whole
    life of each campaign, NOT the period window: a window would cut one of them mid-run."""
    acct, acct_params = account_clause(account)
    daily = db.fetch_df(
        "SELECT campaign_name, day, SUM(spend) AS spend, SUM(link_clicks) AS link_clicks "
        f"FROM v_meta_campaign_daily WHERE artist_id = %s{acct} "
        "AND campaign_name IN (%s, %s) GROUP BY campaign_name, day ORDER BY day",
        (artist_id, *acct_params, first, second))
    st.markdown(t("meta_ads_overview.pair_head", "##### ⏱️ Les deux campagnes sur la même horloge"))
    st.caption(t("meta_ads_overview.pair_caption",
                 "J0 = le premier jour où chaque campagne a dépensé. Toute la vie de chaque "
                 "campagne, quel que soit le filtre de dates ; un jour de pause compte 0. Le CPC "
                 "est la dépense cumulée divisée par les clics cumulés."))
    render_day0(day0_cumulative(daily, first, second), first, second)


def _campaign_scope(bar: MetaFilters) -> tuple[str, tuple, list[str]]:
    """(SQL suffix, parameters, selected campaigns) of the page's one filter bar (R399).

    The campaign values were offered from the database and are re-checked against that
    list (CRITICAL-04: they reach SQL only as `%s` parameters, never interpolated)."""
    acct, acct_params = bar.acct()
    selected = [c for c in bar.scope if c in set(bar.campaigns)]
    win_sql, win_params = bar.window.sql_between("day")
    campaign_in = acct + (
        " AND campaign_name IN ({})".format(','.join(['%s'] * len(selected)))
        if selected else "") + win_sql
    return campaign_in, (*acct_params, *selected, *win_params), selected


def _render_campaign_totals(db, artist_id, bar: MetaFilters) -> None:
    """R554 — the totals per campaign, under the funnel: they answer « how much at each
    step », the funnel's question, not « when » (they left the daily figure)."""
    _render_scope_notice(db, artist_id)
    _campaign_in, scope_params, selected_campaigns = _campaign_scope(bar)
    params = (artist_id, *scope_params)
    # R567 — « ce que ta publicité a appris » left as a block: its cheapest age / country /
    # placement is written on the funnel step Meta measured it at (`best_by_step`).
    # ⚠️ Les totaux de cette page se calculent EN PANDAS (`df_perf['spend'].sum()`).
    # Aucun garde SQL ne peut les voir : il n'y a pas de `SUM(` dans la requête. La
    # tuile « Dépenses » affichait donc 6 165,65 € pour l'artiste 1 là où la couche
    # or en compte 3 087,82 — `meta_insights_performance` porte, en plus de ses
    # lignes quotidiennes, 21 lignes de cumul à vie d'un collecteur antérieur.
    #
    # La vue les écarte ET rend une ligne par campagne, ce que le tableau des taux
    # plus bas supposait déjà : il affichait 252 lignes pour 21 campagnes.
    df_perf = db.fetch_df(_perf_query(_campaign_in), params)

    if not df_perf.empty:
        # Nettoyage
        for c in ['spend', 'results', 'custom_conversions', 'lp_views', 'impressions', 'link_clicks']:
            df_perf[c] = pd.to_numeric(df_perf[c], errors='coerce').fillna(0)

        st.markdown(t("meta_ads_overview.global_perf", "### 🚀 Performance Globale"))
        if df_perf['campaign_name'].nunique() == 1:
            # R246 (fiche 21 « je ne comprends pas quoi lire ») : une seule campagne sur la
            # période, il n'y a RIEN à comparer — le dire au lieu de laisser chercher.
            st.info(t("meta_ads_overview.one_campaign",
                      "Une seule campagne a dépensé sur la période choisie : élargis la "
                      "période pour comparer tes campagnes entre elles."))
        _render_global_perf(df_perf)
        if len(selected_campaigns) == 2:
            _render_pair_day0(db, artist_id, bar.account, *selected_campaigns)

    st.markdown("---")

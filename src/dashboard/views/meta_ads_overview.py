from dataclasses import dataclass
from typing import Callable

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.dashboard.utils import view_session, charts
from src.dashboard.utils.platform_colors import platform_color
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
                          key="cross_release_pick")


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
    st.caption(t("meta_ads_overview.timeline_caption",
                 "Clique une série dans la légende pour l'afficher ou la masquer. L'aire "
                 "orange est le budget Meta dépensé chaque jour (axe € à droite) : là où elle "
                 "est, la pub tournait. Un **clic sortant** est un clic sur un bouton de ton "
                 "smart link Hypeddit vers une plateforme d'écoute — c'est le « résultat » "
                 "que Meta compte, et le **CPR** est le budget divisé par ces clics. Les flux "
                 "Spotify sont des moyennes sur 7 jours ; un jour non importé reste un trou."))


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
    """🛤️ Entonnoir — budget → impressions → clicks → smart link → platforms, then the
    totals per campaign, the comparison, the Hypeddit campaigns and the agency accounts."""
    from src.dashboard.utils.campaign_compare import render as render_compare
    from src.dashboard.views.hypeddit import render_campaign_stats
    from src.dashboard.views.meta_extra_accounts import render_extra_ad_accounts
    from src.dashboard.views.meta_x_spotify import render_funnel

    render_funnel(db, artist_id, bar)
    st.markdown("---")
    _render_campaign_totals(db, artist_id, bar)
    render_compare(db, artist_id, *bar.acct())
    st.markdown("---")
    render_campaign_stats(db, artist_id)
    # Les comptes d'agence se déclarent ICI depuis le 2026-09-05, plus dans
    # Credentials : cette page répond à « que veux-tu suivre », l'autre à
    # « comment te connecter ».
    render_extra_ad_accounts(db, artist_id)


def _render_creatives(db, artist_id, bar: MetaFilters) -> None:
    from src.dashboard.views.meta_creatives import render as render_creatives
    render_creatives(db, artist_id, bar)
    _render_goal_pareto(db, artist_id, bar)


def _render_goal_pareto(db, artist_id, bar: MetaFilters) -> None:
    """The optimisation goal — the first « best setting » criterion (fiche 30 → R557).

    `v_meta_adset_daily` (migration 108) names the tenant on the whole adsets → ads →
    insights chain; the ring that read it left with fiche 30.
    """
    acct_sql, acct_params = bar.acct()
    win_sql, win_params = bar.window.sql_between("day") if bar.window else ("", ())
    df = db.fetch_df(
        "SELECT COALESCE(optimization_goal, %s) AS goal, SUM(spend) AS spend, "
        "SUM(conversions) AS results FROM v_meta_adset_daily WHERE artist_id = %s"
        f"{acct_sql}{win_sql} GROUP BY 1",
        (t("meta_ads_overview.unknown", "Inconnu"), artist_id, *acct_params, *win_params))
    fig = charts.pareto_spend_cpr(
        df, "goal", t("meta_ads_overview.goal_pareto",
                      "🎯 Objectif d'optimisation — dépense et coût par clic sortant"))
    if fig is not None:
        st.markdown("---")
        charts.plotly_chart(fig)


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


def _render_global_perf(df_perf: pd.DataFrame) -> None:
    """La performance globale, CAMPAGNE PAR CAMPAGNE — six cadres, une unité chacun.

    ⚠️ Remplace six `st.metric` qui affichaient la SOMME de la sélection. Demande
    du propriétaire le 2026-09-21 : « peut-on visualiser les datas de perf
    globales quand on compare 2 tracks avec des graphiques plutôt que des champs
    de valeur ? ».

    Il a raison au-delà de la forme : additionner deux campagnes pour en tirer un
    CPM unique répond à une question que personne ne pose. On sélectionne deux
    titres pour les COMPARER ; la somme efface exactement ce qu'on cherchait. Une
    seule campagne sélectionnée rend un cadre à une barre, qui porte sa valeur
    écrite — l'information est la même que celle de l'ancienne jauge.

    Six cadres et non six séries : des euros, des impressions, des clics et trois
    coûts n'ont ni la même unité ni le même ordre de grandeur. Le cliquet d'axes
    secondaires de ce dépôt (`_MAX_SECONDARY_AXES = 0`) dit la même chose.
    """
    from plotly.subplots import make_subplots

    d = df_perf.dropna(subset=['campaign_name']).copy()
    if d.empty:
        return
    d = d.sort_values('spend', ascending=True)          # plus gros budget EN HAUT
    noms = d['campaign_name'].tolist()
    # R209 — a cut label is a CATEGORY here: two names sharing 33 characters would
    # be one row (class a-truncated-label-that-merges-two-categories).
    from src.dashboard.utils.labels import unique_short_labels
    court = unique_short_labels(noms, 34)

    fig = make_subplots(
        rows=2, cols=3, shared_yaxes=True,
        horizontal_spacing=0.06, vertical_spacing=0.18,
        subplot_titles=[t(f"meta_ads_overview.perf.{i}", lab)
                        for i, (lab, _f, _fmt) in enumerate(_PERF_PANNEAUX)])
    for i, (lab, calc, fmt) in enumerate(_PERF_PANNEAUX):
        vals = [float(calc(r)) for _, r in d.iterrows()]
        fig.add_trace(go.Bar(
            x=vals, y=court, orientation='h', showlegend=False,
            marker={'color': platform_color("meta") if i < 3 else "#7f7f7f"},
            text=[fmt.format(v).replace(",", " ") if pd.notna(v) else "—" for v in vals],
            textposition='outside', cliponaxis=False,
            customdata=noms,
            hovertemplate=f"%{{customdata}}<br>{lab} : %{{text}}<extra></extra>",
        ), row=i // 3 + 1, col=i % 3 + 1)
        fig.update_xaxes(showticklabels=False, row=i // 3 + 1, col=i % 3 + 1)
    fig.update_layout(height=max(360, 46 * len(noms) + 220), bargap=0.3,
                      margin={'l': 10, 'r': 40, 't': 60, 'b': 20})
    fig.update_yaxes(automargin=True)
    charts.plotly_chart(fig, width="stretch")

    if not (d['custom_conversions'] > 0).any():
        st.caption(t("meta_ads_overview.capi_required",
                     "CPR vide : il demande la CAPI (évènements serveur) — "
                     "aucune conversion personnalisée n'est remontée ici."))
    else:
        # R146 — la limite s'affiche quand le chiffre EST là. L'ancien message ne
        # parlait que du cas vide : la seule fois où le CPR ne trompait personne.
        st.caption(disclosure_caption())


# ═══════════════════════════════════════════════════════════════════════════
# UNE LIGNE PAR CAMPAGNE, des deux côtés d'une jointure — 2026-09-26.
# ═══════════════════════════════════════════════════════════════════════════
# L'engagement se lisait en brut dans `meta_insights_engagement`, une ligne par
# campagne ET PAR JOUR, plus 21 lignes de cumul à vie. Trois défauts, une cause :
#
#   * fusionné sur `campaign_name` avec un cadre d'une ligne par campagne, il
#     changeait 21 campagnes en 252 lignes ; « les 12 plus dépensières »
#     dessinaient 12 copies de la même campagne (12 × 755,52 €) ;
#   * les tuiles Saves / Shares / Interactions sommaient cumuls ET jours : le
#     double exact (1 094 saves pour 547) ;
#   * le tableau récapitulatif le joignait jour × jour sous `SUM(p.spend)` :
#     24 176,64 € pour une campagne de 755,52 € (× 32).
#
# La vue or `v_meta_engagement_daily` (migration 138) écarte les cumuls ; les
# requêtes ci-dessous REGROUPENT par campagne AVANT toute jointure. Classe :
# `a-join-that-multiplies-the-grain`. Garde :
# `tests/test_a_join_never_multiplies_the_grain.py`.
_ENG_COLS = ("page_interactions", "post_reactions", "comments", "saves", "shares")


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


def _engagement_query(campaign_in: str) -> str:
    """Engagement per campaign, from the gold view: one row per campaign_name."""
    sums = ", ".join(f"SUM({c}) AS {c}" for c in _ENG_COLS)
    return (f"SELECT campaign_name, {sums} FROM v_meta_engagement_daily "
            f"WHERE artist_id = %s{campaign_in} GROUP BY campaign_name")


def _summary_query(campaign_in: str) -> str:
    """The summary table: both sides aggregated per campaign, THEN joined 1:1.

    Takes the (artist_id, *account, *campaigns) parameters twice, once per side.
    """
    # ⚠️ %% in the CTR alias: psycopg2 reads a lone % as a placeholder.
    return (
        'SELECT p.campaign_name, p.spend AS "Dépenses",'
        ' p.custom_conversions AS "Clics Hypeddit",'
        ' p.lp_views AS "Vues LP", p.link_clicks AS "Clics pub",'
        ' CASE WHEN p.custom_conversions > 0'
        '      THEN p.spend / p.custom_conversions END AS "CPR (€/clic sortant)",'
        ' p.impressions AS "Impressions",'
        ' CASE WHEN p.impressions > 0'
        '      THEN p.spend / p.impressions * 1000 END AS "CPM",'
        ' CASE WHEN p.impressions > 0'
        '      THEN p.link_clicks::numeric / p.impressions * 100 END AS "CTR (%%)",'
        ' e.saves AS "Saves", e.shares AS "Shares",'
        ' e.page_interactions AS "Interactions",'
        ' p.collected_at AS "Mise à jour"'
        " FROM (SELECT campaign_name, SUM(spend) AS spend,"
        "              SUM(custom_conversions) AS custom_conversions,"
        "              SUM(lp_views) AS lp_views, SUM(link_clicks) AS link_clicks,"
        "              SUM(impressions) AS impressions, MAX(collected_at) AS collected_at"
        "         FROM v_meta_campaign_daily"
        f"       WHERE artist_id = %s{campaign_in} GROUP BY campaign_name) p"
        f" LEFT JOIN ({_engagement_query(campaign_in)}) e"
        "        ON e.campaign_name = p.campaign_name"
        " ORDER BY p.spend DESC"
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
    window = bar.window

    # R373 (2026-10-05, V6) — « ce que ta publicité a appris » : même fenêtre que la
    # page, et toute la publicité de l'artiste — le conseil parle de ses campagnes.
    from src.dashboard.utils.period_side_metrics import period_side_metrics
    from src.dashboard.views.home_meta_advice import render_meta_advice
    _bornes = (None, None) if window.is_all_history else (window.start, window.end)
    render_meta_advice(period_side_metrics(db, artist_id, *_bornes))

    # ⚠️ Les totaux de cette page se calculent EN PANDAS (`df_perf['spend'].sum()`).
    # Aucun garde SQL ne peut les voir : il n'y a pas de `SUM(` dans la requête. La
    # tuile « Dépenses » affichait donc 6 165,65 € pour l'artiste 1 là où la couche
    # or en compte 3 087,82 — `meta_insights_performance` porte, en plus de ses
    # lignes quotidiennes, 21 lignes de cumul à vie d'un collecteur antérieur.
    #
    # La vue les écarte ET rend une ligne par campagne, ce que le tableau des taux
    # plus bas supposait déjà : il affichait 252 lignes pour 21 campagnes.
    df_perf = db.fetch_df(_perf_query(_campaign_in), params)

    df_eng = db.fetch_df(_engagement_query(_campaign_in), params)

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

        # Engagement
        if not df_eng.empty:
            for c in ['saves', 'shares', 'page_interactions']: df_eng[c] = pd.to_numeric(df_eng[c], errors='coerce').fillna(0)
            st.markdown(t("meta_ads_overview.engagement", "##### ❤️ Engagement"))
            e1, e2, e3 = st.columns(3)
            e1.metric("💾 Saves", f"{df_eng['saves'].sum():,.0f}")
            e2.metric("🔄 Shares", f"{df_eng['shares'].sum():,.0f}")
            e3.metric(t("meta_ads_overview.total_interactions", "⚡ Interactions Totales"), f"{df_eng['page_interactions'].sum():,.0f}")

    with secondary_analyses(t("meta_ads_overview.summary_table",
                              "🗃️ Tableau récapitulatif — le détail chiffré")):

        df_full = db.fetch_df(_summary_query(_campaign_in), params + params)

        if not df_full.empty:
            st.dataframe(
                df_full.style.format({
                    "Dépenses": "{:,.2f} €", "CPR": "{:,.2f} €", "CPM": "{:,.2f} €",
                    "CTR (%)": "{:,.2f}",
                    "Saves": "{:,.0f}", "Shares": "{:,.0f}", "Interactions": "{:,.0f}",
                    "Clics Hypeddit": "{:,.0f}", "Clics pub": "{:,.0f}",
                }, na_rep="—"),
                width="stretch",
            )
    st.markdown("---")

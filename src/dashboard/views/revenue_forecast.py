"""Revenue Forecast — SaaS projections + artistic revenue forecast.

Type: Feature
Depends on: artist_subscriptions, subscription_plans, imusician_monthly_revenue, saas_artists
Persists in: read-only (no writes)

Admin : 4 tabs (MRR actuel, Projection MRR, LTV & Churn, Projection Artistique)
Artist: 1 tab (Projection Artistique — own data only)
"""
import sys
from pathlib import Path
from datetime import date as _date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection, charts, require_db
from src.dashboard.utils.formats import eur, num
from src.dashboard.utils.platform_colors import DISTINCT
from src.dashboard.utils import algo_knowledge as ak
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.revenue_forecast import (
    load_subscriptions as _load_subscriptions,
    load_artist_revenues as _load_artist_revenues,
    load_artists as _load_artists,
    ltv_global,
    ltv_scenarios,
)
from src.database.stripe_schema import PLAN_CATALOG as _CAT
# L'ENSEMBLE DES STATUTS QUI COMPTENT DANS LE MRR — 2026-09-20 (R140 §16.6).
# Il était écrit en dur ICI, trois fois, pendant qu'`admin.py` et `billing.py`
# filtraient sur `'active'` seul : deux pages annonçaient deux nombres différents sous
# le même mot dès qu'un abonnement passait en `trialing`.
from src.utils.mrr import MRR_STATUSES
from src.dashboard.utils.date_format import format_date


# DB loaders + forecast math now live in src/dashboard/utils/revenue_forecast.py
# (refactor R6 — calc/UI split). Imported above; call sites unchanged via aliases.


# ─────────────────────────────────────────────
# Tab 1 — MRR Actuel
# ─────────────────────────────────────────────


def _format_ml_table(ml_df: pd.DataFrame) -> pd.DataFrame:
    """The « scores ML » table: sorted and formatted through the shared floor door. Pure.

    A floor probability (`proba_affichable` → None) prints `texte_plancher()`, never
    « 6.5% », and sorts LAST: sorting on raw floor values ranked titles on the
    calibration intercept (2026-09-26 — 33 of 33 production values on the floor).
    NULL (a model that failed to score) still prints « — ».
    """
    from src.dashboard.utils.algo_preview_data import format_proba, proba_affichable

    out = ml_df.copy()
    if 'dw_probability' in out.columns:
        key = [proba_affichable("dw", v) for v in out['dw_probability']]
        out['_sort'] = pd.to_numeric(pd.Series(key, index=out.index, dtype=object),
                                     errors='coerce')
        out = (out.sort_values('_sort', ascending=False, na_position='last')
               .drop(columns=['_sort']).reset_index(drop=True))
    for col in ['dw_probability', 'rr_probability', 'radio_probability']:
        if col in out.columns:
            algo = col.split("_", 1)[0]
            out[col] = [format_proba(algo, v, decimals=1) for v in out[col]]
    return out

def _tab_mrr(db) -> None:
    st.subheader(t("revenue_forecast.mrr_header", "MRR actuel"))

    df = _load_subscriptions(db)
    if df.empty:
        st.info(t("revenue_forecast.no_subscriptions",
                  "Aucun abonnement trouvé dans la base. Connectez Stripe pour alimenter ces données."))
        return

    active = df[df['status'].isin(MRR_STATUSES)]
    paying = active[active['price'] > 0]

    total_mrr = float(paying['price'].sum())
    nb_paying  = len(paying)
    arpu       = total_mrr / nb_paying if nb_paying else 0.0
    nb_cancel  = int(active['cancel_at_period_end'].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("revenue_forecast.mrr_total", "MRR total"), f"{total_mrr:,.2f} €")
    c2.metric("ARPU", f"{arpu:,.2f} €")
    c3.metric(t("revenue_forecast.paying_artists", "Artistes payants"), nb_paying)
    c4.metric(t("revenue_forecast.pending_cancellations", "Annulations en attente"),
              nb_cancel, delta=f"-{nb_cancel}" if nb_cancel else None,
              delta_color="inverse")

    st.markdown("---")

    # MRR par plan
    mrr_by_plan = (
        paying.groupby('plan')['price']
        .agg(['sum', 'count'])
        .reset_index()
        .rename(columns={'sum': 'mrr', 'count': 'artistes'})
    )
    if not mrr_by_plan.empty:
        fig = px.bar(
            mrr_by_plan, x='plan', y='mrr',
            text='mrr', color='plan',
            labels={'plan': 'Plan', 'mrr': 'MRR (€)'},
            color_discrete_sequence=list(DISTINCT[:3]),
        )
        fig.update_traces(texttemplate='%{text:.2f} €', textposition='outside')
        fig.update_layout(showlegend=False, yaxis_title='MRR (€)')
        charts.plotly_chart(fig, width='stretch')

    st.markdown("---")
    st.subheader(t("revenue_forecast.subs_detail", "Détail des abonnements"))
    display = active[['artist_name', 'plan', 'price', 'status', 'cancel_at_period_end',
                       'current_period_end']].copy()
    display['current_period_end'] = pd.to_datetime(display['current_period_end']).dt.strftime('%Y-%m-%d')
    st.dataframe(
        display.rename(columns={
            'artist_name': t("common.artist", "Artiste"),
            'plan': 'Plan',
            'price': t("revenue_forecast.col_price", "Prix (€/mois)"),
            'status': t("revenue_forecast.col_status", "Statut"),
            'cancel_at_period_end': t("revenue_forecast.col_cancel", "Annulation fin période"),
            'current_period_end': t("revenue_forecast.col_period_end", "Fin de période"),
        }),
        width='stretch', hide_index=True,
    )


# R249 (fiche 61, owner 2026-09-27 : « à retirer ») : the MRR growth simulation tab is gone.

# ─────────────────────────────────────────────
# Tab 3 — LTV & Churn
# ─────────────────────────────────────────────

@st.fragment
def _frag_ltv() -> None:
    """La valeur vie client — rejoué SEUL quand ses curseurs bougent.

    @st.fragment (R118, 2026-09-16). Ses widgets sont des CURSEURS : on les traîne, donc
    ils déclenchent une rafale de reruns. Avant, chacun rejouait tout le script — les
    quatre onglets, dont `st.tabs` exécute tous les corps, plus la barre latérale. C'est
    le pire profil d'usage pour un rerun complet, et le meilleur cas pour un fragment.

    ⚠️ Il ouvre sa PROPRE connexion : ses curseurs pilotent des requêtes, et celle de
    `show()` est refermée dès la fin du rendu complet. Un fragment qui la capturerait la
    ré-emprunterait au pool sans jamais la rendre. Garde :
    `tests/test_a_fragment_never_captures_a_connection.py`.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, _artist_id):
        _tab_ltv(db)


def _tab_ltv(db) -> None:
    st.subheader(t("revenue_forecast.ltv_header", "LTV & Churn"))

    df = _load_subscriptions(db)
    active = df[df['status'].isin(MRR_STATUSES)]
    paying = active[active['price'] > 0]

    total_mrr = float(paying['price'].sum()) if not paying.empty else 0.0
    nb_paying  = len(paying)
    arpu       = total_mrr / nb_paying if nb_paying else 0.0
    nb_cancel  = int(active['cancel_at_period_end'].sum()) if not active.empty else 0
    nb_total   = len(active)
    churn_from_db = (nb_cancel / nb_total * 100) if nb_total > 0 else 0.0

    st.markdown(t("revenue_forecast.ltv_classic_header", "#### LTV classique (ARPU ÷ churn mensuel)"))

    if churn_from_db < 0.5:
        st.info(t("revenue_forecast.churn_low",
                  "Taux de churn détecté < 0.5% (peu d'annulations en attente). Ajustez manuellement :"))
        churn_rate = st.slider(t("revenue_forecast.churn_estimated", "Taux de churn mensuel estimé (%)"),
                               1.0, 20.0, 5.0, step=0.5)
    else:
        churn_rate = st.slider(
            t("revenue_forecast.churn_monthly", "Taux de churn mensuel (%)"),
            1.0, 20.0, round(churn_from_db, 1), step=0.5,
            help=t("revenue_forecast.churn_help",
                   "Valeur estimée depuis les annulations en attente : {churn:.1f}%").format(churn=churn_from_db),
        )

    ltv_val = ltv_global(arpu, churn_rate)

    c1, c2, c3 = st.columns(3)
    c1.metric("ARPU", f"{arpu:,.2f} €")
    c2.metric(t("revenue_forecast.churn_monthly_metric", "Churn mensuel"), f"{churn_rate:.1f}%")
    c3.metric(t("revenue_forecast.ltv_global", "LTV globale"), f"{ltv_val:,.2f} €")

    st.markdown("---")
    st.markdown(t("revenue_forecast.ltv_scenario_header", "#### LTV par scénario de durée de rétention"))

    plans = [('premium', _CAT['premium']['price_eur'])]
    durations = [6, 12, 24, 36]
    ltv_df = pd.DataFrame(ltv_scenarios(plans, durations))

    fig = px.bar(
        ltv_df, x='LTV (€)', y='Durée (mois)', color='Plan',
        orientation='h', barmode='group',
        color_discrete_sequence=list(DISTINCT[:2]),
        labels={'LTV (€)': 'LTV estimée (€)', 'Durée (mois)': 'Rétention'},
        text='LTV (€)',
    )
    fig.update_traces(texttemplate='%{text:.0f} €', textposition='outside')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    charts.plotly_chart(fig, width='stretch')

    st.markdown("---")
    st.markdown(t("revenue_forecast.ltv_artistic_header", "#### LTV artistique (revenus musicaux × durée)"))
    st.caption(t("revenue_forecast.ltv_artistic_caption",
                 "Proxy : valeur musicale moyenne d'un artiste, basée sur l'historique distributeurs + SACEM."))

    avg_row = db.fetch_query("""
        SELECT AVG(monthly_avg) FROM (
            SELECT artist_id, AVG(month_total) AS monthly_avg FROM (
                SELECT artist_id, year, month, SUM(revenue_eur) AS month_total
                FROM v_artist_monthly_revenue GROUP BY artist_id, year, month
            ) m GROUP BY artist_id
        ) t
    """)
    avg_music = float(avg_row[0][0]) if avg_row and avg_row[0][0] else 0.0

    retention = st.select_slider(
        t("revenue_forecast.retention_hypothetical", "Durée de rétention hypothétique (mois)"),
        options=[6, 12, 24, 36], value=12, key='ltv_retention',
    )
    ltv_music = avg_music * retention

    mc1, mc2 = st.columns(2)
    mc1.metric(t("revenue_forecast.avg_music_revenue", "Revenu musical moyen / mois / artiste"), f"{avg_music:,.2f} €")
    mc2.metric(t("revenue_forecast.ltv_artistic_metric", "LTV artistique sur {months} mois").format(months=retention),
               f"{ltv_music:,.2f} €")


# ─────────────────────────────────────────────
# Tab 4 — Projection Artistique
# ─────────────────────────────────────────────

@st.fragment
def _frag_artist_forecast(artist_id: int | None) -> None:
    """La prévision par artiste — rejoué SEUL quand ses curseurs bougent.

    @st.fragment (R118, 2026-09-16). Ses widgets sont des CURSEURS : on les traîne, donc
    ils déclenchent une rafale de reruns. Avant, chacun rejouait tout le script — les
    quatre onglets, dont `st.tabs` exécute tous les corps, plus la barre latérale. C'est
    le pire profil d'usage pour un rerun complet, et le meilleur cas pour un fragment.

    ⚠️ Il ouvre sa PROPRE connexion : ses curseurs pilotent des requêtes, et celle de
    `show()` est refermée dès la fin du rendu complet. Un fragment qui la capturerait la
    ré-emprunterait au pool sans jamais la rendre. Garde :
    `tests/test_a_fragment_never_captures_a_connection.py`.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, _artist_id):
        _tab_artist_forecast(db, artist_id)


# ═══════════════════════════════════════════════════════════════════════════
# TOUT L'ARGENT SUR UNE FIGURE — et la date du point mort
# ═══════════════════════════════════════════════════════════════════════════
#
# Demandé le 2026-09-21 : « fusionner toutes les dépenses et tous les couts […]
# sur 1 seul et faire les prédictions dessus, indiquer clairement sur le
# graphique la durée à ce stade pour être breakheaven ».
#
# ⚠️ « Une seule figure » se rend en DEUX CADRES qui partagent leur axe du temps,
# et ce n'est pas une entorse à la demande — c'est la seule façon de la tenir.
# Mesuré sur l'artiste 1 : les flux mensuels vont de −700 € à +13 €, le cumul
# vaut −2 839 €. Sur un repère commun, les barres mensuelles récentes font MOINS
# D'UN PIXEL. Un second axe y est interdit dans ce dépôt (`_MAX_SECONDARY_AXES =
# 0`) et le serait ici de toute façon : deux échelles décalées feraient croiser
# deux courbes en un point qui ne veut rien dire.
#
# Deux cadres, un objet, un axe du temps, une légende : ce que la demande veut
# dire — ne plus avoir à rapprocher trois figures pour savoir où on en est.

# The colours and names live with the treasury figure (R212) — one definition for
# every page that draws money. The names are re-exported: the cost-entry labels read them.
from src.dashboard.utils.treasury_chart import FLUX_NAMES as _FLUX_NOMS  # noqa: E402


def _render_ledger(db, artist_id, cashflow: pd.DataFrame, mensuel: pd.DataFrame) -> None:
    """R236 — the whole money story in ONE line above the treasury: what came in, what
    went out (ads apart), the result, and what the ads bought in streams. A text line,
    not a figure: the page sits at its figure ceiling, and six numbers read in a row."""
    from src.dashboard.utils.platform_timeseries import platform_totals
    from src.dashboard.utils.treasury_chart import ledger_summary
    totals = platform_totals(db, artist_id) or {}
    measured = [v for v in totals.values() if v is not None]
    s = ledger_summary(cashflow, mensuel, float(sum(measured)) if measured else None)

    head = t("revenue_forecast.ledger_head",
             "| Revenus | Dépenses | dont pub | Résultat financier | Écoutes (toutes plateformes) "
             "| Pub par écoute |")
    streams = "—" if s['streams'] is None else num(s['streams'], 0)
    per_stream = eur(s['cost_per_stream'], 3)
    row = (f"| {eur(s['revenue'], 0)} | {eur(s['spend'], 0)} | {eur(s['ads'], 0)} | "
           f"**{eur(s['result'], 0)}** | {streams} | {per_stream} |")
    st.markdown(head + "\n|---|---|---|---|---|---|\n" + row)
    st.caption(t("revenue_forecast.ledger_caption",
                 "Depuis le début. « Pub par écoute » divise la dépense publicitaire par TOUTES "
                 "les écoutes, organiques comprises : c'est un plafond, pas ce qu'une écoute "
                 "gagnée a coûté — celui-là est dans « Tout mon funnel », campagne par campagne."))


def _render_money_chart(cashflow: pd.DataFrame, mensuel: pd.DataFrame,
                        pm: dict, horizon: int) -> None:
    """The break-even answer — the treasury itself is drawn ONCE, on the distributors page.

    R244 (owner, 2026-09-27, fiche 63 : « redondant, je l'ai déjà vu passer »). The same
    treasury figure was drawn on three pages; it now lives on « Distributeurs », free, and
    this premium page keeps what it adds: the break-even verdict at this pace."""
    st.info(_breakeven_text(pm).replace("<br>", " — "))
    st.caption(t("revenue_forecast.treasury_moved",
                 "Le graphique de trésorerie (ventes, SACEM, dépenses, cumulés) est sur la "
                 "page 💰 Distributeurs."))


from src.dashboard.utils.treasury_chart import (  # noqa: E402 — R262, one definition
    breakeven_short as _breakeven_short, breakeven_text as _breakeven_text)


_CAT_COUTS = ["distribution", "mastering", "visuel", "promo", "materiel", "autre"]


def _artist_tracks(db, artist_id: int) -> list[str]:
    """The artist's titles, as S4A names them (the « Total » row excluded)."""
    rows = db.fetch_query(
        "SELECT DISTINCT song FROM v_s4a_song_daily WHERE artist_id = %s "
        "AND song NOT ILIKE '%%1x7xxxxxxx%%' ORDER BY song", (artist_id,))
    return [r[0] for r in rows or []]


def cost_label(libelle: str, titre: str, categorie: str) -> str | None:
    """The entry's label: what the artist typed, else « <type> — <titre> ». Pure (R248)."""
    if libelle:
        return libelle if not titre or titre == "—" else f"{libelle} — {titre}"
    if titre and titre != "—":
        return f"{_FLUX_NOMS.get(categorie, categorie)} — {titre}"
    return None


def _render_cost_entry(db, artist_id: int) -> None:
    """La saisie des coûts que PERSONNE d'autre ne connaît.

    ⚠️ Aucun distributeur n'expose son abonnement par API — vérifié le
    2026-09-21 sur les trois intégrations du dépôt. iMusician facture par sortie
    ou à l'année, et rien de cette facture ne redescend dans les rapports de
    ventes. Sans cette saisie, la page calcule un point mort qui ignore le coût
    de mise en ligne, c'est-à-dire la première dépense de toute sortie.
    """
    from src.dashboard.utils.ui import flash

    with secondary_analyses(t("revenue_forecast.costs_expander",
                              "💳 Mes coûts (distribution, mastering, visuel…) — saisir"),
                            expanded=False):
        st.caption(t(
            "revenue_forecast.costs_caption",
            "Ce que tu paies pour sortir ta musique n'arrive par aucune API : ton "
            "distributeur ne le renvoie pas dans ses rapports de ventes. Saisis-le "
            "ici et il entre dans la figure et dans le point mort."))

        with st.form("artist_cost_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            categorie = c1.selectbox(
                t("revenue_forecast.cost_category", "Type de coût"), _CAT_COUTS,
                format_func=lambda k: t(f"revenue_forecast.cat.{k}",
                                        _FLUX_NOMS.get(k, k)))
            montant = c2.number_input(t("revenue_forecast.cost_amount", "Montant (€)"),
                                      min_value=0.0, step=5.0, value=0.0)
            periode = c3.selectbox(
                t("revenue_forecast.cost_period", "Fréquence"),
                ["one_off", "yearly", "monthly"],
                format_func=lambda k: t(f"revenue_forecast.period.{k}", {
                    "one_off": "Une fois", "yearly": "Par an",
                    "monthly": "Par mois"}[k]))
            # ⚠️ LA DATE DE FIN EST INDISPENSABLE, et son absence était un défaut
            # de produit trouvé en insérant un vrai coût le 2026-09-21 : un
            # abonnement annuel de 240 € commencé en janvier 2024, sans fin,
            # s'accumule à **660 €** aujourd'hui. Le chiffre est JUSTE — un
            # abonnement actif se renouvelle — mais sans champ pour le clore, un
            # abonnement résilié facturerait l'artiste à vie dans son point mort.
            d1, d2, d3 = st.columns([1, 1, 2])
            debut = d1.date_input(t("revenue_forecast.cost_start", "À partir de"),
                                  value=_date.today().replace(day=1))
            fin = None
            if periode != "one_off":
                encore = d2.checkbox(t("revenue_forecast.cost_ongoing",
                                       "Toujours actif"), value=True)
                if not encore:
                    fin = d2.date_input(t("revenue_forecast.cost_end", "Jusqu'à"),
                                        value=_date.today().replace(day=1))
            else:
                d2.caption(t("revenue_forecast.cost_once",
                             "Dépense unique : elle tombe sur son seul mois."))
            libelle = d3.text_input(t("revenue_forecast.cost_label", "Libellé (facultatif)"),
                                    placeholder="iMusician — sortie « Patte Velours »")
            # R248 (fiche 62) : le coût d'un TITRE — iMusician, DistroKid facturent par
            # sortie. Toujours présent : un formulaire ne se re-rend pas pendant la saisie.
            titre = st.selectbox(t("revenue_forecast.cost_track", "Titre concerné (facultatif)"),
                                 ["—", *_artist_tracks(db, artist_id)])
            if periode == "yearly":
                st.caption(t("revenue_forecast.cost_yearly_warning",
                             "⚠️ **{m:.2f} € PAR AN**, pas au total : tant que "
                             "l'abonnement est actif, il se renouvelle et "
                             "s'accumule dans le point mort."
                             ).format(m=float(montant)))
            elif periode == "monthly":
                st.caption(t("revenue_forecast.cost_monthly_warning",
                             "⚠️ **{m:.2f} € PAR MOIS**, pas au total."
                             ).format(m=float(montant)))
            if st.form_submit_button(t("revenue_forecast.cost_save", "💾 Enregistrer"),
                                     width="stretch"):
                if montant <= 0:
                    st.warning(t("revenue_forecast.cost_zero",
                                 "Un montant à zéro ne change rien à la figure."))
                else:
                    db.execute_query(
                        """INSERT INTO artist_cost_entries
                           (artist_id, category, label, amount_eur,
                            billing_period, start_month, end_month)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (artist_id, categorie, cost_label(libelle, titre, categorie), float(montant),
                         periode, debut.replace(day=1),
                         fin.replace(day=1) if fin else None))
                    # ⚠️ Le message est DÉPOSÉ avant le rerun : `st.rerun()` jette le
                    # rendu en cours, et un `st.success()` juste avant n'est jamais
                    # peint. Le propriétaire a rapporté exactement ce défaut sur la
                    # saisie S4A le 2026-09-20 — « rien ne m'a communiqué que ça
                    # avait été enregistré » — alors que l'écriture avait eu lieu.
                    flash(t("revenue_forecast.cost_saved",
                            "✅ {m:.2f} € enregistrés — la figure et le point mort "
                            "en tiennent compte.").format(m=float(montant)))
                    st.rerun()

        deja = db.fetch_df(
            """SELECT id, category, label, amount_eur, billing_period,
                      start_month, end_month
               FROM artist_cost_entries WHERE artist_id = %s
               ORDER BY start_month DESC, id DESC""", (artist_id,))
        # ⚠️ La vue `v_artist_monthly_costs` est lue ICI, et pas seulement par
        # `v_artist_monthly_cashflow` en SQL : une vue or que seul du SQL lit est
        # comptée ORPHELINE par `make gold-coverage`, et une vue orpheline est du
        # travail gelé qu'on ne relit plus. Elle apporte en plus l'information que
        # la table brute n'a pas — ce que les coûts pèsent PAR MOIS une fois
        # étalés, c'est-à-dire ce qui entre vraiment dans le point mort.
        etale = db.fetch_df(
            """SELECT SUM(amount_eur) AS total,
                      COUNT(DISTINCT (year, month)) AS mois
               FROM v_artist_monthly_costs WHERE artist_id = %s""",
            (artist_id,))
        if etale is not None and not etale.empty \
                and pd.notna(etale['total'].iloc[0]):
            _tot = float(etale['total'].iloc[0])
            _mois = int(etale['mois'].iloc[0] or 1)
            st.caption(t(
                "revenue_forecast.costs_spread",
                "**{tot:,.2f} €** au total, étalés sur {n} mois — soit "
                "**{moy:,.2f} €/mois** dans la figure et dans le point mort."
            ).format(tot=_tot, n=_mois, moy=_tot / max(_mois, 1)))

        if deja is None or deja.empty:
            st.info(t("revenue_forecast.no_cost",
                      "Aucun coût saisi. Le point mort ci-dessus ne compte donc que "
                      "ta publicité — il est OPTIMISTE de tout ce que tu as payé "
                      "pour mettre ta musique en ligne."))
            return
        st.dataframe(
            deja.rename(columns={
                'category': t("revenue_forecast.cost_category", "Type de coût"),
                'label': t("revenue_forecast.cost_label", "Libellé (facultatif)"),
                'amount_eur': t("revenue_forecast.cost_amount", "Montant (€)"),
                'billing_period': t("revenue_forecast.cost_period", "Fréquence"),
                'start_month': t("revenue_forecast.cost_start", "À partir de"),
                'end_month': t("revenue_forecast.cost_end", "Jusqu'à"),
            }).drop(columns=['id']),
            width='stretch', hide_index=True)


def _render_trigger_value(db, artist_id: int, mensuel: pd.DataFrame) -> None:
    """Ce que vaut un titre qui déclenche un algorithme, en euros mesurés.

    ⚠️ CE N'EST PAS LE GAIN DU DÉCLENCHEMENT, et la vue le dit à l'endroit où elle
    l'affiche. La cohorte de référence ne contient QUE des titres qui ont
    déclenché : il n'y a pas de témoin, donc pas d'effet causal à en tirer. Ce
    qu'elle donne est un ordre de grandeur — voilà où arrivent les titres qui y
    arrivent — et le contraste que la donnée supporte est la comparaison avec les
    propres titres de l'artiste.
    """
    from src.dashboard.utils.artist_cashflow import (
        stream_rate, trigger_expectation, trigger_value)

    st.markdown("---")
    st.subheader(t("revenue_forecast.trigger_header",
                   "🚀 Et si un titre déclenchait les algorithmes ?"))

    taux = stream_rate(db, artist_id)
    if taux is None:
        st.info(t("revenue_forecast.no_rate",
                  "Il faut au moins un rapport de ventes du distributeur pour "
                  "connaître ce qu'une écoute te rapporte. Importe un CSV depuis "
                  "**Import CSV**."))
        return

    valeurs = trigger_value(db, taux['eur_par_stream'])
    if valeurs.empty:
        st.info(t("revenue_forecast.no_benchmark",
                  "La cohorte de référence n'est pas chargée sur cette base."))
        return

    # ⚠️ `v_s4a_song_daily`, PAS `s4a_song_timeline`. Agréger la table de fait
    # ici créerait une deuxième définition du total par titre — la plateforme
    # dont le total a divergé TROIS fois avant la migration 097. La vue porte
    # déjà le filtre de la ligne « Total » des exports S4A ; vérifié le
    # 2026-09-21, les deux rendent 11 titres et une médiane de 9 049 écoutes.
    # Garde : `tests/test_the_metrics_layer_only_grows.py`.
    propre = db.fetch_df(
        """SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tot) AS mediane
           FROM (SELECT song, SUM(streams) AS tot FROM v_s4a_song_daily
                 WHERE artist_id = %s
                 GROUP BY song) p""",
        (artist_id,))
    med_propre = (float(pd.to_numeric(propre['mediane'].iloc[0], errors='coerce'))
                  if propre is not None and not propre.empty
                  and pd.notna(propre['mediane'].iloc[0]) else None)

    # DEUX BARRES PAR ALGORITHME, et la seconde est celle qui décide.
    #
    # La première dit ce qu'un déclenchement VAUT — 23 € pour Discover Weekly.
    # La seconde dit ce que TON CATALOGUE peut en espérer : la même valeur
    # multipliée par la probabilité calibrée de chacun de tes titres. Sur
    # l'artiste 1 le 2026-09-21 : 23,38 € de valeur, **18,27 € d'espérance** sur
    # onze titres — parce qu'aucun n'est au-dessus de 7,4 % de chance.
    #
    # Montrer la première sans la seconde laisserait lire « 23 € par titre ».
    espoir = trigger_expectation(db, artist_id, valeurs)
    esp = ({r['algo']: r for _, r in espoir['par_algo'].iterrows()}
           if espoir else {})

    # R247 (fiche 64) — what « a trigger » and its value are, before the bars.
    st.caption(t("revenue_forecast.trigger_plain",
                 "Un **déclenchement**, c'est un algorithme (Discover Weekly, Release Radar, "
                 "Radio) qui se met à pousser ton titre. Barre pâle : ce que rapporte "
                 "d'habitude un titre qui déclenche (ses écoutes médianes × ce qu'une écoute "
                 "te paie). Barre verte : ce que tes titres peuvent en espérer, vu leur "
                 "chance réelle."))
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=valeurs['valeur_eur'], y=valeurs['nom'], orientation='h',
        marker={'color': "#9FD8B4"},
        name=t("revenue_forecast.bar_value", "Valeur d'un déclenchement"),
        text=[eur(v, 2) for v in valeurs['valeur_eur']],
        textposition='outside', cliponaxis=False,
        customdata=valeurs[['streams_med', 'n']].values,
        hovertemplate=("%{y}<br>%{customdata[0]:,.0f} écoutes médianes"
                       "<br>cohorte de %{customdata[1]} titres<extra></extra>")))
    if esp:
        ordre = [esp.get(a, {}).get('esperance_eur', 0.0) for a in valeurs['algo']]
        probas = [esp.get(a, {}).get('proba_moyenne', 0.0) for a in valeurs['algo']]
        fig.add_trace(go.Bar(
            x=ordre, y=valeurs['nom'], orientation='h',
            marker={'color': DISTINCT[0]},
            name=t("revenue_forecast.bar_expect", "Espérance sur ton catalogue"),
            text=[eur(v, 2) for v in ordre],
            textposition='outside', cliponaxis=False,
            customdata=[[p * 100] for p in probas],
            hovertemplate=("%{y}<br>%{x:.2f} € espérés"
                           "<br>chance moyenne : %{customdata[0]:.1f} %"
                           "<extra></extra>")))
    if med_propre:
        fig.add_vline(
            x=med_propre * taux['eur_par_stream'], line={'color': "#FF6B35",
                                                         'width': 2, 'dash': 'dash'},
            annotation_text=t("revenue_forecast.own_median",
                              "ton titre médian : {e:,.2f} €"
                              ).format(e=med_propre * taux['eur_par_stream']
                                       ).replace(",", " "),
            annotation_position="top")
    fig.update_xaxes(showticklabels=False)
    fig.update_layout(height=360, margin={'l': 10, 'r': 70, 't': 70, 'b': 20},
                      bargap=0.3, barmode='group',
                      legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.04,
                              'xanchor': 'right', 'x': 1})
    fig.update_yaxes(automargin=True)
    charts.plotly_chart(fig, width='stretch')

    # ⚠️ LE MANQUE SE COMPARE À L'ESPÉRANCE, pas à la valeur.
    #
    # Le premier jet divisait l'écart au point mort par la VALEUR du meilleur
    # déclenchement (23 €) et concluait « il faudrait 123 titres ». C'était faux
    # d'un facteur quatorze : ces titres n'auraient pas tous déclenché. Rapporté à
    # l'espérance du catalogue — 42,75 € pour onze titres, soit 3,89 € par titre —
    # il en faudrait **730**. Le second nombre est brutal ; c'est le juste, et
    # c'est lui qui dit que la réponse n'est pas « sortir plus de titres ».
    pm = _breakeven_gap(mensuel)
    manque = ""
    if pm is not None and pm > 0 and espoir and espoir['titres'] > 0:
        par_titre = espoir['total'] / espoir['titres']
        if par_titre > 0:
            manque = t(
                "revenue_forecast.trigger_gap",
                "\n\nTon catalogue de **{k} titres** espère **{e} €** au total, "
                "soit **{u} € par titre**. Pour combler les **{c} €** qui te "
                "séparent du point mort, il en faudrait environ **{n}** de plus, "
                "au même niveau."
            ).format(k=espoir['titres'],
                     e=num(espoir['total'], 2),
                     u=num(par_titre, 2),
                     c=num(pm, 0),
                     n=num(pm / par_titre, 0))

    # ⚠️ `.replace(",", " ")` s'applique au NOMBRE FORMATÉ, jamais à la phrase.
    # Appliqué à la phrase entière, il mangeait la virgule de « ton taux réel,
    # mesuré sur… » — vu au rendu le 2026-09-21. Un séparateur de milliers et une
    # ponctuation sont le même caractère ; seul le premier doit être remplacé.
    _fr = lambda v, f="{:,.0f}": f.format(v).replace(",", " ")   # noqa: E731
    st.caption(t(
        "revenue_forecast.trigger_caption",
        "À **{tx} € l'écoute** — ton taux réel, mesuré sur {s} écoutes "
        "payées {r} € par ton distributeur.\n\n"
        "⚠️ **Ce n'est pas le gain du déclenchement.** La cohorte de référence ne "
        "contient que des titres qui ONT déclenché : sans titre témoin, on ne peut "
        "pas dire ce que l'algorithme a ajouté. C'est un ordre de grandeur — voilà "
        "où arrivent les titres qui y arrivent. L'espérance, elle, multiplie "
        "cette valeur par la chance CALIBRÉE de chacun de tes titres{d}."
    ).format(tx=f"{taux['eur_par_stream']:.6f}", s=_fr(taux['streams']),
             r=_fr(taux['revenus'], "{:,.2f}"),
             d=(t("revenue_forecast.pred_dated", " (prédictions du {d})").format(
                 d=format_date(espoir["date"]))
                if espoir and espoir.get('date') else "")) + manque)
    st.markdown(_trigger_decision_text(float(valeurs['valeur_eur'].max()), pm))


def _trigger_decision_text(best: float, gap: float | None) -> str:
    from src.dashboard.utils.artist_cashflow import trigger_decision
    kind, n = trigger_decision(best, gap)
    if kind == "small":
        return t("revenue_forecast.trigger_small",
                 "**La décision** : il faudrait environ **{n}** déclenchements à {v} € pour "
                 "rentrer dans tes frais. Les algorithmes t'apportent des auditeurs, pas de "
                 "quoi rembourser ta pub — juge ta pub sur les écoutes qu'elle achète, et "
                 "tes frais sur ce qu'ils rapportent.").format(
                     n=num(n, 0), v=num(best, 2))
    return t("revenue_forecast.trigger_worth",
             "**La décision** : un déclenchement rapporte jusqu'à {v} €, à l'échelle de ce "
             "qui te manque — pousse le titre le plus proche d'une porte (Road to Algo)."
             ).format(v=num(best, 2))


def _breakeven_gap(mensuel: pd.DataFrame) -> float | None:
    """Les euros qui manquent pour revenir à zéro, ou None si déjà au-dessus."""
    if mensuel is None or mensuel.empty:
        return None
    cumul = float(mensuel['cumul'].iloc[-1])
    return -cumul if cumul < 0 else None


_FLOOR_COLUMNS = (("DW", "dw_streams_forecast_7d"),
                  ("RR", "rr_streams_forecast_7d"),
                  ("RADIO", "radio_streams_forecast_7d"))


def drop_suppressed_floor_columns(ml_df: pd.DataFrame) -> pd.DataFrame:
    """Drop every floor column whose volume regressor the single-source gate suppresses.

    This read only `"RR"` until 2026-09-26, so the DW floor column (DW volume R²<0,
    suppressed since v3) stayed in the ROI table.
    Guard: tests/test_a_suppressed_forecast_is_never_drawn.py
    """
    return ml_df.drop(columns=[col for algo, col in _FLOOR_COLUMNS
                               if not ak.volume_forecast_reliable(algo)],
                      errors='ignore')


def _tab_artist_forecast(db, artist_id: int | None) -> None:
    # ⚠️ `show_infra` a été RETIRÉ le 2026-09-21, pas mis en commentaire. Il ne
    # servait qu'au champ « Coût infra VPS (€/mois) » du waterfall de marge, que
    # cette page n'a plus : ce coût est celui de l'EXPLOITANT, il vit dans
    # `app_operating_costs` et se lit dans les onglets MRR. Un drapeau que plus
    # rien ne lit est une couche débranchée, et ce dépôt a mesuré ce qu'elles
    # coûtent quand on les rebranche des mois plus tard.
    st.subheader(t("revenue_forecast.artist_forecast_header",
                   "Mon argent : ce qui rentre, ce qui sort, et quand j'y suis"))
    st.caption(t("revenue_forecast.artist_forecast_caption",
                 "Tout ton argent sur une figure : distributeurs (iMusician, "
                 "DistroKid), royalties SACEM, publicité Meta et tes coûts de "
                 "sortie. La courbe du bas croise zéro le jour où tu rentres "
                 "dans tes frais."))

    if is_admin():
        artists_df = _load_artists(db)
        if artists_df.empty:
            st.warning(t("revenue_forecast.no_active_artist", "Aucun artiste actif."))
            return
        opts = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        sel  = st.selectbox(t("common.artist", "Artiste"), list(opts.keys()), key='forecast_artist')
        target_id = opts[sel]
    else:
        target_id = artist_id
        if target_id is None:
            st.error(t("revenue_forecast.no_artist_id", "Impossible de déterminer votre identifiant artiste."))
            return

    # ═══════════════════════════════════════════════════════════════════════
    # TOUT L'ARGENT, PUIS LE POINT MORT — 2026-09-21
    # ═══════════════════════════════════════════════════════════════════════
    #
    # La page ouvrait sur trois tuiles de revenus cumulés, puis une courbe de
    # revenus, puis — plus bas, sous un séparateur — une figure de dépense Meta,
    # puis un « waterfall » de marge nourri par un champ à remplir à la main.
    # Quatre surfaces pour une seule question, et aucune n'y répondait :
    # **est-ce que je suis rentré dans mes frais, et quand ?**
    #
    # Mesuré sur l'artiste 1 le 2026-09-21 : 248,39 € de revenus nets contre
    # 3 087,82 € de publicité. Le chiffre existait dans la base depuis des mois ;
    # aucune page ne le posait côte à côte.
    from src.dashboard.utils.artist_cashflow import (
        FENETRE_RYTHME, break_even, forward_rate, monthly_net)

    cashflow = db.fetch_df(
        """SELECT year, month, flux, source, amount_eur, direction
           FROM v_artist_monthly_cashflow WHERE artist_id = %s""",
        (target_id,))
    mensuel = monthly_net(cashflow)

    if mensuel.empty:
        st.info(t(
            "revenue_forecast.no_money_yet",
            "Aucun mouvement d'argent connu. Importe un rapport de ventes depuis "
            "**Import CSV**, ou connecte Meta dans **🔑 Credentials API**."))
        return

    pm = break_even(mensuel)
    horizon = st.select_slider(
        t("revenue_forecast.horizon", "Horizon de projection (mois)"),
        options=[3, 6, 12], value=6)

    b1, b2, b3 = st.columns(3)
    # ⚠️ Les valeurs sont lues sur `mensuel`, PAS sur le dictionnaire du point
    # mort, alors que `pm['cumul']` vaut exactement la même chose. La carte de la
    # couche or remonte la provenance de proche en proche : passée par
    # `break_even(monthly_net(cashflow))`, la tuile sortait « indéterminée ·
    # profondeur » — un chiffre d'argent dont la carte ne sait plus dire d'où il
    # vient. Un saut de moins, et elle nomme `v_artist_monthly_cashflow`.
    b1.metric(
        t("revenue_forecast.kpi_cumul", "💰 Où j'en suis au total"),
        f"{float(mensuel['cumul'].iloc[-1]):+,.2f} €".replace(",", " "),
        delta=t("revenue_forecast.kpi_cumul_delta",
                "{r:+,.0f} € encaissés · {d:,.0f} € dépensés").format(
            r=mensuel['revenus'].sum(), d=mensuel['depenses'].sum()).replace(",", " "),
        delta_color="off")
    b2.metric(
        t("revenue_forecast.kpi_rythme", "📆 Mon rythme actuel"),
        f"{forward_rate(mensuel):+,.2f} €/mois".replace(",", " "),
        delta=t("revenue_forecast.kpi_rythme_delta",
                "moyenne des {n} derniers mois").format(n=FENETRE_RYTHME),
        delta_color="off")
    b3.metric(
        t("revenue_forecast.kpi_breakeven", "⏳ Point mort"),
        _breakeven_short(pm),
        delta=(f"{pm['date']:%m/%Y}" if pm.get('date') else
               t("revenue_forecast.be_no_date", "hors d'atteinte")),
        delta_color="off")

    _render_ledger(db, target_id, cashflow, mensuel)
    _render_money_chart(cashflow, mensuel, pm, horizon)
    _render_cost_entry(db, target_id)
    _render_trigger_value(db, target_id, mensuel)

    # ── Ce qui RAFFINE la réponse, et ne la prend pas ────────────────────────
    df = _load_artist_revenues(db, target_id)
    if not df.empty:
        df['date'] = pd.to_datetime(
            df.apply(lambda r: f"{int(r['year'])}-{int(r['month']):02d}-01", axis=1))
        df = df.sort_values('date').reset_index(drop=True)
        df['revenue_eur'] = df['revenue_eur'].astype(float)
        with secondary_analyses(t("revenue_forecast.detail_expander",
                                  "🔎 Le détail par source et mois — chiffres exacts")):
            # ⚠️ LES TUILES LISENT LA MÊME VUE QUE LA FIGURE, et c'est une
            # correction vue au rendu le 2026-09-21 : elles affichaient
            # **43,06 €** de SACEM sous une figure qui en dessinait **36,49 €**.
            #
            # Les deux nombres étaient justes et ne disaient pas la même chose :
            # `_load_artist_revenue_by_source` rend le BRUT, la vue de trésorerie
            # rend le NET, charges et TVA déduites (6,57 € ici). Deux définitions
            # du même mot dans le même écran, à un clic l'une de l'autre — la
            # forme exacte que ce dépôt a déjà payée sur un total Apple.
            #
            # C'est le net qui compte pour un point mort : c'est ce qui arrive
            # réellement sur le compte.
            par_source = (cashflow[cashflow['flux'] == 'revenu']
                          .groupby('source')['amount_eur'].sum())
            if float(par_source.sum()) > 0:
                bs1, bs2, bs3 = st.columns(3)
                bs1.metric("💿 iMusician", f"{float(par_source.get('imusician', 0)):,.2f} €")
                bs2.metric("🟢 DistroKid", f"{float(par_source.get('distrokid', 0)):,.2f} €")
                bs3.metric("🎼 SACEM", f"{float(par_source.get('sacem', 0)):,.2f} €")
                st.caption(t("revenue_forecast.by_source_net",
                             "Montants NETS — charges et TVA déduites, comme dans "
                             "la figure et dans le point mort."))
            table = mensuel[['date', 'revenus', 'depenses', 'net', 'cumul']].copy()
            table['date'] = table['date'].dt.strftime('%Y-%m')
            st.dataframe(
                table.rename(columns={
                    'date': t("revenue_forecast.col_month", "Mois"),
                    'revenus': t("revenue_forecast.col_in", "Encaissé (€)"),
                    'depenses': t("revenue_forecast.col_out", "Dépensé (€)"),
                    'net': t("revenue_forecast.col_net", "Net (€)"),
                    'cumul': t("revenue_forecast.col_cumul", "Cumul (€)"),
                }).style.format("{:,.2f}", subset=[
                    t("revenue_forecast.col_in", "Encaissé (€)"),
                    t("revenue_forecast.col_out", "Dépensé (€)"),
                    t("revenue_forecast.col_net", "Net (€)"),
                    t("revenue_forecast.col_cumul", "Cumul (€)")], na_rep="—"),
                width='stretch', hide_index=True)

    # ── LE « ROI Meta » A DISPARU, ABSORBÉ — 2026-09-21 ──────────────────────
    #
    # Il portait deux barres (revenus, dépense Meta) et une courbe de ROI %, sur
    # la même fenêtre et la même maille que la figure d'ouverture. C'était la
    # MÊME question posée une seconde fois, avec une réponse en pourcentage là où
    # l'artiste demande une date.
    #
    # Et la seconde réponse était plus FAIBLE : son dénominateur ne connaissait
    # que la publicité. Un ROI qui ignore le coût de distribution surestime la
    # rentabilité de tout ce qui est sorti — et c'est justement le coût que la
    # migration 133 fait entrer.
    #
    # La dépense Meta n'est pas perdue : elle est une série de la figure
    # d'ouverture, dans `v_artist_monthly_cashflow`, à côté des autres dépenses.

    st.markdown("---")
    # ── Quel de MES titres est le plus près de déclencher ? — REPLIÉ ─────────
    #
    # La figure ci-dessus dit ce qu'un déclenchement VAUT ; ce tableau dit lequel
    # de tes titres en est le plus près. C'est la question d'après, pas la même :
    # elle se pose une fois qu'on a décidé que le montant valait l'effort.
    with secondary_analyses(t("revenue_forecast.ml_expander",
                              "🤖 Lequel de mes titres est le plus près — scores ML")):
        # ── ML — scores par track ─────────────────────────────────────────────────

        try:
            ml_df = db.fetch_df(
                """
                SELECT DISTINCT ON (song)
                    song,
                    prediction_date,
                    dw_probability,
                    rr_probability,
                    radio_probability,
                    dw_streams_forecast_7d,
                    rr_streams_forecast_7d,
                    radio_streams_forecast_7d,
                    streams_7d,
                    streams_28d
                FROM ml_song_predictions
                WHERE artist_id = %s
                  AND song NOT ILIKE '%%1x7xxxxxxx%%'
                ORDER BY song, prediction_date DESC
                """,
                (target_id,),
            )
            ml_read_failed = False
        except Exception as exc:  # noqa: BLE001 — shown below, never as an absence
            ml_df, ml_read_failed = pd.DataFrame(), True
            st.warning(t("revenue_forecast.ml_unreadable",
                         "Les scores ML n'ont pas pu être lus ({err}) : ce n'est pas une "
                         "absence de prédiction.").format(err=type(exc).__name__))

        if ml_read_failed:
            pass
        elif ml_df.empty:
            st.info(t("revenue_forecast.no_ml",
                      "Pas encore de prédiction. Elles sont recalculées chaque jour en fin de "
                      "matinée, à partir des données déjà collectées."))
        else:
            ml_df = _format_ml_table(ml_df)
            ml_df['prediction_date'] = pd.to_datetime(ml_df['prediction_date']).dt.strftime('%Y-%m-%d')

            ml_df = drop_suppressed_floor_columns(ml_df)

            st.caption(
                t("revenue_forecast.ml_caption",
                  "🛡️ Les colonnes *plancher* sont des **estimations worst-case** : le modèle "
                  "de volume sous-estime les hits, le potentiel réel est souvent supérieur. "
                  "Release Radar et Discover Weekly n'ont pas de colonne volume : leur "
                  "volume n'est pas prédictible (taux d'ouverture des notifications pour RR, "
                  "R²<0 pour DW) — on s'appuie sur leur classification (AUC 0.94 et 0.92, "
                  "validée par chanson).")
            )
            st.dataframe(
                ml_df.rename(columns={
                    'song': t("revenue_forecast.col_track", "Track"),
                    'prediction_date': t("revenue_forecast.col_last_prediction", "Dernière prédiction"),
                    'dw_probability': t("revenue_forecast.col_dw_prob", "Discovery Weekly (%)"),
                    'rr_probability': t("revenue_forecast.col_rr_prob", "Release Radar (%)"),
                    'radio_probability': t("revenue_forecast.col_radio_prob", "Radio (%)"),
                    'dw_streams_forecast_7d': t("revenue_forecast.col_dw_streams", "Streams DW 7j (plancher ≥)"),
                    'rr_streams_forecast_7d': t("revenue_forecast.col_rr_streams", "Streams RR 7j (plancher ≥)"),
                    'radio_streams_forecast_7d': t("revenue_forecast.col_radio_streams", "Streams Radio 7j (plancher ≥)"),
                    'streams_7d': t("revenue_forecast.col_streams_7d", "Streams 7j (réels)"),
                    'streams_28d': t("revenue_forecast.col_streams_28d", "Streams 28j (réels)"),
                }),
                width='stretch', hide_index=True,
            )
    # ── LE « WATERFALL DE MARGE » A DISPARU, ET C'ÉTAIT LE PLUS TROMPEUR ─────
    #
    # Il projetait une marge sur l'horizon choisi à partir d'un champ à remplir à
    # la main (« Dépense Meta estimée (€/mois) », pré-rempli avec la moyenne
    # historique). Trois défauts, et le troisième est le grave :
    #
    #   · il demandait à l'artiste de SAISIR une dépense que la base connaît ;
    #   · il pré-remplissait avec une moyenne prise sur des mois où les campagnes
    #     tournaient, donc reconduisait une dépense ARRÊTÉE depuis septembre 2024 ;
    #   · sa projection venait d'une régression sur tout l'historique, tandis que
    #     le reste de la page lit le rythme des douze derniers mois. Deux pentes
    #     incompatibles dans le même écran, chacune affirmant l'autre fausse.
    #
    # La marge projetée est désormais la courbe de projection du cumul net, qui
    # sort du MÊME calcul que le point mort (`artist_cashflow.project`).


def show() -> None:
    from src.dashboard.auth import require_plan
    if not is_admin() and not require_plan('premium'):
        return

    st.title(t("revenue_forecast.title", "📈 Prévisions revenus"))

    db = require_db(get_db_connection())
    # Les fragments de cette page REUTILISENT cette connexion pendant un rendu
    # complet (~13 ms de poignee SCRAM economises chacun) et n'en ouvrent une que
    # lors d'un rerun de fragment. Libere AVANT `close()` : entre les deux, un
    # fragment verrait une connexion fermee dans la fente.
    from src.dashboard.utils.fragment_db import declare_page_db, release_page_db

    declare_page_db(db)
    try:
        if is_admin():
            tab_mrr, tab_ltv, tab_artist = st.tabs([
                t("revenue_forecast.tab_mrr", "📊 MRR Actuel"),
                t("revenue_forecast.tab_ltv", "💎 LTV & Churn"),
                t("revenue_forecast.tab_artist", "🎵 Projection Artistique"),
            ])
            with tab_mrr:
                _tab_mrr(db)
            with tab_ltv:
                _frag_ltv()
            with tab_artist:
                _frag_artist_forecast(artist_id=None)
        else:
            st.caption(t("revenue_forecast.artist_caption",
                         "Revenus, dépenses et point mort — tout sur une figure."))
            _frag_artist_forecast(artist_id=get_artist_id())
    finally:
        release_page_db()
        db.close()

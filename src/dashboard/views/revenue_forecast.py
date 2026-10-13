"""Money pieces of « 💶 Trésorerie » — ledger, cost entry, spend→revenue fit, trigger value.

Type: Sub
Depends on: v_artist_monthly_cashflow, artist_subscriptions, ml_song_predictions
Triggers: views/imusician.py (the Trésorerie page, R553); views/admin.py (`render_ltv`).
          The route key `revenue_forecast` is an ALIAS of `imusician` (mail/PDF links).
Persists in: artist_costs (the cost entry)

R553 (owner Y1, 2026-10-13 : « consolider tous les graphiques de revenue … dans la vue
revenue »): this module used to be « 💶 Mon argent », a section of the algo page. Every
euro is now on ONE page; each piece here has exactly one caller.
"""
import sys
from pathlib import Path
from datetime import date as _date
from datetime import date

import numpy as np

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import charts
from src.dashboard.utils.formats import eur, num
from src.dashboard.utils.platform_colors import DISTINCT
from src.dashboard.utils.semantic_colors import BON
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import secondary_analyses
from src.dashboard.auth import is_admin
from src.dashboard.utils.revenue_forecast import (
    load_subscriptions as _load_subscriptions,
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
    """Admin only, FOLDED: the SaaS value of a subscriber — not the artist's question."""
    with secondary_analyses(t("revenue_forecast.ltv_header", "LTV & Churn")):

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
                 "gagnée a coûté — celui-là est dans « 📣 Publicité Meta Ads › Tout mon funnel », campagne par campagne."))


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
        # R477 (« pas de tableaux ») — one line per entered cost, not a grid.
        st.markdown("\n".join(cost_lines(deja)))


def cost_lines(deja: pd.DataFrame) -> list[str]:
    """One markdown bullet per entered cost: what, how much, how often, since when. Pure."""
    out = []
    for r in deja.to_dict("records"):
        quoi = r.get("label") or r.get("category") or "—"
        fin = f" → {r['end_month']}" if r.get("end_month") else ""
        out.append(f"- **{quoi}** — {float(r['amount_eur']):,.2f} € · "
                   f"{r.get('billing_period') or ''} · {r.get('start_month') or ''}{fin}"
                   .replace(",", " "))
    return out


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
                 "d'habitude un titre qui déclenche (les écoutes d'un titre déclenché typique — "
                 "la moitié font plus, la moitié moins — × ce qu'une écoute te paie). Barre "
                 "verte : le **gain probable** sur ton catalogue = cette valeur × la chance "
                 "réelle de chacun de tes titres de déclencher."))
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=valeurs['valeur_eur'], y=valeurs['nom'], orientation='h',
        marker={'color': "#9FD8B4"},
        name=t("revenue_forecast.bar_value", "Valeur d'un déclenchement"),
        text=[eur(v, 2) for v in valeurs['valeur_eur']],
        textposition='outside', cliponaxis=False,
        customdata=valeurs[['streams_med', 'n']].values,
        hovertemplate=("%{y}<br>%{customdata[0]:,.0f} écoutes (titre déclenché typique)"
                       "<br>cohorte de %{customdata[1]} titres<extra></extra>")))
    if esp:
        ordre = [esp.get(a, {}).get('esperance_eur', 0.0) for a in valeurs['algo']]
        probas = [esp.get(a, {}).get('proba_moyenne', 0.0) for a in valeurs['algo']]
        fig.add_trace(go.Bar(
            x=ordre, y=valeurs['nom'], orientation='h',
            marker={'color': DISTINCT[0]},
            name=t("revenue_forecast.bar_expect", "Gain probable sur ton catalogue"),
            text=[eur(v, 2) for v in ordre],
            textposition='outside', cliponaxis=False,
            customdata=[[p * 100] for p in probas],
            hovertemplate=("%{y}<br>gain probable : %{x:.2f} €"
                           "<br>chance moyenne : %{customdata[0]:.1f} %"
                           "<extra></extra>")))
    if med_propre:
        fig.add_vline(
            x=med_propre * taux['eur_par_stream'], line={'color': "#FF6B35",
                                                         'width': 2, 'dash': 'dash'},
            annotation_text=t("revenue_forecast.own_median",
                              "la moitié de tes titres rapporte plus de {e:,.2f} €"
                              ).format(e=med_propre * taux['eur_par_stream']
                                       ).replace(",", " "),
            annotation_position="top")
    fig.update_xaxes(showticklabels=False)
    fig.update_layout(height=360, margin={'l': 10, 'r': 70, 't': 70, 'b': 20},
                      bargap=0.3, barmode='group')
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
                "\n\nTon catalogue de **{k} titres** a un gain probable de **{e} €** au total, "
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
        "où arrivent les titres qui y arrivent. Le gain probable, lui, multiplie "
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


def render_spend_revenue_fit(db, artist_id: int) -> None:
    """Monthly spend→revenue fit — refused below `MIN_FIT_POINTS` months (2026-09-26).

    It used to fit from 2 points: a line through two points is exact, so the page printed
    R² = 1.000 and p = 0.000 as an artefact of n. `n` is now shown next to R² and p.
    """
    from src.dashboard.utils.roi_verdicts import MIN_FIT_POINTS, fit_spend_revenue

    st.subheader(t("trigger_algo.roi.regression_header", "📉 ROI — Régression linéaire (mensuel)"))
    st.caption(t(
        "trigger_algo.roi.regression_caption",
        "Sur **tout l'historique mensuel** disponible (revenue iMusician × spend Meta Ads), "
        "indépendamment de la période choisie en haut : une régression mensuelle a besoin de "
        "plusieurs mois, qu'une fenêtre J+28 ne peut pas fournir."
    ))
    try:
        from src.dashboard.utils.kpi_helpers import get_monthly_roi_series

        # All-time window on purpose — monthly ROI is a long-horizon analysis, decoupled
        # from the J+28 period selector (date_from/date_to) which captures ≤ 1 month.
        df_roi = get_monthly_roi_series(db, artist_id, date(2000, 1, 1), date.today())
        if df_roi is None or df_roi.empty:
            st.info(t("trigger_algo.roi.no_revenue_spend",
                      "Pas de données revenue/spend pour calculer la régression ROI "
                      "(aucun mois avec spend Meta Ads + revenue iMusician dans l'historique)."))
            return
        fit = fit_spend_revenue(df_roi)
        if fit is None:
            st.info(t("trigger_algo.roi.insufficient_data",
                      "Données insuffisantes : il faut au moins {n} mois où coexistent un "
                      "spend Meta Ads ET un revenu distributeur. En dessous, une droite "
                      "passe presque exactement par les points et le R² ne mesure rien."
                      ).format(n=MIN_FIT_POINTS))
            return
        _render_fit(fit)
    except ImportError:
        st.warning(t("trigger_algo.roi.scipy_unavailable", "scipy non disponible — régression désactivée."))
    except Exception as e:
        st.warning(t("trigger_algo.roi.regression_unavailable",
                     "Graphique ROI indisponible : {err}").format(err=e))


def _render_fit(fit: dict) -> None:
    """R247 (fiche 45) — the months and the trend, then the DECISION in words. The
    equation, R² and p-value are gone from the page (owner : « sans équation ni R² ») :
    they decide the verdict below, they are not what the artist acts on."""
    from src.dashboard.utils.roi_verdicts import fit_decision
    x, y = fit["x"], fit["y"]
    x_line = np.linspace(x.min(), x.max(), 100)
    fig_roi = go.Figure()
    fig_roi.add_trace(go.Scatter(
        x=x, y=y, mode="markers+text", text=fit["labels"], textposition="top center",
        name=t("trigger_algo.roi.trace_monthly", "Mensuel"),
        marker=dict(color=BON, size=10)))
    fig_roi.add_trace(go.Scatter(
        x=x_line, y=fit["slope"] * x_line + fit["intercept"], mode="lines",
        name=t("trigger_algo.roi.trace_trend", "Tendance"),
        line=dict(color="#FF6B6B", width=2, dash="dash")))
    fig_roi.update_layout(
        title=t("trigger_algo.roi.regression_chart_title",
                "Revenue iMusician (€) vs Spend Meta Ads (€)"),
        xaxis_title=t("trigger_algo.roi.axis_meta_spend", "Dépenses Meta Ads (€)"),
        yaxis_title=t("trigger_algo.roi.axis_imusician_revenue", "Revenus iMusician (€)"),
        height=420, hovermode="closest")
    charts.plotly_chart(fig_roi, width='stretch')
    kind, slope = fit_decision(fit)
    text = {
        "none": t("trigger_algo.roi.decision_none",
                  "**Sur {n} mois, tes revenus ne suivent pas ta pub** — les mois où tu as "
                  "plus dépensé n'ont pas rapporté plus. Juge ta pub sur les écoutes qu'elle "
                  "apporte (onglets Meta), pas sur tes ventes."),
        "pays": t("trigger_algo.roi.decision_pays",
                  "**Sur {n} mois, chaque euro de pub a ramené environ {k} € de revenus** — "
                  "la pub se rembourse en ventes : tu peux l'augmenter prudemment."),
        "short": t("trigger_algo.roi.decision_short",
                   "**Sur {n} mois, chaque euro de pub n'a ramené qu'environ {k} € de "
                   "revenus** — elle ne se rembourse pas en ventes : garde-la pour ce "
                   "qu'elle apporte en écoutes, ou baisse-la."),
    }[kind]
    st.markdown(text.format(n=fit["n"], k=f"{slope:.2f}".replace(".", ",") if slope else ""))


def render_artist_money(db, artist_id: int) -> None:
    """The money pieces under the Trésorerie break-even (R553, ADR-033 decision 1): the
    whole-history ledger line, the cost entry, revenue against Meta spend (fiche 50), and
    what an algo trigger is worth (fiche 68 — a prediction, so Premium, ADR-029)."""
    from src.dashboard.utils.artist_cashflow import monthly_net
    from src.dashboard.utils.plan_gate import est_verrouille, note_de_plan
    from src.dashboard.utils.treasury_chart import load_cashflow
    cashflow = load_cashflow(db, artist_id)
    mensuel = monthly_net(cashflow)
    if not mensuel.empty:
        _render_ledger(db, artist_id, cashflow, mensuel)
    _render_cost_entry(db, artist_id)
    st.markdown("---")
    render_spend_revenue_fit(db, artist_id)
    if est_verrouille("revenue_forecast"):
        st.markdown("---")
        note_de_plan("revenue_forecast", ferme=t(
            "revenue_forecast.trigger_locked",
            "Ce qu'un déclenchement des algorithmes te rapporterait, et la projection "
            "de ton point mort : compris dans Premium"))
        return
    _render_trigger_value(db, artist_id, mensuel)


def render_ltv() -> None:
    """Fiche 67 — the subscriber LTV, the OPERATOR's number (R553, owner Y1 : « l'artiste ne
    doit pas voir ça »). Rendered by the admin page only, folded."""
    if is_admin():
        _frag_ltv()

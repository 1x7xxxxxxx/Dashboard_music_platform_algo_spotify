"""Money pieces of « 💶 Trésorerie » — the cost entry, the Premium note, the operator LTV.

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


import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import charts
from src.dashboard.utils.platform_colors import DISTINCT
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


def render_artist_money(db, artist_id: int) -> None:
    """Under the point mort figure: the Premium note when locked, then the cost entry.

    R566 (owner, Trésorerie 2026-10-15 : « on doit comprendre par le graphique seul ») —
    the fit verdict, the trigger paragraph and the ledger table are gone: the figure's
    title carries revenue, spend and ROI, the star carries the trigger value."""
    from src.dashboard.utils.plan_gate import est_verrouille, note_de_plan
    if est_verrouille("revenue_forecast"):
        note_de_plan("revenue_forecast", ferme=t(
            "revenue_forecast.trigger_locked",
            "Ce qu'un déclenchement des algorithmes te rapporterait, et la projection "
            "de ton point mort : compris dans Premium"))
    st.markdown("---")
    _render_cost_entry(db, artist_id)


def render_ltv() -> None:
    """Fiche 67 — the subscriber LTV, the OPERATOR's number (R553, owner Y1 : « l'artiste ne
    doit pas voir ça »). Rendered by the admin page only, folded."""
    if is_admin():
        _frag_ltv()

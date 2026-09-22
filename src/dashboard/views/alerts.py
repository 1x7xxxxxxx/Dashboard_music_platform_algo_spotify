"""Alerting Dashboard — Brick 30.

Type: Feature
Uses: get_db_connection, AirflowMonitor, get_source_freshness, freshness_status
Depends on: etl_circuit_breaker, etl_run_log, saas_users, artist_subscriptions
Accessible to all authenticated users (artists see their own data; admins see all).
"""
import html as _html

import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
)


# ── Section 1: Circuit breakers ───────────────────────────────────

def _section_circuit_breakers(db, artist_id) -> int:
    """Returns count of OPEN/HALF_OPEN circuits."""
    if artist_id is not None:
        rows = db.fetch_query(
            """
            SELECT platform, artist_id, state, failure_count, last_failure_at, last_error
            FROM etl_circuit_breaker
            WHERE artist_id = %s AND state != 'closed'
            ORDER BY state DESC, failure_count DESC
            """,
            (artist_id,),
        )
    else:
        rows = db.fetch_query(
            """
            SELECT platform, artist_id, state, failure_count, last_failure_at, last_error
            FROM etl_circuit_breaker
            WHERE state != 'closed'
            ORDER BY state DESC, failure_count DESC
            """
        )

    if not rows:
        from src.utils.circuit_breaker import circuit_mechanism_is_recording
        if circuit_mechanism_is_recording(db):
            st.success(t("alerts.circuits_all_closed",
                         "✅ All circuits closed — no platform collection failures."))
        else:
            # Pas un ✅ : rien n'écrit dans cette table, donc « aucun circuit
            # ouvert » ne dit rien de la santé des collectes.
            st.info(t(
                "alerts.circuits_not_recording",
                "ℹ️ Aucun circuit breaker n'a encore été enregistré. Ce panneau ne "
                "prouve donc **rien** sur l'état des collectes — la fraîcheur des "
                "données ci-dessous est la mesure qui fait foi."
            ))
        return 0

    for row in rows:
        platform, aid, state, failures, last_fail, last_error = row
        color = "#e74c3c" if state == "open" else "#f39c12"
        icon  = "🔴" if state == "open" else "🟡"
        fail_str = pd.to_datetime(last_fail).strftime("%d/%m %H:%M") if last_fail else "—"
        st.markdown(
            f"{icon} **{_html.escape(str(platform))}** "
            + t(
                "alerts.circuit_line",
                "(artist #{aid}) — <span style='color:{color};font-weight:bold'>{state}</span> — {failures} failure(s) — last: {fail_str}",
            ).format(
                aid=int(aid),
                color=_html.escape(color),
                state=_html.escape(state.upper()),
                failures=int(failures),
                fail_str=_html.escape(fail_str),
            ),
            unsafe_allow_html=True,
        )
        if last_error:
            st.caption(f"↳ {str(last_error)[:120]}")
    return len(rows)


# ── Section 2: Data freshness ─────────────────────────────────────

def _section_freshness_alerts(db, artist_id) -> int:
    """Returns count of stale (orange/red) sources."""
    freshness = get_source_freshness(db, artist_id)
    stale = [
        (label, info)
        for label, info in freshness.items()
        if freshness_status(info['last_dt'])[1] in ('#e74c3c', '#f39c12')
    ]
    if not stale:
        st.success(t("alerts.sources_all_fresh", "✅ All data sources are fresh."))
        return 0

    for label, info in stale:
        emoji, color, age_label = freshness_status(info['last_dt'])
        date_str = info['last_dt'].strftime("%d/%m %H:%M") if info['last_dt'] else "never"
        icon = "🔴" if color == '#e74c3c' else "🟡"
        st.markdown(
            f"{icon} **{_html.escape(label)}** — "
            + t(
                "alerts.freshness_line",
                "<span style='color:{color}'>{age_label}</span> (last: {date_str})",
            ).format(
                color=_html.escape(color),
                age_label=_html.escape(age_label),
                date_str=_html.escape(date_str),
            ),
            unsafe_allow_html=True,
        )
    return len(stale)


# ── Section 3: Recent DAG failures ───────────────────────────────

def _section_dag_failures(db, artist_id) -> int:
    """Returns count of DAG failures in the last 24 hours."""
    if artist_id is not None:
        df = db.fetch_df(
            """
            SELECT dag_id, platform, started_at, error_type, error_message
            FROM etl_run_log
            WHERE artist_id = %s AND status = 'failed'
              AND started_at >= NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC LIMIT 50
            """,
            (artist_id,),
        )
    else:
        df = db.fetch_df(
            """
            SELECT dag_id, platform, artist_id, started_at, error_type, error_message
            FROM etl_run_log
            WHERE status = 'failed'
              AND started_at >= NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC LIMIT 50
            """
        )

    if df.empty:
        st.success(t("alerts.no_dag_failures", "✅ No DAG failures in the last 24 hours."))
        return 0

    df['started_at'] = pd.to_datetime(df['started_at']).dt.strftime('%d/%m %H:%M')
    st.dataframe(df, hide_index=True, width="stretch")
    return len(df)


# ── Section 4: Suspicious login activity (admin only) ────────────

def _section_login_alerts(db) -> int:
    """Returns count of currently locked accounts."""
    rows = db.fetch_query(
        """
        SELECT username, email, failed_login_attempts, locked_until
        FROM saas_users
        WHERE locked_until > NOW()
        ORDER BY locked_until DESC
        """
    )
    if not rows:
        st.success(t("alerts.no_locked_accounts", "✅ No accounts currently locked."))
        return 0

    for uname, email, attempts, locked_until in rows:
        lu_str = pd.to_datetime(locked_until).strftime("%d/%m %H:%M") if locked_until else "—"
        st.markdown(
            f"🔒 **{_html.escape(str(uname))}** ({_html.escape(str(email))}) — "
            + t(
                "alerts.locked_line",
                "{attempts} failed attempt(s) — locked until {lu_str}",
            ).format(attempts=int(attempts), lu_str=_html.escape(lu_str))
        )
    return len(rows)


# ── Section 5: Billing / subscription alerts (admin only) ─────────

def _section_billing_alerts(db) -> int:
    rows = db.fetch_query(
        """
        SELECT a.name, asub.status, asub.current_period_end
        FROM artist_subscriptions asub
        JOIN saas_artists a ON a.id = asub.artist_id
        WHERE asub.status IN ('past_due', 'canceled', 'unpaid')
           OR (asub.status = 'active' AND asub.current_period_end < NOW() + INTERVAL '7 days')
        ORDER BY asub.current_period_end ASC
        """
    )
    if not rows:
        st.success(t("alerts.no_billing_issues", "✅ No billing issues detected."))
        return 0

    for artist_name, status, period_end in rows:
        end_str = pd.to_datetime(period_end).strftime("%d/%m/%Y") if period_end else "—"
        icon = "🔴" if status in ('past_due', 'unpaid', 'canceled') else "🟡"
        st.markdown(
            f"{icon} **{_html.escape(str(artist_name))}** — "
            + t(
                "alerts.billing_line",
                "status: `{status}` — period ends: {end_str}",
            ).format(status=_html.escape(str(status)), end_str=_html.escape(end_str))
        )
    return len(rows)


# ── Admin: subscription analytics ─────────────────────────────────

def _plans_a_tracer(hist) -> list[str]:
    """Les plans à dessiner : ce qu'on vend aujourd'hui ∪ ce que l'historique porte.

    Classe : `a-display-that-restates-a-catalogue-instead-of-reading-it`.
    """
    from src.database.stripe_schema import PLAN_CATALOG

    vendus = list(PLAN_CATALOG)
    vus = [p for p in hist['plan'].dropna().unique() if p not in vendus] \
        if hist is not None and 'plan' in getattr(hist, 'columns', []) else []
    return vendus + sorted(vus)


_PLAN_STATE_SQL = """
    SELECT sa.id,
           sa.created_at,
           sa.promo_plan,
           sa.promo_plan_expires_at,
           sp.name AS subscription_plan,
           sa.tier
      FROM saas_artists sa
      LEFT JOIN artist_subscriptions asub
        ON asub.artist_id = sa.id AND asub.status IN ('active', 'trialing')
      LEFT JOIN subscription_plans sp ON sp.id = asub.plan_id
     ORDER BY sa.id
"""


def _plan_events(hist, etats, now):
    """Les transitions de plan RÉELLES. Le journal seul en rate la moitié.

    ⚠️ MESURÉ EN PRODUCTION LE 2026-09-22 — quatre artistes sur huit étaient faux,
    et la figure affirmait **5 Premium sur 6 artistes** quand le résolveur de plan
    en voyait **2 sur 8**. Le total lui-même manquait deux comptes.

    `subscription_plan_history` est un journal *append-only*, et il ne porte que ce
    que quelqu'un a pensé à y écrire. Trois trous, chacun observé :

      · **L'expiration d'un essai n'est écrite nulle part.** `_grant_welcome_trial`
        pose `promo_plan_expires_at` et `plan_resolver` la relit À CHAQUE LECTURE ;
        aucun travail de fond ne journalise le jour où elle tombe. Un essayeur
        restait donc « Premium » pour l'éternité sur cette figure — trois artistes
        en production, essais clos depuis le 2026-07-14, le 2026-07-15 et le
        2026-09-11.
      · **Une inscription ne garantit pas une ligne.** `log_plan_change` avale ses
        erreurs par conception (« un échec de journal ne doit jamais casser
        l'inscription »), et le remplissage de la migration 029 ne couvrait que les
        comptes existants ce jour-là. Deux artistes nés après n'avaient aucune
        ligne : la figure les ignorait purement et simplement.
      · **Un plan posé hors du chemin d'inscription** (édition admin d'une colonne,
        code promo appliqué à la main) ne passe par aucun appelant de
        `log_plan_change`.

    La parade tient en une phrase : **le journal décrit le PASSÉ, le résolveur décrit
    MAINTENANT.** On ne devine donc aucune date de rétroaction ; on ajoute trois
    évènements de synthèse, et le dernier point de la courbe est celui qui fait foi :

      1. une **naissance** à `created_at` (plan gratuit) quand le journal ne porte
         rien à cette date ou avant — sans elle, un compte n'existe pas sur la figure ;
      2. une **expiration** à `promo_plan_expires_at` quand elle est passée, portant
         le plan d'APRÈS (abonnement actif, sinon `tier`, sinon gratuit) — c'est
         exactement la précédence de `plan_from_row`, et c'est ce qui redresse les
         seaux passés ;
      3. un **ancrage à maintenant** valant la résolution de `plan_resolver`. Le
         dernier seau, celui que lisent les quatre tuiles sous la figure, ne peut
         alors plus contredire ce que l'artiste voit dans son propre compte.

    L'ancrage a un coût assumé : un plan accordé hors journal apparaît à la date
    d'AUJOURD'HUI et non à celle de l'octroi, qu'aucune colonne ne porte. Une
    marche tardive vaut mieux qu'un compte manquant ou qu'un Premium immortel.

    Garde : `tests/test_the_plan_chart_agrees_with_the_plan_resolver.py`.
    """
    from src.database.stripe_schema import normalize_plan
    from src.utils.plan_resolver import plan_from_row

    lignes = [] if hist is None or hist.empty else [
        {'artist_id': int(r.artist_id), 'plan': r.plan, 'changed_at': r.changed_at}
        for r in hist.itertuples()
    ]
    premiere = {}
    for e in lignes:
        d = e['changed_at']
        if e['artist_id'] not in premiere or d < premiere[e['artist_id']]:
            premiere[e['artist_id']] = d

    for a in etats.itertuples():
        aid = int(a.id)
        naissance = pd.Timestamp(a.created_at).tz_localize(None) \
            if pd.notna(a.created_at) else None
        # 1. la naissance — un compte que le journal ignore existe quand même.
        if naissance is not None and (aid not in premiere or premiere[aid] > naissance):
            lignes.append({'artist_id': aid, 'plan': 'free', 'changed_at': naissance})
        # 2. l'expiration — le seul évènement que personne n'écrit.
        exp = pd.Timestamp(a.promo_plan_expires_at).tz_localize(None) \
            if pd.notna(a.promo_plan_expires_at) else None
        if exp is not None and exp <= now:
            apres = normalize_plan(a.subscription_plan) if a.subscription_plan \
                else (normalize_plan(a.tier) if a.tier else 'free')
            lignes.append({'artist_id': aid, 'plan': apres, 'changed_at': exp})
        # 3. l'ancrage — maintenant, c'est le résolveur qui a raison.
        lignes.append({
            'artist_id': aid,
            'plan': plan_from_row((a.promo_plan, a.promo_plan_expires_at,
                                   a.subscription_plan, a.tier)),
            'changed_at': now,
        })

    return pd.DataFrame(lignes).sort_values('changed_at')


def _section_plan_evolution(db) -> None:
    """Stacked-area chart of the number of artists per plan over time.

    Reconstructs each artist's effective plan as-of monthly snapshots from the
    append-only subscription_plan_history table (seeded by migration 029's
    backfill). Returns nothing — purely informational (no alert count).
    """
    import plotly.express as px

    rows = db.fetch_query(
        "SELECT artist_id, plan, changed_at FROM subscription_plan_history "
        "ORDER BY changed_at"
    )
    etats = pd.DataFrame(
        db.fetch_query(_PLAN_STATE_SQL),
        columns=['id', 'created_at', 'promo_plan', 'promo_plan_expires_at',
                 'subscription_plan', 'tier'],
    )
    if etats.empty:
        st.info(
            t(
                "alerts.no_plan_history",
                "Aucun historique de plan pour l'instant. Le graphique se remplit "
                "au fil des inscriptions et des changements de plan.",
            )
        )
        return

    hist = pd.DataFrame(rows or [], columns=['artist_id', 'plan', 'changed_at'])
    # Normalise to tz-naive UTC so comparisons with the bucket timestamps work.
    if not hist.empty:
        hist['changed_at'] = pd.to_datetime(hist['changed_at'], utc=True).dt.tz_localize(None)

    # Le journal ne porte ni les expirations d'essai ni les comptes qu'il a ratés —
    # `_plan_events` les rétablit, et ancre le dernier point sur le résolveur.
    now = pd.Timestamp.utcnow().tz_localize(None)
    evts = _plan_events(hist, etats, now)

    start = evts['changed_at'].min().normalize().replace(day=1)
    buckets = pd.date_range(start=start, end=now.normalize(), freq='MS')
    # Always include "now" as the final point so the latest state is shown.
    buckets = buckets.append(pd.DatetimeIndex([now])).unique()

    records = []
    for b in buckets:
        asof = evts[evts['changed_at'] <= b]
        if asof.empty:
            continue
        latest = asof.sort_values('changed_at').groupby('artist_id').tail(1)
        counts = latest['plan'].value_counts()
        # ⚠️ LES PLANS SE LISENT, ILS NE SE RECOPIENT PAS — 2026-09-22.
        #
        # Cette ligne était `('free', 'basic', 'premium')`. `basic` a été RETIRÉ du
        # catalogue : `PLAN_CATALOG` et `PLAN_FEATURES` n'en portent plus que deux.
        # La figure dessinait donc une bande « Basic » plate à zéro pour toujours —
        # un plan que le produit ne vend plus, montré à l'exploitant comme s'il
        # existait. Et symétriquement, un plan AJOUTÉ n'y serait jamais apparu.
        #
        # On prend l'union de ce que le catalogue vend AUJOURD'HUI et de ce que
        # l'historique contient RÉELLEMENT : un plan retiré reste visible sur la
        # période où il a existé — c'est un historique, l'effacer le falsifierait —
        # et un plan neuf apparaît tout seul.
        for plan in _plans_a_tracer(evts):
            records.append({'Date': b, 'Plan': plan.capitalize(),
                            'Artistes': int(counts.get(plan, 0))})

    chart_df = pd.DataFrame(records)
    if chart_df.empty:
        # No plan-history rows yet (fresh tenant / fresh install) → px.area would raise
        # "'x' is not a column" on a column-less empty frame. Show an empty state instead.
        st.info(t("alerts.no_plan_history", "Pas encore d'historique de plans à afficher."))
        return
    fig = px.area(
        chart_df, x='Date', y='Artistes', color='Plan',
        category_orders={'Plan': ['Free', 'Basic', 'Premium']},
        color_discrete_map={'Free': '#9E9E9E', 'Basic': '#2196F3', 'Premium': '#1DB954'},
        title=t("alerts.plan_chart_title", "Évolution du nombre d'artistes — total et par plan"),
    )
    # Explicit total-artists line on top of the per-plan stacked areas.
    totals = chart_df.groupby('Date', as_index=False)['Artistes'].sum()
    fig.add_scatter(
        x=totals['Date'], y=totals['Artistes'],
        mode='lines+markers', name=t("alerts.total_artists", "Total artistes"),
        line=dict(color='#FFFFFF', width=2, dash='dot'),
    )
    fig.update_layout(hovermode='x unified', height=400, legend_title_text='')
    st.plotly_chart(fig, width="stretch")

    # Current snapshot KPIs (latest bucket).
    latest_date = chart_df['Date'].max()
    snap = chart_df[chart_df['Date'] == latest_date]
    cols = st.columns(4)
    cols[0].metric(t("alerts.total_artists", "Total artistes"), int(snap['Artistes'].sum()))
    for col, plan in zip(cols[1:], ['Free', 'Basic', 'Premium']):
        val = int(snap[snap['Plan'] == plan]['Artistes'].sum())
        col.metric(plan, val)


# Le repère de *Lean Analytics* pour un essai SANS carte bancaire : 15 % des essais
# deviennent payants (50 % quand la carte est prise à l'inscription). C'est un chiffre
# de 2013 sur des SaaS B2B — il donne un ordre de grandeur, pas une cible.
_REPERE_CONVERSION = 0.15


def _essais_avant_de_douter(repere: float = _REPERE_CONVERSION, seuil: float = 0.05) -> int:
    """Combien d'essais doivent finir À ZÉRO avant que le repère soit en cause.

    Une série de zéros n'est un signal que si elle est improbable sous le repère.
    Sous 15 %, observer zéro conversion sur `n` essais a la probabilité `0,85**n` ;
    on cherche le premier `n` qui passe sous 5 %.

    Ce nombre existe pour une raison précise, et c'est la leçon de R147 : avec trois
    essais arrivés à terme, « 0 % de conversion » et « 15 % de conversion » sont la
    MÊME observation. Afficher un pourcentage là-dessus invente une information.
    """
    from math import ceil, log

    return int(ceil(log(seuil) / log(1 - repere)))


def _trial_cohorts(etats, hist, now):
    """Les cohortes d'essai, avec leur EFFECTIF — jamais un taux nu.

    R147 (2026-09-22), née d'une phrase de *Product-Led Growth* (Wes Bush) : « you
    need to start with a free trial. Once your free trial is proven to convert, you
    can consider freemium. » streaMLytics fait les deux à la fois — trente jours de
    Premium à l'inscription, puis un plan gratuit ILLIMITÉ — et personne n'avait
    jamais regardé ce que font les comptes au jour 31.

    ⚠️ **La prémisse de la tâche était à moitié fausse, et c'est ce qui a fait
    écrire cette fonction ainsi.** La roadmap disait « `subscription_plan_history`
    et `log_plan_change` portent déjà la donnée ». Vérifié en production : le
    journal porte l'OCTROI (`welcome_trial`) et la CONVERSION (`stripe_webhook`),
    mais **jamais l'expiration** — aucun travail de fond ne l'écrit, `plan_resolver`
    la recalcule à chaque lecture. La fin d'un essai se lit donc dans
    `saas_artists.promo_plan_expires_at`, et nulle part ailleurs.

    Trois colonnes, trois questions distinctes :
      · **accordés** — combien d'essais ont commencé ce mois-là ;
      · **arrivés à terme** — combien ont atteint leur jour 30 (les autres courent
        encore : les compter dans un dénominateur les compterait comme des échecs) ;
      · **devenus payants** — un abonnement actif, ou une ligne `stripe_webhook`
        postérieure à la fin de l'essai.

    Le taux n'est rendu que lorsqu'il veut dire quelque chose ; en dessous,
    `_essais_avant_de_douter()` dit combien il en faudrait. Mesuré en production le
    2026-09-22 : **trois essais arrivés à terme, zéro conversion** — et zéro sur
    trois est parfaitement compatible avec le repère de 15 %.
    """
    from src.database.stripe_schema import normalize_plan

    paiements = {}
    if hist is not None and not hist.empty:
        for r in hist.itertuples():
            if getattr(r, 'source', None) == 'stripe_webhook':
                aid = int(r.artist_id)
                d = r.changed_at
                if aid not in paiements or d < paiements[aid]:
                    paiements[aid] = d

    lignes = []
    for a in etats.itertuples():
        if pd.isna(a.promo_plan_expires_at):
            continue                       # pas d'essai : rien à suivre
        aid = int(a.id)
        fin = pd.Timestamp(a.promo_plan_expires_at).tz_localize(None)
        debut = pd.Timestamp(a.created_at).tz_localize(None) \
            if pd.notna(a.created_at) else fin
        paye = (a.subscription_plan is not None
                and normalize_plan(a.subscription_plan) != 'free') \
            or (aid in paiements and paiements[aid] >= fin)
        lignes.append({
            'artist_id': aid,
            'Cohorte': debut.strftime('%Y-%m'),
            'accordes': 1,
            'termines': int(fin <= now),
            'payants': int(bool(paye)),
        })

    if not lignes:
        return pd.DataFrame(columns=['Cohorte', 'accordes', 'termines', 'payants'])
    return (pd.DataFrame(lignes)
            .groupby('Cohorte', as_index=False)[['accordes', 'termines', 'payants']]
            .sum()
            .sort_values('Cohorte'))


def _section_trial_cohorts(db) -> None:
    """R147 — ce que font les comptes au jour 31, avec l'effectif en face."""
    rows = db.fetch_query(
        "SELECT artist_id, plan, changed_at, source FROM subscription_plan_history "
        "ORDER BY changed_at"
    )
    hist = pd.DataFrame(rows or [],
                        columns=['artist_id', 'plan', 'changed_at', 'source'])
    if not hist.empty:
        hist['changed_at'] = pd.to_datetime(hist['changed_at'], utc=True).dt.tz_localize(None)
    etats = pd.DataFrame(
        db.fetch_query(_PLAN_STATE_SQL),
        columns=['id', 'created_at', 'promo_plan', 'promo_plan_expires_at',
                 'subscription_plan', 'tier'],
    )
    now = pd.Timestamp.utcnow().tz_localize(None)
    coh = _trial_cohorts(etats, hist, now)

    if coh.empty:
        st.info(t("alerts.no_trial_cohort",
                  "Aucun essai accordé pour l'instant — la courbe se remplit à la "
                  "première inscription."))
        return

    termines = int(coh['termines'].sum())
    payants = int(coh['payants'].sum())
    seuil = _essais_avant_de_douter()

    # ⚠️ REPLIÉ, ET C'EST LA DISCIPLINE DE R149 APPLIQUÉE À SOI-MÊME.
    #
    # Ces quatre figures ont fait passer la vue Alertes de 5 à 7 au premier écran, et
    # le cliquet `test_the_first_screen_counts_its_gauges` l'a dit tout de suite. La
    # tentation était de relever le plafond : ç'aurait été ajouter des tuiles le jour
    # même où l'on écrit qu'il y en a trop. Une cohorte se consulte périodiquement,
    # elle n'alerte de rien — sa place est sous un dépliant.
    #
    # Le repli doit être STRUCTUREL : un `with` dans une fonction appelée depuis un
    # dépliant est invisible à l'AST du garde.
    with st.expander(t("alerts.trial_expander",
                       "🎟️ Détail des cohortes d'essai"), expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric(t("alerts.trial_granted", "Essais accordés"), int(coh['accordes'].sum()))
        c2.metric(t("alerts.trial_matured", "Arrivés au jour 30"), termines)
        c3.metric(t("alerts.trial_paid", "Devenus payants"), payants)

        affichage = coh.rename(columns={
            'accordes': t("alerts.trial_col_granted", "Accordés"),
            'termines': t("alerts.trial_col_matured", "Arrivés à terme"),
            'payants': t("alerts.trial_col_paid", "Payants"),
        })
        st.dataframe(affichage, width="stretch", hide_index=True)

        if termines >= seuil:
            st.metric(t("alerts.trial_rate", "Taux de conversion des essais"),
                      f"{payants / termines:.0%}")
            st.caption(t("alerts.trial_rate_bench",
                         "Repère *Lean Analytics* pour un essai sans carte bancaire : "
                         "≈ 15 %.").replace("*", ""))
        else:
            # Le point de R147 : sous cet effectif, un pourcentage serait une invention.
            st.info(t(
                "alerts.trial_too_few",
                "**{payants} conversion(s) sur {termines} essai(s) arrivé(s) à terme.** "
                "Aucun taux n'est affiché : sous le repère de 15 % (essai sans carte "
                "bancaire, *Lean Analytics*), il faudrait **{seuil} essais** terminés "
                "sans une seule conversion pour que ce repère soit en cause. Les essais "
                "en cours ne sont pas comptés — ce ne sont pas encore des échecs."
            ).format(payants=payants, termines=termines, seuil=seuil))
def _section_users_table(db) -> None:
    """Table of every user: email, signup date, and effective plan."""
    from datetime import datetime, timezone

    rows = db.fetch_query(
        "SELECT u.email, u.username, u.role, u.created_at, "
        "       a.tier, a.promo_plan, a.promo_plan_expires_at "
        "FROM saas_users u "
        "LEFT JOIN saas_artists a ON a.id = u.artist_id "
        "ORDER BY u.created_at DESC"
    )
    if not rows:
        st.info(t("alerts.no_users", "Aucun utilisateur enregistré."))
        return

    now = datetime.now(timezone.utc)

    def _effective_plan(tier, promo_plan, promo_exp) -> str:
        if promo_plan and (promo_exp is None or promo_exp > now):
            return promo_plan
        return tier or 'free'

    table = []
    for email, username, role, created_at, tier, promo_plan, promo_exp in rows:
        table.append({
            t("alerts.col_email", "Email"): email,
            t("alerts.col_username", "Username"): username,
            t("alerts.col_role", "Rôle"): role,
            t("alerts.col_signup", "Inscription"): created_at.strftime('%Y-%m-%d') if created_at else "—",
            t("alerts.col_plan", "Plan"): _effective_plan(tier, promo_plan, promo_exp).capitalize(),
        })
    st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)


# ── Entry point ───────────────────────────────────────────────────

def show():
    st.title(t("alerts.title", "🚨 Alerting Dashboard"))
    st.caption(t("alerts.caption", "Real-time status of platform health, data freshness, and security events."))

    # Tenant first, connection second: the `st.stop()` below raised between the
    # open and the `try`, so the `finally` never ran and the connection leaked.
    # Same fix as `utils.view_session()` and `db_health.show()`.
    artist_id = get_artist_id()
    if artist_id is None and not is_admin():
        st.error(t("alerts.invalid_session", "Session invalide."))
        st.stop()

    db = get_db_connection()
    if db is None:
        st.error(t("alerts.db_unreachable", "❌ Database unreachable."))
        return

    admin = is_admin()

    try:
        # Summary banner
        total_alerts = 0

        st.subheader(t("alerts.section_circuits", "🔌 Circuit Breakers"))
        total_alerts += _section_circuit_breakers(db, artist_id)
        st.markdown("---")

        st.subheader(t("alerts.section_freshness", "📡 Data Freshness"))
        total_alerts += _section_freshness_alerts(db, artist_id)
        st.markdown("---")

        st.subheader(t("alerts.section_dag_failures", "❌ DAG Failures (last 24h)"))
        total_alerts += _section_dag_failures(db, artist_id)

        if admin:
            st.markdown("---")
            st.subheader(t("alerts.section_locked", "🔒 Locked Accounts"))
            total_alerts += _section_login_alerts(db)
            st.markdown("---")
            st.subheader(t("alerts.section_billing", "💳 Billing Alerts"))
            total_alerts += _section_billing_alerts(db)
            st.markdown("---")
            st.subheader(t("alerts.section_plan_evolution", "📈 Évolution des plans"))
            _section_plan_evolution(db)
            st.markdown("---")
            st.subheader(t("alerts.section_trial_cohorts",
                           "🎟️ Essais de 30 jours — ce qu'ils deviennent"))
            _section_trial_cohorts(db)
            st.markdown("---")
            st.subheader(t("alerts.section_users", "👥 Utilisateurs (email & date d'inscription)"))
            _section_users_table(db)

        if total_alerts == 0:
            st.balloons()
            st.success(t("alerts.all_healthy", "✅ Everything looks healthy. No active alerts."))
        else:
            st.sidebar.error(
                t("alerts.active_count", "🚨 {n} active alert(s)").format(n=total_alerts)
            )

    finally:
        db.close()

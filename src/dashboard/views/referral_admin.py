"""Referral admin KPI page — admin-only.

Type: Feature
Uses: get_db_connection, is_admin
Depends on: referral_events, referral_codes, saas_artists, artist_subscriptions tables
Persists in: read-only view

Shows referral program metrics: total referrals, free months granted,
conversion rate, top referrers, and full event log.
"""
import streamlit as st
import pandas as pd

from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t
from src.dashboard.auth import is_admin


def _guard():
    if not is_admin():
        st.error(t("referral_admin.admin_only", "⛔ Accès réservé aux administrateurs."))
        st.stop()


# ── LES CRÉANCES À HONORER — 2026-09-21 ────────────────────────────────────
#
# Ce panneau existe parce que la promesse n'est pas automatique, et que le dire à
# l'artiste ne suffit pas : il faut que quelqu'un puisse la TENIR.
#
# Balayé le 2026-09-21 : **rien dans l'arbre ne consomme `referral_free_months`
# ni `first_month_discount_pct`**. Aucun coupon Stripe, aucune prolongation
# d'essai, aucun avoir. La montée en gamme passe par un lien de paiement statique
# (`STRIPE_CHECKOUT_URL`), qui ne peut porter de remise par client sans un appel à
# l'API Stripe que personne n'écrit. Les deux colonnes sont écrites à
# l'inscription, affichées sur deux pages, et lues par personne.
#
# Personne n'a encore été lésé — zéro parrainage en base ce jour-là. C'est
# précisément la fenêtre où l'on peut corriger sans dette : au premier filleul,
# la promesse devient un impayé.
#
# ⚠️ Ce panneau ne REMPLACE PAS l'automatisation, il la rend inutile pour
# survivre. Poser les coupons Stripe reste une brique de roadmap ; en attendant,
# l'exploitant a la liste, chiffrée, de ce qu'il doit.
_Q_CREANCES = """
SELECT sa.id, sa.name,
       sa.referral_free_months        AS mois_offerts,
       sa.first_month_discount_pct    AS remise_pct,
       sp.name                        AS plan,
       sp.price_monthly               AS prix,
       asub.status                    AS statut,
       asub.current_period_end        AS prochain_paiement
FROM saas_artists sa
LEFT JOIN artist_subscriptions asub ON asub.artist_id = sa.id
LEFT JOIN subscription_plans sp     ON sp.id = asub.plan_id
WHERE COALESCE(sa.referral_free_months, 0) > 0
   OR COALESCE(sa.first_month_discount_pct, 0) > 0
ORDER BY sa.referral_free_months DESC NULLS LAST, sa.name
"""


def _render_creances(db) -> None:
    """Ce que le programme DOIT, et à qui — en euros."""
    st.markdown("---")
    st.subheader(t("referral_admin.owed_header",
                   "🧾 Récompenses à appliquer À LA MAIN"))

    df = db.fetch_df(_Q_CREANCES)
    if df is None or df.empty:
        st.success(t("referral_admin.owed_none",
                     "Aucune récompense en attente. Rien à appliquer aujourd'hui."))
        st.caption(t(
            "referral_admin.owed_why",
            "Ce panneau existe parce que `referral_free_months` et "
            "`first_month_discount_pct` ne sont consommés par AUCUN code : le lien "
            "de paiement Stripe est statique et ne porte pas de remise par client. "
            "Les deux pages qui les affichent le disent désormais à l'artiste."))
        return

    for c in ("mois_offerts", "remise_pct", "prix"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    # La valeur d'un mois offert est le PRIX DU PLAN de l'artiste, pas un tarif
    # moyen : un parrain resté en Free ne coûte rien tant qu'il ne s'abonne pas.
    df["valeur_eur"] = df["mois_offerts"] * df["prix"]

    # ⚠️ UNE SEULE JAUGE, ET C'EST UN ARBITRAGE, pas une économie de place.
    #
    # Trois jauges portaient cette section, et le cliquet du premier écran a
    # rougi : cette page en affichait 7 pour un plafond de 5. Plutôt que de lui
    # inventer une exemption, on choisit — et le choix est instructif.
    #
    # La jauge gardée est le nombre de MOIS, pas la valeur en euros. La valeur
    # vaut 0,00 € tant que les parrains n'ont pas d'abonnement payant, ce qui se
    # lit « rien à payer » alors que la dette existe ; les mois, eux, sont dus
    # quoi qu'il arrive. Les deux autres chiffres descendent dans la légende, où
    # ils informent sans occuper le regard.
    st.metric(t("referral_admin.owed_months", "Mois offerts dus"),
              int(df["mois_offerts"].sum()))
    st.caption(t(
        "referral_admin.owed_summary",
        "{n} artiste(s) concerné(s) · **{v} €** à honorer au tarif de leur plan "
        "actuel."
    ).format(n=len(df),
             v=f"{float(df['valeur_eur'].sum()):,.2f}".replace(",", " ")))

    # ⚠️ « 0,00 € » à côté de « 3 mois offerts dus » se lit « rien à payer », et
    # c'est faux : un parrain resté en Free ne coûte rien AUJOURD'HUI, et coûtera
    # trois mois le jour où il s'abonne. Vu au rendu le 2026-09-21 sur l'artiste 1,
    # qui n'a pas de ligne d'abonnement. Le dire vaut mieux qu'un zéro muet.
    _dormants = int((df["prix"] <= 0).sum())
    if _dormants:
        st.caption(t(
            "referral_admin.owed_dormant",
            "⏳ **{n} de ces artistes n'ont pas d'abonnement payant** : leurs mois "
            "offerts ne coûtent rien tant qu'ils ne s'abonnent pas, et la valeur "
            "ci-dessus les compte donc à zéro. Elle montera d'un coup le jour où "
            "ils passent à l'acte — c'est une dette, pas une absence."
        ).format(n=_dormants))

    st.dataframe(
        df.rename(columns={
            "name": t("common.artist", "Artiste"),
            "mois_offerts": t("referral_admin.col_months", "Mois offerts"),
            "remise_pct": t("referral_admin.col_discount", "Remise 1er mois (%)"),
            "plan": t("referral_admin.col_plan", "Plan"),
            "prix": t("referral_admin.col_price", "Prix (€)"),
            "statut": t("referral_admin.col_status", "Statut"),
            "prochain_paiement": t("referral_admin.col_next", "Prochain paiement"),
            "valeur_eur": t("referral_admin.col_value", "Valeur (€)"),
        }).drop(columns=["id"]),
        width="stretch", hide_index=True)
    st.caption(t(
        "referral_admin.owed_howto",
        "Geste : portail Stripe → l'abonnement de l'artiste → **ajouter un coupon** "
        "(100 % sur N mois, ou {pct} % sur le premier) → remettre sa colonne à zéro "
        "en base. Tant que ce n'est pas automatisé, cette liste EST le programme."
    ).format(pct=int(df["remise_pct"].max())))


def show():
    _guard()
    st.title(t("referral_admin.title", "📊 Programme de parrainage — KPIs"))
    st.markdown("---")

    with project_db() as db:
        # ── Global KPIs ────────────────────────────────────────────────────
        total_row = db.fetch_query("SELECT COUNT(*) FROM referral_events")
        total_referrals = total_row[0][0] if total_row else 0

        free_months_row = db.fetch_query(
            "SELECT COALESCE(SUM(referral_free_months), 0) FROM saas_artists"
        )
        total_free_months = free_months_row[0][0] if free_months_row else 0

        converted_row = db.fetch_query(
            """
            SELECT COUNT(DISTINCT re.referred_artist_id)
            FROM referral_events re
            JOIN artist_subscriptions asub ON asub.artist_id = re.referred_artist_id
            WHERE asub.status IN ('active', 'trialing')
            """
        )
        converted = converted_row[0][0] if converted_row else 0
        conversion_rate = f"{(converted / total_referrals * 100):.1f}%" if total_referrals else "—"

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(t("referral_admin.metric_total_referrals", "Parrainages totaux"), total_referrals)
        col2.metric(t("referral_admin.metric_converted", "Convertis en payant"), converted)
        col3.metric(t("referral_admin.metric_conversion_rate", "Taux de conversion"), conversion_rate)
        col4.metric(t("referral_admin.metric_free_months", "Mois offerts accordés"), int(total_free_months))

        st.markdown("---")

        # ── Top referrers ──────────────────────────────────────────────────
        st.subheader(t("referral_admin.top_referrers", "Meilleurs parrains"))

        top_rows = db.fetch_query(
            """
            SELECT sa.name,
                   COUNT(re.id)               AS referrals_made,
                   sa.referral_free_months    AS free_months_earned,
                   rc.uses_count              AS code_uses,
                   rc.code
            FROM referral_events re
            JOIN saas_artists sa ON sa.id = re.referrer_artist_id
            LEFT JOIN referral_codes rc ON rc.artist_id = sa.id
            GROUP BY sa.id, sa.name, sa.referral_free_months, rc.uses_count, rc.code
            ORDER BY referrals_made DESC
            LIMIT 20
            """
        )

        if top_rows:
            df_top = pd.DataFrame(
                top_rows,
                columns=["Artist", "Referrals made", "Free months earned", "Code uses", "Code"],
            )
            st.dataframe(
                df_top,
                hide_index=True,
                width="stretch",
                column_config={
                    "Artist": t("referral_admin.col_artist", "Artiste"),
                    "Referrals made": t("referral_admin.col_referrals_made", "Parrainages réalisés"),
                    "Free months earned": t("referral_admin.col_free_months_earned", "Mois offerts gagnés"),
                    "Code uses": t("referral_admin.col_code_uses", "Utilisations du code"),
                    "Code": t("referral_admin.col_code", "Code"),
                },
            )
        else:
            st.info(t("referral_admin.no_referrals", "Aucun parrainage enregistré pour l'instant."))

        st.markdown("---")

        # ── Full event log ─────────────────────────────────────────────────
        st.subheader(t("referral_admin.all_events", "Tous les événements de parrainage"))

        log_rows = db.fetch_query(
            """
            SELECT
                referrer.name                                       AS referrer,
                referred.name                                       AS referred,
                re.code_used,
                re.created_at::date                                 AS date,
                COALESCE(sp.name, 'free')                           AS referred_plan
            FROM referral_events re
            JOIN saas_artists referrer  ON referrer.id  = re.referrer_artist_id
            JOIN saas_artists referred  ON referred.id  = re.referred_artist_id
            LEFT JOIN artist_subscriptions asub ON asub.artist_id = re.referred_artist_id
            LEFT JOIN subscription_plans sp     ON sp.id          = asub.plan_id
            ORDER BY re.created_at DESC
            """
        )

        if log_rows:
            df_log = pd.DataFrame(
                log_rows,
                columns=["Referrer", "Referred", "Code used", "Date", "Referred's plan"],
            )
            df_log["Date"] = df_log["Date"].astype(str)
            st.dataframe(
                df_log,
                hide_index=True,
                width="stretch",
                column_config={
                    "Referrer": t("referral_admin.col_referrer", "Parrain"),
                    "Referred": t("referral_admin.col_referred", "Filleul"),
                    "Code used": t("referral_admin.col_code_used", "Code utilisé"),
                    "Date": t("referral_admin.col_date", "Date"),
                    "Referred's plan": t("referral_admin.col_referred_plan", "Plan du filleul"),
                },
            )
        else:
            st.info(t("referral_admin.no_events", "Aucun événement de parrainage pour l'instant."))

        # Les créances EN DERNIER : ce sont les KPI qui disent s'il y a lieu de
        # regarder, et la liste qui dit quoi faire. L'ordre suit la question.
        _render_creances(db)

"""Referral page — artist-facing referral program.

Type: Feature
Uses: get_db_connection, get_artist_id
Depends on: referral_codes table, referral_events table, saas_artists table
Persists in: PostgreSQL spotify_etl (referral_codes, referral_events, saas_artists)

Accessible to all plans (free, basic, premium).
Each artist gets one unique code. Referrer earns +1 free month per successful referral.
"""
import os
import secrets
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import tenant_scope


def _get_or_create_code(db, artist_id: int) -> str:
    """Return this artist's referral code, creating it once — atomically.

    C'était un SELECT puis, s'il ne rendait rien, un INSERT. Deux rendus de la page
    qui se croisent lisent tous les deux « aucun code », insèrent tous les deux, et
    le second viole `referral_codes_artist_id_key` : la page CRASHE. Ce n'est pas une
    hypothèse — la CI l'a produit le 2026-09-06 (`duplicate key value violates unique
    constraint "referral_codes_artist_id_key"`, `referral.show()` en erreur), et
    Streamlit re-exécute le script à chaque interaction, donc un double-clic ou deux
    onglets suffisent chez un artiste.

    `ON CONFLICT … DO UPDATE SET code = referral_codes.code` plutôt que `DO NOTHING` :
    `DO NOTHING` ne rend AUCUNE ligne sur conflit, ce qui ramène le problème sous une
    autre forme — il faudrait re-SELECT, et on serait à deux allers-retours pour la
    même course. Le `DO UPDATE` réécrit la valeur existante par elle-même, ce qui est
    un no-op, et `RETURNING` rend le code dans tous les cas.
    """
    code = secrets.token_hex(3).upper()  # e.g. "A3F8C1"
    row = db.fetch_query(
        "INSERT INTO referral_codes (artist_id, code) VALUES (%s, %s) "
        "ON CONFLICT (artist_id) DO UPDATE SET code = referral_codes.code "
        "RETURNING code",
        (artist_id, code),
    )
    return row[0][0]


def show():
    st.title(t("referral.title", "🎁 Programme de parrainage"))
    st.caption(t("referral.caption",
                 "Partagez votre code — gagnez 1 mois gratuit pour chaque artiste "
                 "qui s'abonne avec."))

    # None here now means admin and only admin — a tenant-less artist session is
    # stopped by tenant_scope() instead of being told it is an admin account.
    artist_id = tenant_scope()
    if artist_id is None:
        st.info(t("referral.admin_na",
                  "Le programme de parrainage n'est pas disponible pour les comptes admin."))
        return

    db = get_db_connection()
    if db is None:
        st.error(t("referral.db_unreachable", "❌ Base de données injoignable."))
        return

    try:
        code = _get_or_create_code(db, artist_id)

        # ── Your code ─────────────────────────────────────────────────────
        # ── LE LIEN, PAS SEULEMENT LE CODE — 2026-09-21 ──────────────────
        #
        # La page donnait `A3F8C1` et disait « partagez-le ». Entre ce code et un
        # filleul inscrit, il y avait quatre gestes à sa charge : ouvrir le site,
        # trouver « créer un compte », repérer un champ nommé « Code promo ou
        # parrainage » au milieu de six autres, et retaper six caractères sans se
        # tromper. Chacun perd du monde, et aucun n'était nécessaire :
        # `register.py` lit maintenant `?ref=` et pré-remplit le champ.
        #
        # Le code reste affiché à côté, pour un filleul qui s'inscrit sans le lien : il
        # le tape dans le MÊME champ du formulaire d'inscription (R462 — la page disait
        # « pour le dire à l'oral » sans dire où il se saisit).
        st.subheader(t("referral.your_link", "Ton lien d'invitation"))
        base = os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/")
        lien = f"{base}/?page=register&ref={code}"
        st.code(lien, language=None)
        st.caption(
            t("referral.link_caption",
              "Envoie ce lien : le code est posé tout seul dans le formulaire "
              "d'inscription. Ton filleul obtient **20 % sur son premier mois "
              "payant**, et tu gagnes **1 mois offert** quand il s'abonne. "
              "(Chaque nouvel inscrit reçoit aussi **30 jours de Premium** "
              "automatiquement, parrainage ou non.)")
        )
        # V88 (2026-10-05) : le code se lit sous le lien, sans dépliant — replié, il
        # fallait savoir qu'il existait pour aller le chercher.
        st.caption(t("referral.code_alone",
                     "Sans le lien, ton filleul saisit ce code lui-même en créant son "
                     "compte, dans le champ **« Code promo ou parrainage »** du "
                     "formulaire d'inscription :"))
        st.code(code, language=None)
        st.caption(t("referral.code_caption",
                     "Code **unique** et permanent attribué à ton compte."))

        st.markdown("---")

        # ── Referral stats ─────────────────────────────────────────────────
        stats = db.fetch_query(
            "SELECT referral_free_months FROM saas_artists WHERE id = %s",
            (artist_id,),
        )
        free_months = stats[0][0] if stats else 0

        uses_row = db.fetch_query(
            "SELECT uses_count FROM referral_codes WHERE artist_id = %s",
            (artist_id,),
        )
        total_referrals = uses_row[0][0] if uses_row else 0

        col1, col2 = st.columns(2)
        col1.metric(t("referral.artists_referred", "Artistes parrainés"), total_referrals)
        col2.metric(t("referral.free_months_pending", "Mois offerts en attente"), free_months,
                    help=t("referral.free_months_help",
                           "Un mois est gagné quand l'artiste que tu as parrainé paie son "
                           "premier mois ; il est déduit de ta facture suivante."))

        # ⚠️ LA PHRASE A CHANGÉ LE 2026-09-21, ET C'EST UNE CORRECTION DE FOND.
        #
        # ⚠️ PÉRIMÉ DEPUIS R272/R283 (2026-09-28 / 2026-10-05) : le mois est désormais
        # posé par un coupon Stripe (`src/utils/referral_rewards.py`, webhook
        # `invoice.paid`). Le récit ci-dessous est celui du 2026-09-21.
        #
        # Elle disait : « Ils seront appliqués avant votre prochain cycle de
        # facturation. » — au futur, à la voix passive, comme si un mécanisme s'en
        # chargeait. Balayé le même jour : **rien ne consomme `referral_free_months`**.
        # Aucun coupon Stripe, aucune prolongation d'essai, aucun avoir. La montée
        # en gamme passe par un lien de paiement statique (`STRIPE_CHECKOUT_URL`),
        # qui ne peut porter aucune remise par client sans un appel à l'API Stripe
        # que personne n'écrit.
        #
        # Le crédit est donc RÉEL et son application est MANUELLE. Le dire est la
        # seule version honnête tant que l'automatisation n'existe pas — et elle
        # est à la roadmap, pas dans ce correctif : poser des coupons Stripe est
        # une brique, pas une retouche de texte.
        #
        # Personne n'a encore été lésé : zéro parrainage en base au 2026-09-21. La
        # promesse n'aurait échoué qu'au premier, ce qui est exactement le moment
        # où elle coûte le plus cher.
        if free_months > 0:
            st.success(
                t("referral.free_months_msg",
                  "🎉 Tu as **{n} mois offert(s)** en attente. Chacun est déduit de ta "
                  "prochaine facture Stripe, un mois à la fois, dès que ton abonnement "
                  "est actif.").format(n=free_months)
            )

        st.markdown("---")

        # ── Referred artists list ──────────────────────────────────────────
        st.subheader(t("referral.referred_header", "Artistes que vous avez parrainés"))

        rows = db.fetch_query(
            """
            SELECT sa.name, re.created_at::date AS joined_on
            FROM referral_events re
            JOIN saas_artists sa ON sa.id = re.referred_artist_id
            WHERE re.referrer_artist_id = %s
            ORDER BY re.created_at DESC
            """,
            (artist_id,),
        )

        if not rows:
            st.info(t("referral.no_referrals",
                      "Aucun parrainage pour l'instant. Partagez votre code pour commencer "
                      "à gagner des mois gratuits !"))
        else:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["Artist", "Joined on"])
            df["Joined on"] = df["Joined on"].astype(str)
            df.columns = [t("common.artist", "Artiste"),
                          t("referral.joined_on", "Inscrit le")]
            st.dataframe(df, hide_index=True, width="stretch")

        st.markdown("---")

        # ── How it works ───────────────────────────────────────────────────
        with st.expander(t("referral.how_it_works", "Comment ça marche ?")):
            st.markdown(t("referral.how_body", """
**Le parcours, étape par étape :**
1. Tu envoies ton **lien d'invitation** (ou ton code) à un artiste.
2. Il crée son compte : avec le lien, le code est déjà posé dans le champ
   **« Code promo ou parrainage »** du formulaire d'inscription ; sans le lien, il l'y tape.
3. Il reçoit ses **30 jours de Premium** offerts, comme tout nouvel inscrit.
4. Quand il paie son **premier mois**, tu gagnes **+1 mois offert**, déduit de ta
   prochaine facture Stripe.

**Pour vous (parrain) :**
- Quand il paie son premier mois avec votre code, vous gagnez **+1 mois offert**.
- Chaque mois offert est déduit de votre prochaine facture Stripe, un mois à la fois.
- Les mois offerts s'accumulent — sans plafond.

**Pour lui (filleul) :**
- Saisissez le code de parrainage à l'inscription.
- Obtenez **20% de réduction sur le premier mois payant** — signalez votre code en vous abonnant : nous posons la remise sur votre première facture.

**Limites :**
- Chaque code ne peut être utilisé qu'une fois par artiste parrainé.
- Les mois gratuits s'appliquent à votre prochain cycle de facturation.
            """))

    finally:
        db.close()

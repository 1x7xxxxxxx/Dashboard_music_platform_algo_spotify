"""Referral page — artist-facing referral program.

Type: Feature
Uses: get_db_connection, get_artist_id
Depends on: referral_codes table, referral_events table, saas_artists table
Persists in: PostgreSQL spotify_etl (referral_codes, referral_events, saas_artists)

Accessible to all plans (free, basic, premium).
Each artist gets one unique code. Referrer earns +1 free month per successful referral.
"""
import secrets
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id


def _get_or_create_code(db, artist_id: int) -> str:
    """Return existing referral code for artist, or generate and insert a new one."""
    row = db.fetch_query(
        "SELECT code FROM referral_codes WHERE artist_id = %s",
        (artist_id,),
    )
    if row:
        return row[0][0]
    code = secrets.token_hex(3).upper()  # e.g. "A3F8C1"
    db.execute_query(
        "INSERT INTO referral_codes (artist_id, code) VALUES (%s, %s)",
        (artist_id, code),
    )
    return code


def show():
    st.title(t("referral.title", "🎁 Programme de parrainage"))
    st.caption(t("referral.caption",
                 "Partagez votre code — gagnez 1 mois gratuit pour chaque artiste "
                 "qui s'abonne avec."))

    artist_id = get_artist_id()
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
        st.subheader(t("referral.your_code", "Votre code de parrainage"))
        st.code(code, language=None)
        st.caption(
            t("referral.code_caption",
              "Code **unique** et permanent attribué à votre compte. Partagez-le : "
              "les artistes qui l'utilisent à l'inscription obtiennent **20% sur leur "
              "premier mois**. (Rappel : chaque nouvel inscrit reçoit aussi **30 jours "
              "d'accès Premium offerts** automatiquement.)")
        )

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
        col2.metric(t("referral.free_months_earned", "Mois gratuits gagnés"), free_months)

        if free_months > 0:
            st.success(
                t("referral.free_months_msg",
                  "🎉 Vous avez **{n} mois gratuit(s)** crédités sur votre compte. "
                  "Ils seront appliqués avant votre prochain cycle de facturation.").format(
                      n=free_months)
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
**Pour vous (parrain) :**
- Partagez votre code avec n'importe quel artiste.
- Quand il s'inscrit et souscrit à un plan payant avec votre code, vous gagnez automatiquement **+1 mois gratuit** sur votre plan actuel.
- Les mois gratuits s'accumulent — sans plafond.

**Pour lui (filleul) :**
- Saisissez le code de parrainage à l'inscription.
- Obtenez **20% de réduction sur le premier mois payant**.

**Limites :**
- Chaque code ne peut être utilisé qu'une fois par artiste parrainé.
- Les mois gratuits s'appliquent à votre prochain cycle de facturation.
            """))

    finally:
        db.close()

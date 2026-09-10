"""Les deux pages qu'on atteint depuis un e-mail, sans être connecté.

Type: Feature
Uses: streamlit, get_db_connection, src.utils.verification_email
Triggers: src/dashboard/app.py (?page=verify, ?page=unsubscribe)
Persists in: saas_users (email_verified, marketing_consent, weekly_digest_optout_at)

Pourquoi ce module n'est PAS sous `views/`
------------------------------------------
Dans ce dépôt, `views/` veut dire « une page de la navigation, avec un `show()` ». Ces
deux flux n'ont ni l'un ni l'autre : pas de `show()`, absents de `_NAV_SECTIONS`,
atteints par une URL. Les y ranger a été essayé et deux gardes l'ont dit, chacun à sa
façon — la Views Map réclamait une ligne pour une page qui n'existe pas, et le budget de
connexions comptait 2 connexions par fichier là où la règle #9 parle d'un `show()`. Or
la règle est respectée : un visiteur atteint exactement UN des deux flux par requête, et
chacun ouvre une connexion. Le fichier était au mauvais endroit, pas le code.

Pourquoi ces deux flux vivent hors de `app.py`
----------------------------------------------
`app.py` porte la navigation, le routage, la session et la première visite — quatre
sujets qui se lisent mal ensemble, et 1 252 lignes le 2026-09-10. Ces deux-là n'en
sont aucun : ce sont des pages ATTEINTES PAR UNE URL, sans session, sans barre
latérale, sans locataire résolu. Elles n'ont en commun avec le reste du fichier que
d'être servies par le même processus.

Les sortir n'est pas un rangement : `app.py` exécute son en-tête au chargement — il
lève si `AIRFLOW_PASSWORD` ou `FERNET_KEY` manquent — donc rien de ce qu'il contient
n'était atteignable depuis un test sans cette configuration. Ici, elles le sont.

Ce que ces flux ne font PAS, et c'est délibéré : `_artist_id_of` rend `None` plutôt
qu'un repli sur l'artiste 1. Écrire un lien d'inscription sous l'artiste 1 serait la
fuite de locataire du 2026-08-20, par la porte d'entrée.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import get_lang, t


def _artist_id_of(db, user_id: int):
    """Le locataire de cet utilisateur, ou `None`. Ne lève jamais.

    `None` et non un repli sur 1 : écrire les liens d'inscription sous l'artiste 1
    serait la fuite de locataire du 2026-08-20, cette fois par la porte d'entrée.
    """
    try:
        rows = db.fetch_query(
            "SELECT artist_id FROM saas_users WHERE id = %s LIMIT 1", (user_id,))
        return rows[0][0] if rows and rows[0][0] else None
    except Exception:  # noqa: BLE001
        return None


def _verify_email(token: str) -> None:
    """Handle the email verification link (?page=verify&token=xxx)."""
    st.title(t("app.verify_title", "🎵 Vérification de l'email"))
    if not token:
        st.error(t("app.verify_invalid_link", "Lien de vérification invalide."))
        return
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        st.error(t("app.db_unreachable_short", "Base de données injoignable."))
        return
    try:
        rows = db.fetch_query(
            "SELECT id, username, email, email_verified, verification_token_created_at "
            "FROM saas_users "
            "WHERE verification_token = %s LIMIT 1",
            (token,)
        )
        if not rows:
            st.error(t("app.verify_used_link",
                       "Ce lien de vérification est invalide ou a déjà été utilisé."))
            return
        uid, username, email, already_verified, token_created_at = rows[0]
        if already_verified:
            st.info(t("app.verify_already",
                      "Le compte **{u}** est déjà vérifié.").format(u=username))
            # Même raison que le bouton du cas nominal, plus bas : un lien navigue,
            # un bouton relance la page. « [Se connecter](/) » au fil du texte
            # cumulait les deux défauts — il se rate à la lecture, et il peut ouvrir
            # un onglet.
            if st.button(t("app.verify_login_btn", "→ Me connecter"), type="primary",
                         key="_verify_goto_login_already"):
                st.query_params.clear()
                st.rerun()
            return
        # INFO-01: reject tokens older than 48 hours
        if token_created_at:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            created = token_created_at if token_created_at.tzinfo else token_created_at.replace(tzinfo=timezone.utc)
            if now - created > timedelta(hours=48):
                db.execute_query(
                    "UPDATE saas_users SET verification_token = NULL, "
                    "verification_token_created_at = NULL WHERE id = %s",
                    (uid,)
                )
                st.error(t(
                    "app.verify_expired",
                    "Ce lien de vérification a expiré (48 heures). "
                    "Inscrivez-vous à nouveau ou utilisez l'option de renvoi sur la page "
                    "de connexion."
                ))
                return
        db.execute_query(
            "UPDATE saas_users SET email_verified = TRUE, verification_token = NULL, "
            "verification_token_created_at = NULL WHERE id = %s",
            (uid,)
        )
        # Les liens saisis à l'inscription deviennent des credentials MAINTENANT,
        # et pas avant : le compte est confirmé, donc l'identité peut être opposée
        # aux autres locataires (migration 087). Ne lève jamais — au pire l'artiste
        # trouve ses champs vides, comme avant cette fonctionnalité.
        _connected = []
        try:
            from src.dashboard.views.credentials._from_signup import materialise
            _aid = _artist_id_of(db, uid)
            _connected = materialise(db, _aid) if _aid else []
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "signup links not materialised: %s", type(exc).__name__)

        # Show the confirmation FIRST — the verification is already committed above.
        # The welcome email (a blocking ~3s SMTP round-trip) must NOT delay the message
        # the user is waiting for; send it after the success is rendered.
        st.success(t(
            "app.verify_success",
            "✅ Email vérifié ! Bienvenue, **{u}**. "
            "Nous vous avons envoyé un guide de bienvenue par email."
        ).format(u=username))
        if _connected:
            from src.dashboard.views.credentials._registry import PLATFORMS
            _names = ", ".join((PLATFORMS.get(p) or {}).get("label", p)
                               for p in _connected)
            st.info(t(
                "app.verify_links_connected",
                "🔗 On a déjà branché **{names}** avec les liens que tu as donnés à "
                "l'inscription — rien à ressaisir."
            ).format(names=_names))
        # Un BOUTON, pas un `st.link_button`. Signalé le 2026-09-04 : « ça m'ouvre une
        # nouvelle fenêtre, est-ce qu'on peut rester sur la même fenêtre ? »
        #
        # `st.link_button` rend une balise `<a>` : le navigateur navigue, et selon la
        # façon dont la page a été ouverte — depuis un client mail, typiquement — il
        # peut le faire dans un nouvel onglet. On ne contrôle pas ce choix.
        #
        # Un bouton Streamlit n'en pose pas : il efface le paramètre d'URL et relance
        # le script. Il n'y a aucune navigation HTML, donc aucun onglet possible. Le
        # même écran devient l'écran de connexion — c'est ce qu'un lien vers `/`
        # essayait d'obtenir.
        if st.button(t("app.verify_login_btn", "→ Me connecter"), type="primary",
                     key="_verify_goto_login"):
            st.query_params.clear()
            st.rerun()
        # Welcome email + onboarding guide PDF — sent now (account confirmed), NOT at
        # signup, so the guide lands only once the address is proven deliverable.
        try:
            from src.dashboard.views.register import WELCOME_TRIAL_DAYS
            from src.utils.verification_email import send_welcome_email
            with st.spinner(t("app.sending_welcome", "Envoi du guide de bienvenue…")):
                send_welcome_email(email, username, WELCOME_TRIAL_DAYS, user_id=uid,
                                   lang=get_lang())
        except Exception:
            pass  # best-effort — never block verification on the welcome email
    finally:
        db.close()


def _unsubscribe(uid: str, token: str, scope: str = "marketing") -> None:
    """Handle the one-click unsubscribe link (?page=unsubscribe&uid=&t=&scope=).

    Verifies the HMAC token, then sets marketing_consent=FALSE for that user — no
    login required. Mirrors the toggle in 'Mon compte → Communications'.
    """
    st.title(t("app.unsub_title", "📧 Désinscription"))
    from src.utils.verification_email import verify_unsubscribe_token
    try:
        user_id = int(uid)
    except (TypeError, ValueError):
        st.error(t("app.unsub_invalid", "Lien de désinscription invalide."))
        return
    if not verify_unsubscribe_token(user_id, token):
        st.error(t("app.unsub_expired", "Lien de désinscription invalide ou expiré."))
        return
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        st.error(t("app.db_unreachable_retry",
                   "Base de données injoignable. Réessayez plus tard."))
        return
    try:
        # One link, two scopes. `digest` stops the weekly recap ONLY: it is a service
        # e-mail for a paid feature, and clearing `marketing_consent` for it would
        # silently switch off every unrelated communication as well. Column names are
        # not interpolated — the branch is explicit, so there is no identifier to
        # validate against an allowlist (cross-cutting rule #8).
        if scope == "digest":
            db.execute_query(
                "UPDATE saas_users SET weekly_digest_optout_at = now() WHERE id = %s",
                (user_id,),
            )
            st.success(t(
                "app.unsub_digest_success",
                "✅ C'est fait — vous ne recevrez plus le récapitulatif hebdomadaire. "
                "Vos autres e-mails ne changent pas."
            ))
        else:
            db.execute_query(
                "UPDATE saas_users SET marketing_consent = FALSE, marketing_consent_at = now() "
                "WHERE id = %s",
                (user_id,),
            )
            st.success(t(
                "app.unsub_success",
                "✅ C'est fait — vous ne recevrez plus de communications marketing. "
                "Vous pouvez réactiver l'option à tout moment dans « Mon compte → Communications »."
            ))
    finally:
        db.close()

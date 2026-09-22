"""Account self-service page — password change, consent management, data export.

Type: Feature
Uses: get_db_connection, verify_password, hash_password
Depends on: saas_users, saas_artists
RGPD: covers Art. 15 (access), Art. 16 (rectification), Art. 17 (partial — deletion via admin),
      Art. 21 (opposition marketing).
"""
from datetime import datetime, timezone

import streamlit as st

from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t
from src.dashboard.auth import verify_password, hash_password, _validate_password_strength
from src.dashboard.utils.tz import to_local_datetime
from src.dashboard.utils.ui import flash


def _get_user_row(db, username: str) -> dict | None:
    """La ligne du compte. ⚠️ SANS `a.tier` ni `a.slug` — 2026-09-21.

    `tier` n'est que le REPLI de `get_artist_plan()`, qui lit d'abord
    `artist_subscriptions` et applique la précédence promo / essai / `view_as`.
    Mesuré : l'artiste 1 porte `tier='premium'` et **aucune ligne d'abonnement**,
    donc cette page pouvait annoncer un plan que la facturation contredit. Le
    laisser dans le SELECT aurait suffi à ce qu'on le réaffiche un jour.

    `slug` est un champ de développeur : un artiste n'en fait rien.

    Garde : `tests/test_the_plan_is_shown_by_its_resolver.py`.
    """
    rows = db.fetch_query(
        """
        SELECT u.id, u.username, u.email, u.password_hash, u.role,
               u.created_at, u.email_verified,
               u.terms_accepted, u.terms_accepted_at,
               u.marketing_consent, u.marketing_consent_at,
               a.name  AS artist_name,
               u.totp_enabled
        FROM saas_users u
        LEFT JOIN saas_artists a ON u.artist_id = a.id
        WHERE u.username = %s LIMIT 1
        """,
        (username,),
    )
    if not rows:
        return None
    cols = [
        "id", "username", "email", "password_hash", "role",
        "created_at", "email_verified",
        "terms_accepted", "terms_accepted_at",
        "marketing_consent", "marketing_consent_at",
        "artist_name",
        "totp_enabled",
    ]
    return dict(zip(cols, rows[0]))


# ─────────────────────────────────────────────
# Sections
# ─────────────────────────────────────────────

_Q_BRANCHEES = """
SELECT platform, MAX(updated_at)::date AS depuis
FROM artist_credentials WHERE artist_id = %s
GROUP BY platform ORDER BY platform
"""


def _section_profile(db, user: dict) -> None:
    """Le compte en un écran : qui je suis, ce que j'ai, ce qui est branché.

    ⚠️ DEUX CORRECTIONS DE FOND le 2026-09-21, pas une réorganisation.

    **1. Le plan affiché était la COLONNE BRUTE `saas_artists.tier`.** Elle n'est
    qu'un REPLI dans `get_artist_plan()`, qui lit d'abord `artist_subscriptions`
    et applique la précédence promo / essai de bienvenue / `view_as`. Mesuré sur
    l'artiste 1 : `tier = 'premium'` alors qu'il n'a **aucune ligne
    d'abonnement**. La page de compte pouvait donc annoncer un plan que la barre
    latérale et la facturation contredisent — trois surfaces, deux vérités. On
    lit désormais la fonction, jamais la colonne.

    **2. `slug` et `tier` ont disparu de l'écran.** Ce sont des champs de
    développeur : un artiste n'a rien à faire d'un slug, et « tier » ne veut rien
    dire pour quelqu'un dont la page de prix parle de « Free » et « Premium ».
    """
    from src.dashboard.auth import get_artist_plan

    st.subheader(t("account.profile_header", "👤 Mon compte"))

    plan = get_artist_plan() if user.get("artist_name") else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("account.username", "Nom d'utilisateur"), user["username"])
    c2.metric(t("account.plan", "Mon plan"),
              (plan or user["role"]).capitalize())
    c3.metric(
        t("account.email_verified", "Email vérifié"),
        t("account.yes", "✅ Oui") if user["email_verified"]
        else t("account.pending", "⏳ En attente"))
    c4.metric(t("account.twofa", "2FA"),
              t("account.on", "🔐 Activée") if user.get("totp_enabled")
              else t("account.off", "—"))

    st.caption(t("account.email_caption", "Email : **{email}**").format(email=user['email']))
    if user.get("artist_name"):
        st.caption(t("account.artist_caption", "Artiste : **{name}**").format(
            name=user['artist_name']))
    joined = user.get("created_at")
    if joined:
        st.caption(t("account.member_since", "Membre depuis : {date}").format(
            date=to_local_datetime(joined).strftime('%d %B %Y')))

    _section_connected(db, user)


def _section_connected(db, user: dict) -> None:
    """Ce qui est branché — la question qu'on vient poser ici, et qui était ailleurs.

    « Est-ce que mon Spotify est bien connecté ? » se répondait en trois clics,
    sur une autre page. Elle a sa place sur la page du compte : c'est un état du
    compte, pas un réglage.

    ⚠️ Cette section ne dit PAS si la connexion FONCTIONNE — une clé enregistrée
    peut être expirée, et Meta répond `code-190` sur ce dépôt depuis des semaines.
    Elle dit ce qui est DÉCLARÉ, et renvoie à la page qui teste. Confondre les
    deux enverrait l'artiste se rassurer sur une pastille verte.
    """
    artiste = st.session_state.get("artist_id")
    if not artiste:
        return
    try:
        df = db.fetch_df(_Q_BRANCHEES, (artiste,))
    except Exception:
        return
    st.markdown("---")
    st.markdown(t("account.connected_header", "**🔌 Mes comptes branchés**"))
    if df is None or df.empty:
        st.info(t("account.connected_none",
                  "Aucun compte branché. C'est ce qui remplit tes pages : "
                  "ouvre **🔑 Credentials API** dans la barre latérale."))
        return

    from src.dashboard.views.credentials._render import platform_label
    lignes = " · ".join(
        f"**{platform_label(r['platform'])}** ({r['depuis']:%m/%Y})"
        for _i, r in df.iterrows())
    st.markdown(lignes)
    st.caption(t(
        "account.connected_caption",
        "{n} compte(s) déclaré(s). Cette liste dit ce qui est **enregistré**, pas "
        "ce qui **répond** : une clé peut avoir expiré depuis. Le test vit dans "
        "**🔑 Credentials API**.").format(n=len(df)))


def _section_change_password(db, user: dict) -> None:
    st.subheader(t("account.change_pw_header", "🔒 Changer le mot de passe"))
    with st.form("change_password"):
        current = st.text_input(t("account.current_pw", "Mot de passe actuel"), type="password")
        new_pw  = st.text_input(t("account.new_pw", "Nouveau mot de passe"), type="password",
                                help=t("account.pw_help", "8 caractères minimum."))
        new_pw2 = st.text_input(t("account.confirm_new_pw", "Confirmer le nouveau mot de passe"), type="password")
        submitted = st.form_submit_button(t("account.update_pw_btn", "Mettre à jour le mot de passe"), type="primary")

    if not submitted:
        return

    if not current or not new_pw or not new_pw2:
        st.error(t("account.pw_all_required", "Les trois champs sont obligatoires."))
        return
    if not verify_password(current, user["password_hash"]):
        st.error(t("account.pw_incorrect", "Le mot de passe actuel est incorrect."))
        return
    pw_error = _validate_password_strength(new_pw)
    if pw_error:
        st.error(pw_error)
        return
    if new_pw != new_pw2:
        st.error(t("account.pw_mismatch", "Les mots de passe ne correspondent pas."))
        return
    if verify_password(new_pw, user["password_hash"]):
        st.warning(t("account.pw_same", "Le nouveau mot de passe est identique à l'actuel."))
        return

    # Bumping token_version is the half that makes this gesture mean something after
    # a compromise (R24): changing the hash alone left every API token issued to the
    # intruder valid for up to 24 h. The user's own dashboard session survives — they
    # are the one who just typed the current password.
    db.execute_query(
        "UPDATE saas_users SET password_hash = %s, token_version = token_version + 1 "
        "WHERE id = %s",
        (hash_password(new_pw), user["id"]),
    )
    st.success(t("account.pw_updated",
                 "✅ Mot de passe mis à jour. Les jetons d'API émis avant ce "
                 "changement ne sont plus valides."))


def _section_consent(db, user: dict) -> None:
    st.subheader(t("account.consent_header", "📧 Préférences de communication"))

    current_consent = bool(user.get("marketing_consent"))
    st.write(
        t("account.opted_in", "Vous êtes actuellement **inscrit(e)** aux communications marketing.")
        if current_consent
        else t("account.opted_out",
               "Vous êtes actuellement **désinscrit(e)** des communications marketing "
               "(newsletters, actualités de la plateforme).")
    )
    if user.get("marketing_consent_at"):
        st.caption(
            t("account.consent_updated", "Dernière mise à jour : {date}").format(
                date=to_local_datetime(user['marketing_consent_at']).strftime('%d/%m/%Y %H:%M'))
        )

    # Email alerts checked by default: for users who never set a preference,
    # the toggle defaults to ON (and is persisted as opt-in on first view).
    # Users who explicitly opted out keep their choice.
    ever_set = user.get("marketing_consent_at") is not None
    default_val = current_consent if ever_set else True

    new_consent = st.toggle(
        t("account.consent_toggle", "Recevoir les alertes et communications par email"),
        value=default_val,
        key="marketing_toggle",
    )

    if new_consent != current_consent:
        now = datetime.now(timezone.utc)
        db.execute_query(
            "UPDATE saas_users SET marketing_consent = %s, marketing_consent_at = %s WHERE id = %s",
            (new_consent, now, user["id"]),
        )
        if new_consent:
            st.success(t("account.consent_on", "✅ Vous êtes inscrit(e) aux communications marketing."))
        else:
            st.success(t("account.consent_off",
                         "✅ Vous êtes désinscrit(e). Vous ne recevrez plus d'emails marketing."))
        st.rerun()


def _section_totp(db, user: dict) -> None:
    """Brick 28 — TOTP 2FA enrollment and revocation."""
    st.subheader(t("account.totp_header", "🔐 Authentification à deux facteurs (2FA)"))

    totp_enabled = bool(user.get("totp_enabled"))

    if totp_enabled:
        st.success(t("account.totp_enabled",
                     "✅ L'authentification à deux facteurs est **activée** sur votre compte."))
        st.caption(t("account.totp_required_caption",
                     "Votre application d'authentification est requise à chaque connexion."))
        st.markdown("---")
        st.write(t("account.totp_disable_title", "**Désactiver la 2FA**"))
        with st.form("disable_totp"):
            pw = st.text_input(t("account.totp_confirm_pw",
                                 "Confirmez votre mot de passe pour désactiver la 2FA"), type="password")
            submitted = st.form_submit_button(t("account.totp_disable_btn", "Désactiver la 2FA"), type="secondary")
        if submitted:
            if not verify_password(pw, user["password_hash"]):
                st.error(t("account.totp_pw_incorrect", "Mot de passe incorrect."))
                return
            db.execute_query(
                "UPDATE saas_users SET totp_enabled = FALSE, totp_secret = NULL WHERE id = %s",
                (user["id"],),
            )
            flash(t("account.totp_disabled",
                         "✅ 2FA désactivée. Vous pouvez la réactiver à tout moment."))
            st.rerun()
        return

    # ── Enrollment flow ──────────────────────────────────────────────
    st.info(t("account.totp_intro",
              "Protégez votre compte avec un mot de passe à usage unique basé sur le temps (TOTP). "
              "Compatible avec Google Authenticator, Authy et les applications similaires."))

    # Generate or reuse pending secret stored in session
    try:
        import pyotp
        import qrcode
        import io
    except ImportError:
        # `pip install …` s'adressait à l'artiste. Ces paquets manquent sur le
        # SERVEUR, pas sur sa machine : il n'a rien à installer et rien à corriger.
        # La commande ne va donc qu'à l'admin, et par le seul constructeur de blocs
        # (`utils.shell_block`), qui la fait précéder de ce que son shell exige.
        st.error(t("account.totp_unavailable",
                   "La double authentification est momentanément indisponible. "
                   "Préviens l'administrateur — il n'y a rien à faire de ton côté."))
        from src.dashboard.auth import is_admin
        if is_admin():
            from src.dashboard.utils.shell_block import command_block
            _lang, _cmd = command_block("pip install pyotp 'qrcode[pil]'")
            st.code(_cmd, language=_lang)
        return

    if 'totp_enroll_secret' not in st.session_state:
        st.session_state['totp_enroll_secret'] = pyotp.random_base32()

    secret = st.session_state['totp_enroll_secret']
    issuer = "MusicDashboard"
    account = user["email"]
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)

    # Render QR code as PNG bytes
    qr_img = qrcode.make(uri)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    col_qr, col_info = st.columns([1, 2])
    with col_qr:
        st.image(buf.getvalue(),
                 caption=t("account.totp_scan_caption", "Scannez avec votre application d'authentification"),
                 width=200)
    with col_info:
        st.write(t("account.totp_manual_key", "**Clé de saisie manuelle :**"))
        st.code(secret, language=None)
        st.caption(t("account.totp_manual_caption",
                     "Saisissez cette clé manuellement dans votre application si vous ne pouvez pas "
                     "scanner le QR code."))

    st.markdown("---")
    st.write(t("account.totp_verify_title", "**Vérifier et activer**"))
    with st.form("enable_totp"):
        code = st.text_input(t("account.totp_code_input", "Saisissez le code à 6 chiffres de votre application"),
                             max_chars=6, placeholder="000000")
        submitted = st.form_submit_button(t("account.totp_activate_btn", "Activer la 2FA"), type="primary")

    if submitted:
        totp = pyotp.TOTP(secret)
        if totp.verify(code.strip(), valid_window=1):
            db.execute_query(
                "UPDATE saas_users SET totp_secret = %s, totp_enabled = TRUE WHERE id = %s",
                (secret, user["id"]),
            )
            st.session_state.pop('totp_enroll_secret', None)
            flash(t("account.totp_active",
                         "✅ L'authentification à deux facteurs est désormais active sur votre compte."))
            st.rerun()
        else:
            st.error(t("account.totp_invalid_code",
                       "Code invalide. Vérifiez que l'horloge de votre appareil est correcte et réessayez."))


def _section_delete_account() -> None:
    st.subheader(t("account.delete_header", "🗑️ Supprimer mon compte (RGPD Art. 17)"))
    st.warning(
        t("account.delete_warning",
          "La suppression de compte est gérée par l'administrateur. "
          "Envoyez une demande à **1x7xxxxxxx@gmail.com** avec l'objet "
          "**'Supprimer mon compte — [votre nom d'utilisateur]'**. "
          "Vos données seront supprimées sous 30 jours.")
    )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def show() -> None:
    st.title(t("account.title", "👤 Mon compte"))
    st.markdown("---")

    username = st.session_state.get("username")
    if not username:
        st.error(t("account.session_expired", "Session expirée. Veuillez vous reconnecter."))
        return

    with project_db() as db:
        user = _get_user_row(db, username)
        if user is None:
            st.error(t("account.user_not_found", "Utilisateur introuvable."))
            return

        tab_profile, tab_password, tab_2fa, tab_consent = st.tabs([
            t("account.tab_profile", "👤 Profil"),
            t("account.tab_password", "🔒 Mot de passe"),
            t("account.tab_2fa", "🔐 2FA"),
            t("account.tab_consent", "📧 Communications"),
        ])

        with tab_profile:
            _section_profile(db, user)
            # Data-export tab removed (redundant with the Export CSV page); the
            # RGPD account-deletion path stays here so it remains reachable.
            st.markdown("---")
            _section_delete_account()

        with tab_password:
            _section_change_password(db, user)

        with tab_2fa:
            _section_totp(db, user)

        with tab_consent:
            _section_consent(db, user)

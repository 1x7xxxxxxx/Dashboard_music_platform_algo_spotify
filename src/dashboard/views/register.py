"""Registration view — New artist sign-up.

Type: Feature
Uses: get_db_connection, hash_password, send_verification_email
Depends on: saas_artists table, saas_users table
Persists in: PostgreSQL spotify_etl (saas_artists + saas_users, atomic CTE insert)

Accessible without login via /?page=register.

Anonymous-surface rules (R23, 2026-08-22). Everything on this page runs for a visitor
who has proven nothing, so three properties are load-bearing and each has a test:

  * the outcome must not depend on whether the email already exists — otherwise the
    page is an account-enumeration oracle for anyone;
  * a promo/referral code must not be *checkable* without paying the cost of a full
    registration — otherwise `secrets.token_hex(3)` (24 bits) is brute-forced for free,
    and a hit grants `promo_plan='premium'`;
  * an exception must never reach the page — psycopg2 names the constraint and the
    columns it violated.

The per-IP budget in `src.dashboard.utils.throttle` bounds the fourth: each submit
sends an email to an address the visitor chose, from our domain.
"""
import logging
import re
import secrets
import streamlit as st

from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t, get_lang
from src.dashboard.utils.throttle import throttle_check, throttle_record
from src.dashboard.auth import hash_password, _validate_password_strength
from src.utils.safe_error import public_error_ref
from src.utils.verification_email import (
    send_account_exists_email,
    send_verification_email,
)
from src.utils.plan_history import log_plan_change
from src.dashboard.content.platform_value import ordered_for_setup

logger = logging.getLogger(__name__)

_SLUG_RE    = re.compile(r'^[a-z0-9_-]+$')
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,50}$')

# Every new account gets a full-access (premium) trial for this many days.
WELCOME_TRIAL_DAYS = 30


def _derive_identifiers(db, artist_name: str) -> tuple[str, str]:
    """Auto-derive a unique slug + username from the artist name (both hidden from the
    user — login is by email). Slug allows [a-z0-9_-]; username (login fallback +
    display) is [a-zA-Z0-9_]{3,50}. Numeric suffixes resolve collisions."""
    base = re.sub(r'[^a-z0-9_-]', '-', artist_name.lower().strip())
    base_slug = re.sub(r'-+', '-', base).strip('-') or 'artist'
    slug = base_slug
    i = 2
    while _slug_taken(db, slug):
        slug = f"{base_slug}-{i}"; i += 1
    base_user = (re.sub(r'[^a-z0-9_]', '_', artist_name.lower().strip()) or 'artist')[:48]
    base_user = base_user.ljust(3, '_')
    username = base_user
    j = 2
    while _username_taken(db, username):
        username = f"{base_user}_{j}"; j += 1
    return slug, username


def _validate(artist_name, email, pw, pw2, terms: bool) -> list[str]:
    errors = []
    if not artist_name.strip():
        errors.append(t("register.err_artist_name", "Le nom d'artiste est requis."))
    if not email or not re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        errors.append(t("register.err_email", "Une adresse email valide est requise."))
    pw_error = _validate_password_strength(pw)
    if pw_error:
        errors.append(pw_error)
    if pw != pw2:
        errors.append(t("register.err_pw_mismatch", "Les mots de passe ne correspondent pas."))
    if not terms:
        errors.append(t("register.err_terms",
                        "Vous devez accepter la Politique de confidentialité et les Conditions "
                        "d'utilisation pour vous inscrire."))
    return errors


def _username_taken(db, username: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM saas_users WHERE username = %s", (username,)
    ))


def _email_taken(db, email: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM saas_users WHERE email = %s", (email,)
    ))


def _slug_taken(db, slug: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM saas_artists WHERE slug = %s", (slug,)
    ))


def _validate_referral_code(db, code: str) -> int | None:
    """Return referrer artist_id for a valid code, or None if not found."""
    if not code:
        return None
    row = db.fetch_query(
        "SELECT artist_id FROM referral_codes WHERE code = %s",
        (code.upper(),),
    )
    return row[0][0] if row else None


def _validate_promo_code(db, code: str) -> dict | None:
    """Return promo code metadata if valid and redeemable, else None.

    Checks: active, not expired, uses_count < max_uses (0 = unlimited).
    MEDIUM-05: validation is read-only; the atomic increment happens in
    _apply_promo via a conditional UPDATE that re-checks the limit,
    preventing TOCTOU race conditions on single-use codes.
    """
    if not code:
        return None
    from datetime import datetime, timezone
    row = db.fetch_query(
        """
        SELECT id, plan_target, duration_days, max_uses, uses_count, expires_at
        FROM promo_codes
        WHERE code = %s AND active = TRUE
        """,
        (code.upper(),),
    )
    if not row:
        return None
    promo_id, plan_target, duration_days, max_uses, uses_count, expires_at = row[0]
    if expires_at and expires_at < datetime.now(timezone.utc):
        return None
    if max_uses > 0 and uses_count >= max_uses:
        return None
    return {
        'id': promo_id,
        'plan_target': plan_target,
        'duration_days': duration_days,
        'max_uses': max_uses,
    }


def _apply_promo(db, promo: dict, artist_id: int, code: str) -> None:
    """Set promo plan on artist and record the event.

    MEDIUM-05: uses a conditional UPDATE with a row-level guard to atomically
    increment uses_count only if the limit has not yet been reached.
    Concurrent registrations with the same single-use code will fail the
    UPDATE check and return 0 rows — the second caller is rejected safely.
    """
    from datetime import datetime, timezone, timedelta
    expires_at = datetime.now(timezone.utc) + timedelta(days=promo['duration_days'])

    # Atomic increment: only succeeds if max_uses not yet reached
    max_uses = promo.get('max_uses', 0)
    if max_uses > 0:
        incremented = db.fetch_query(
            """
            UPDATE promo_codes
            SET    uses_count = uses_count + 1
            WHERE  id = %s AND (max_uses = 0 OR uses_count < max_uses)
            RETURNING id
            """,
            (promo['id'],),
        )
        if not incremented:
            raise ValueError("Promo code already exhausted (race condition prevented).")
    else:
        db.execute_query(
            "UPDATE promo_codes SET uses_count = uses_count + 1 WHERE id = %s",
            (promo['id'],),
        )

    db.fetch_query(
        """
        UPDATE saas_artists
        SET promo_code_used = %s, promo_plan = %s, promo_plan_expires_at = %s
        WHERE id = %s
        """,
        (code, promo['plan_target'], expires_at, artist_id),
    )
    db.fetch_query(
        "INSERT INTO promo_events (promo_code_id, artist_id) VALUES (%s, %s)",
        (promo['id'], artist_id),
    )
    # Note: uses_count increment is already handled atomically above.
    # Invalidate the 60s plan-row cache so the artist's own session reflects the new
    # plan on the next render (otherwise they'd still see the paywall for up to 60s).
    from src.dashboard.auth import _cached_plan_row
    _cached_plan_row.clear()


def _grant_welcome_trial(db, artist_id: int, trial_days: int = WELCOME_TRIAL_DAYS) -> None:
    """Grant a full-access (premium) trial for `trial_days` to a new account.

    Reuses the promo_plan precedence in get_artist_plan() — no promo_codes row is
    consumed. Sentinel code 'WELCOME_TRIAL' marks the source for auditing.
    """
    from datetime import datetime, timezone, timedelta
    expires_at = datetime.now(timezone.utc) + timedelta(days=trial_days)
    db.execute_query(
        "UPDATE saas_artists "
        "SET promo_code_used = %s, promo_plan = 'premium', promo_plan_expires_at = %s "
        "WHERE id = %s",
        ('WELCOME_TRIAL', expires_at, artist_id),
    )
    from src.dashboard.auth import _cached_plan_row
    _cached_plan_row.clear()


def _apply_referral(db, referrer_artist_id: int, referred_artist_id: int, code: str,
                    discount_pct: int = 20) -> None:
    """Credit referrer +1 free month, stamp the referred artist, record the event.

    The two columns on the referred artist used to be filled by
    `_create_artist_and_user`. They moved here when code validation moved AFTER account
    creation (R23): the insert no longer knows whether the code is real, and a code the
    insert cannot vouch for must not reach the row.
    """
    db.fetch_query(
        "UPDATE saas_artists SET referred_by_code = %s, first_month_discount_pct = %s "
        "WHERE id = %s",
        (code, discount_pct, referred_artist_id),
    )
    db.fetch_query(
        "INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) VALUES (%s, %s, %s)",
        (referrer_artist_id, referred_artist_id, code),
    )
    db.fetch_query(
        "UPDATE saas_artists SET referral_free_months = referral_free_months + 1 WHERE id = %s",
        (referrer_artist_id,),
    )
    db.fetch_query(
        "UPDATE referral_codes SET uses_count = uses_count + 1 WHERE code = %s",
        (code,),
    )


def _create_artist_and_user(
    db, artist_name, slug, username, email, pw, token: str,
    marketing_consent: bool = False,
    referred_by_code: str = '',
    first_month_discount_pct: int = 0,
) -> tuple[int, int]:
    """Atomic insert: saas_artists + saas_users via CTE.

    Returns (saas_users.id, saas_artists.id).
    autocommit=True on the handler — CTE executes as a single statement,
    so either both rows are created or neither is.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = db.fetch_query(
        """
        WITH new_artist AS (
            INSERT INTO saas_artists
                (name, slug, tier, active, referred_by_code, first_month_discount_pct)
            VALUES (%s, %s, 'free', TRUE, %s, %s)
            RETURNING id
        )
        INSERT INTO saas_users
            (username, email, password_hash, artist_id, role, active,
             email_verified, verification_token,
             terms_accepted, terms_accepted_at,
             marketing_consent, marketing_consent_at)
        SELECT %s, %s, %s, id, 'artist', TRUE, FALSE, %s,
               TRUE, %s,
               %s, %s
        FROM new_artist
        RETURNING id, (SELECT id FROM new_artist)
        """,
        (artist_name.strip(), slug.strip(),
         referred_by_code or None, first_month_discount_pct,
         username.strip(), email.strip(), hash_password(pw), token,
         now,
         marketing_consent, now if marketing_consent else None)
    )
    user_id, artist_id = rows[0]
    return user_id, artist_id


def _welcome_trial_msg() -> str:
    """The default trial sentence — the one a brand-new account gets with no code.

    Shared with the already-taken branch on purpose: that branch must render the
    string a fresh signup would have rendered, and reaching for it here is what keeps
    the two identical when the wording changes.
    """
    return t("register.welcome_trial",
             " Vous bénéficiez de **{days} jours d'accès Premium offerts**.").format(
                 days=WELCOME_TRIAL_DAYS)


def _render_success(artist_name: str, email: str, discount_msg: str,
                    email_sent: bool = True, resend: str = "verify",
                    username: str | None = None, token: str | None = None) -> None:
    """The post-submit screen. The ONLY success renderer on this page.

    Both branches — account created, and address already taken — go through here, so
    a future edit cannot make one of them observably different by touching only the
    other. That divergence is the enumeration oracle coming back.
    """
    if email_sent:
        st.success(
            t("register.success",
              "✅ Compte créé pour **{name}** !{msg} "
              "Un email de vérification a été envoyé à **{email}**. "
              "Cliquez sur le lien dans l'email pour activer votre compte.").format(
                  name=artist_name, msg=discount_msg, email=email)
        )
    else:
        st.warning(
            t("register.email_failed",
              "✅ Compte créé pour **{name}**,{msg} mais l'email de vérification "
              "n'a pas pu être envoyé (SMTP non configuré). "
              "Demandez à un admin de vérifier votre compte manuellement.").format(
                  name=artist_name, msg=discount_msg)
        )
    # Le bouton pointait vers `/?page=onboarding`. À cet instant précis le compte
    # existe mais n'est PAS vérifié : `require_login` renvoie donc vers la page de
    # connexion. Le bouton promettait l'onboarding et livrait un formulaire de login
    # — signalé en test le 2026-08-30 (« ça nous emmène directement dans la page
    # d'accueil »).
    st.info(t("register.next_step",
              "📬 **Prochaine étape : ouvre ta boîte mail.** Le lien de vérification "
              "active ton compte — l'onboarding s'ouvre juste après.\n\n"
              "Il part **immédiatement** et arrive en général en moins d'une minute. "
              "S'il n'est pas là : regarde dans les **spams**, et chez Gmail dans "
              "l'onglet **Promotions**."))

    _resend_button(email, resend, username, token)
    st.link_button(t("register.login_btn", "→ J'ai vérifié, me connecter"), "/")

    # ── Ce qu'on peut faire PENDANT l'attente ────────────────────────────────
    #
    # Signalé le 2026-09-04 : « beaucoup de temps entre l'inscription et la réception
    # du mail, et on ne sait pas quoi faire en attendant ». L'envoi n'y est pour rien
    # — la poignée de main SMTP mesurée en production coûte 0,24 s ; c'est la
    # DISTRIBUTION qui prend une minute, et pendant cette minute l'écran ne proposait
    # rien. Le travail suivant est réel et ne demande aucun compte : rassembler ses
    # identifiants. Autant le faire maintenant.
    st.markdown("---")
    st.markdown("### " + t("register.meanwhile", "⏳ Pendant que le mail arrive"))
    _guide_download()
    st.markdown(t("register.prepare_header",
                  "**Rassemble ce que tu auras à coller**, c'est tout ce que la mise "
                  "en route demande :"))
    for pv in ordered_for_setup(set()):
        star = t("onboarding.reco_tag", " — ⭐ recommandé") if pv.recommended else ""
        st.markdown(f"- {pv.icon} **{pv.label}** · ≈{pv.effort_min} min{star} — "
                    + t("onboarding.need", "À fournir : {need}").format(need=pv.need))
    st.caption(t("register.prepare_hint",
                 "Tu n'as pas besoin de tout : deux plateformes suffisent pour "
                 "commencer, et tu pourras ajouter le reste quand tu veux."))


def _guide_download() -> None:
    """Le guide PDF, téléchargeable AVANT même d'avoir vérifié son adresse.

    Il n'existait qu'après vérification (pièce jointe du mot de bienvenue) et dans
    l'application. Or c'est exactement le document qu'on veut lire pendant qu'on
    attend un mail — et il ne contient rien de personnel : c'est de la documentation.
    """
    try:
        from src.dashboard.utils.guide_assets import credentials_guide_pdf
        data = credentials_guide_pdf(get_lang())
    except Exception:      # noqa: BLE001 — un PDF absent ne bloque pas l'inscription
        data = None
    if not data:
        return
    st.download_button(
        t("register.download_guide", "📄 Télécharger le guide de démarrage (PDF)"),
        data=data, file_name=f"streamlytics-guide-{get_lang()}.pdf",
        mime="application/pdf", type="primary", key="_reg_guide")


_RESEND_KEY = "_register_resend_at"
_RESEND_COOLDOWN_S = 60


def _resend_button(email: str, resend: str, username, token) -> None:
    """Renvoyer le mail — la même forme dans les DEUX branches.

    L'écran d'adresse-déjà-prise doit rester indiscernable de celui d'un compte créé
    (oracle d'énumération). Le bouton est donc présent des deux côtés et fait la même
    chose des deux côtés : un envoi SMTP, un booléen, le même message. Ce qui change
    est le contenu du mail, que le visiteur ne voit pas.
    """
    import time

    last = st.session_state.get(_RESEND_KEY, 0.0)
    left = int(_RESEND_COOLDOWN_S - (time.time() - last))
    if left > 0:
        st.caption(t("register.resend_wait",
                     "Tu pourras redemander un envoi dans {s} s.").format(s=left))
        return
    if not st.button(t("register.resend", "✉️ Je n'ai rien reçu — renvoyer le mail"),
                     key="_reg_resend"):
        return
    st.session_state[_RESEND_KEY] = time.time()
    ok = False
    try:
        if resend == "verify" and username and token:
            ok = send_verification_email(email, username, token, lang=get_lang())
        else:
            with project_db() as db:
                ok = _notify_existing_account(db, email)
    except Exception:      # noqa: BLE001 — surface anonyme : jamais de détail
        ok = False
    if ok:
        st.success(t("register.resent", "✅ Renvoyé à **{email}**.").format(email=email))
    else:
        st.warning(t("register.resend_failed",
                     "L'envoi n'a pas abouti. Réessaie dans une minute."))


def _remember_success(artist_name: str, email: str, discount_msg: str, *,
                      email_sent: bool, resend: str,
                      username: str | None = None, token: str | None = None) -> None:
    """Mémorise l'écran de succès, puis relance pour qu'il devienne la page."""
    st.session_state[_DONE_KEY] = {
        "artist_name": artist_name, "email": email, "discount_msg": discount_msg,
        "email_sent": email_sent, "resend": resend,
        "username": username, "token": token,
    }
    st.rerun()


def _notify_existing_account(db, email: str) -> bool:
    """Mail the real owner that a signup was attempted. Returns whether it was sent.

    Never raises and never says anything on the page: the caller renders the same
    screen either way. A failure here degrades to "the honest user gets no email",
    which is the pre-2026-08-22 behaviour for them, not a new leak.
    """
    try:
        rows = db.fetch_query(
            "SELECT username FROM saas_users WHERE email = %s LIMIT 1", (email,)
        )
        username = rows[0][0] if rows else email
        return send_account_exists_email(email, username, lang=get_lang())
    except Exception as e:  # noqa: BLE001 — best-effort courtesy mail
        logger.warning("account-exists notice failed for a taken address: %s",
                       type(e).__name__)
        return False


_DONE_KEY = "_register_done"


def show():
    # L'écran d'après-inscription ne vivait QUE pendant le run du submit : le moindre
    # bouton dessus le faisait disparaître, puisque le rerun ne repasse pas dans la
    # branche du formulaire. C'est pour ça qu'il ne portait qu'un `link_button` (un
    # lien ne relance pas le script) — et donc rien à faire pendant l'attente du mail.
    # On le mémorise, on le rend en tête, et il devient une vraie page.
    if st.session_state.get(_DONE_KEY):
        _render_success(**st.session_state[_DONE_KEY])
        return

    # Title + pre-login language toggle on one row (toggle right-aligned), persisted
    # via ?lang= into the app.
    from src.dashboard.utils.i18n import language_selector
    _title_col, _lang_col = st.columns([3, 1], vertical_alignment="center")
    with _title_col:
        st.title(t("register.title", "🎵 Créez votre compte"))
    with _lang_col:
        language_selector(sidebar=False)
    st.caption(t("register.subtitle",
                 "Rejoignez streaMLytics. Plan gratuit — passez à un plan supérieur à tout moment."))

    # Brick 32 — Live Activity (public trust signal). Count only, no PII.
    # Cached 10 min server-side to absorb anonymous traffic bursts.
    from src.dashboard.utils.live_pulse import get_registered_count_public
    _registered = get_registered_count_public()
    if _registered > 0:
        st.metric("Live Activity",
                  t("register.live_activity", "{n} artistes utilisent streaMLytics").format(
                      n=f"{_registered:,}"))
        st.markdown("---")

    with st.form("register"):
        artist_name = st.text_input(
            t("register.artist_name", "Nom d'artiste *"),
            # Pas un nom d'artiste réel en exemple — c'était celui du propriétaire
            # de la plateforme, montré à chaque inscription.
            placeholder=t("register.artist_name_ph", "Votre nom d'artiste"),
            help=t("register.artist_name_help", "Votre nom d'artiste public (aussi votre nom d'affichage)."),
        )
        email = st.text_input(
            t("register.email", "Email *"),
            placeholder=t("register.email_ph", "vous@exemple.com"),
            help=t("register.email_help", "Sert d'identifiant pour vous connecter."),
        )

        col3, col4 = st.columns(2)
        pw  = col3.text_input(t("register.password", "Mot de passe *"), type="password",
                              help=t("register.pw_help", "8 caractères minimum."))
        pw2 = col4.text_input(t("register.confirm_password", "Confirmer le mot de passe *"), type="password")

        referral_code = st.text_input(
            t("register.referral_code", "Code promo ou parrainage (optionnel)"),
            placeholder=t("register.referral_ph", "ex. A3F8C1"),
            help=t("register.referral_help",
                   "Code promo (accès gratuit) ou code de parrainage d'un ami "
                   "(20% sur le premier mois)."),
        ).strip().upper()

        st.markdown("---")
        terms = st.checkbox(
            t("register.terms_checkbox",
              "J'accepte la [Politique de confidentialité](?page=privacy) et les Conditions d'utilisation *"),
            value=False,
            help=t("register.terms_help", "Requis pour créer un compte."),
        )
        marketing = st.checkbox(
            t("register.marketing_checkbox",
              "J'accepte de recevoir des actualités, mises à jour et communications marketing "
              "par email (optionnel)"),
            value=False,
            help=t("register.marketing_help", "Vous pouvez retirer ce consentement à tout moment."),
        )

        submitted = st.form_submit_button(t("register.submit", "Créer le compte"), type="primary")

    # Le trajet miroir de « Créez-en un », et le même défaut : deux onglets pour un
    # aller-retour entre deux écrans de la même application. `?page=login` n'était
    # d'ailleurs routé nulle part — vider le paramètre EST le retour à la connexion.
    if st.button(t("register.already_have", "Vous avez déjà un compte ? Connectez-vous"),
                 key="_goto_login"):
        st.query_params.clear()
        st.rerun()

    if not submitted:
        return

    errors = _validate(artist_name, email, pw, pw2, terms)
    if errors:
        for e in errors:
            st.error(e)
        return

    # Per-IP budget, checked before any DB work and before any email leaves the box.
    # Anything past this point either writes a row or sends a mail to an address the
    # visitor typed, so this is the only place the cost of a submit is bounded.
    retry_after = throttle_check("register")
    if retry_after is not None:
        st.error(t("register.throttled",
                   "Trop de tentatives d'inscription depuis cette connexion. "
                   "Réessayez dans {s} seconde(s).").format(s=retry_after))
        return
    throttle_record("register")

    with project_db() as db:
        try:
            # The address is already taken: answer EXACTLY as a successful signup does,
            # create nothing, and tell the real owner by email. Any observable
            # difference here — a distinct message, a missing button, a faster
            # response — is an account-enumeration oracle for an anonymous visitor.
            if _email_taken(db, email):
                with st.spinner(t("register.sending",
                                  "Envoi de ton e-mail de vérification…")):
                    sent = _notify_existing_account(db, email)
                _remember_success(artist_name, email, _welcome_trial_msg(),
                                  email_sent=sent, resend="existing")
                return
            # slug + username are auto-derived (hidden fields) and made unique here.
            slug, username = _derive_identifiers(db, artist_name)

            token = secrets.token_urlsafe(32)
            _user_id, new_artist_id = _create_artist_and_user(
                db, artist_name, slug, username, email, pw, token,
                marketing_consent=marketing,
            )

            # Codes are resolved only NOW, against an account that exists. Validating
            # first with an early return let anyone test a code for free; a probe now
            # costs a full registration, which the per-IP budget above rations.
            promo = None
            referrer_artist_id = None
            if referral_code:
                promo = _validate_promo_code(db, referral_code)
                if promo is None:
                    referrer_artist_id = _validate_referral_code(db, referral_code)

            if promo is not None:
                # Explicit promo code overrides the default welcome trial.
                _apply_promo(db, promo, new_artist_id, referral_code)
                log_plan_change(db, new_artist_id, promo['plan_target'], 'promo')
            else:
                # Default: every new account gets a full-access (premium) trial.
                if referrer_artist_id is not None:
                    _apply_referral(db, referrer_artist_id, new_artist_id, referral_code)
                _grant_welcome_trial(db, new_artist_id, WELCOME_TRIAL_DAYS)
                log_plan_change(db, new_artist_id, 'premium', 'welcome_trial')

            discount_pct = 20 if referrer_artist_id is not None else 0
            if referral_code and promo is None and referrer_artist_id is None:
                # Said after creation, never instead of it — the account is real either
                # way, so this line tells the honest typo-maker without answering
                # "does this code exist?" any cheaper than a full signup.
                st.warning(t("register.code_ignored",
                             "Le code '{code}' n'a pas pu être appliqué. Votre compte "
                             "est créé ; contactez-nous si le code devait "
                             "fonctionner.").format(code=referral_code))

            if promo:
                discount_msg = t("register.promo_active",
                                 " Votre **plan {plan}** est actif pendant **{days} jours**.").format(
                                     plan=promo['plan_target'].capitalize(),
                                     days=promo['duration_days'])
            else:
                discount_msg = t("register.welcome_trial",
                                 " Vous bénéficiez de **{days} jours d'accès Premium offerts**.").format(
                                     days=WELCOME_TRIAL_DAYS)
                if discount_pct:
                    discount_msg += t("register.referral_discount",
                                      " Un **rabais de 20%** sera appliqué à votre premier mois payant.")
            # The welcome email + onboarding guide PDF is sent AFTER the user confirms
            # their address (see app._verify_email), not here — so the guide only reaches
            # a proven-deliverable inbox.
            # L'envoi est dans le chemin de la requête, et il le restera : la réponse
            # doit dire si le mail est parti. Ce qui change, c'est qu'on NOMME
            # l'attente — un spinner muet et un écran figé se ressemblent trop.
            with st.spinner(t("register.sending",
                              "Envoi de ton e-mail de vérification…")):
                email_sent = send_verification_email(email, username, token,
                                                     lang=get_lang())
            _remember_success(artist_name, email, discount_msg,
                              email_sent=email_sent, resend="verify",
                              username=username, token=token)

        except Exception as e:  # noqa: BLE001 — anonymous surface, see module docstring
            ref = public_error_ref(e, logger, "registration")
            st.error(t("register.failed",
                       "L'inscription n'a pas abouti. Réessayez ; si le problème "
                       "persiste, contactez-nous en citant la référence **{ref}**."
                       ).format(ref=ref))

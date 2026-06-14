"""Email verification sender — registration flow.

Type: Utility
Uses: config_loader, smtplib
Depends on: smtp section in config/config.yaml
"""
import os
import smtplib
import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

logger = logging.getLogger(__name__)

# Public base URL used in verification + welcome links. Override in prod via the
# APP_BASE_URL env var (e.g. https://app.streamlytics.io); defaults to local dev.
_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")


def _tr(key: str, fr: str, lang: str, **fmt) -> str:
    """Translate one email string for `lang` (FR = inline source + fallback), then format.

    Reuses the dashboard i18n helper (headless-safe: `translate()` with an explicit lang
    never touches st.session_state). Imported lazily so this module stays importable
    without a Streamlit context if i18n's transitive imports ever change."""
    from src.dashboard.utils.i18n import translate
    txt = translate(key, fr, lang)
    return txt.format(**fmt) if fmt else txt


def _smtp_config() -> dict:
    """SMTP settings. Environment variables take precedence (prod/containers have no
    config.yaml — mirrors the FERNET_KEY/DATABASE_URL env-first pattern); the `smtp`
    section of config/config.yaml is the local-dev fallback."""
    from src.utils.config_loader import config_loader
    cfg = config_loader.load().get('smtp', {})
    env = os.environ
    return {
        'host': env.get('SMTP_HOST') or cfg.get('host', 'smtp.gmail.com'),
        'port': env.get('SMTP_PORT') or cfg.get('port', 587),
        'user': env.get('SMTP_USER') or cfg.get('user', ''),
        'password': env.get('SMTP_PASSWORD') or cfg.get('password', ''),
        'from_name': env.get('SMTP_FROM_NAME') or cfg.get('from_name', 'streaMLytics'),
        # Sender address — distinct from the SMTP login (e.g. Brevo: login is the
        # account/relay user, but the From must be the authenticated domain address
        # noreply@streamlytics.fr for SPF/DKIM alignment). Falls back to the login.
        'from_email': env.get('SMTP_FROM') or cfg.get('from_email', ''),
    }


def _attach_pdf(msg: MIMEMultipart, path: str) -> bool:
    """Attach a PDF to the message. Non-raising — missing file logs + skips."""
    p = Path(path)
    if not p.exists():
        logger.warning("Attachment missing, sending without it: %s", path)
        return False
    part = MIMEBase('application', 'pdf')
    part.set_payload(p.read_bytes())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment', filename=p.name)
    msg.attach(part)
    return True


def _send_html(to_email: str, subject: str, html: str,
               attachments: list[str] | None = None) -> bool:
    """Send one HTML email via the configured SMTP relay. Non-raising.

    Returns False (and logs) when SMTP is not configured or sending fails. Zero or
    more PDF attachments are added (each missing path is skipped, email sent anyway).
    """
    cfg = _smtp_config()
    smtp_host = cfg.get('host', 'smtp.gmail.com')
    smtp_port = int(cfg.get('port', 587))
    smtp_user = cfg.get('user', '')
    smtp_pass = cfg.get('password', '')
    from_name = cfg.get('from_name', 'streaMLytics')
    from_email = cfg.get('from_email') or smtp_user

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured — skipping email '%s'.", subject)
        return False

    try:
        # 'mixed' so the HTML body and the PDF coexist; HTML nested in 'alternative'.
        msg = MIMEMultipart('mixed')
        msg['From']    = f"{from_name} <{from_email}>"
        msg['To']      = to_email
        msg['Subject'] = subject
        body = MIMEMultipart('alternative')
        body.attach(MIMEText(html, 'html'))
        msg.attach(body)
        for _att in (attachments or []):
            _attach_pdf(msg, _att)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info("Email '%s' sent to %s", subject, to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email '%s' to %s: %s", subject, to_email, e)
        return False


def send_welcome_email(to_email: str, username: str, trial_days: int = 30,
                       user_id: int | None = None, lang: str = "fr") -> bool:
    """Welcome email recapping the first onboarding actions. Non-raising.

    Sent once the address is verified. Recaps the onboarding sequence in execution
    order: enter credentials → import CSVs → map Meta campaigns → launch collection
    → explore. Announces the trial and carries the API+CSV guide PDF as attachment.
    Localised (FR/EN) via `lang` — the caller threads the verified user's UI language
    (recovered from the `&lang=` carried on the verification link).
    """
    onboarding_url = f"{_BASE_URL}?page=onboarding&lang={lang}"
    unsub_footer = _unsubscribe_footer(user_id, lang)
    steps = "".join(
        f"<li>{_tr(f'email.welcome.step{i}', fr, lang)}</li>"
        for i, fr in enumerate((
            "<strong>Saisir vos credentials API</strong> (Spotify, YouTube, SoundCloud, "
            "Meta Ads) dans la page <em>🔑 Credentials API</em>.",
            "<strong>Importer vos fichiers CSV</strong> (Spotify for Artists, Apple Music, "
            "iMusician) via la page <em>📥 Import CSV</em> — suivez le <strong>guide PDF "
            "joint</strong> pour les exporter puis les déposer.",
            "<strong>Mapper vos campagnes Meta Ads à vos titres Spotify</strong> dans "
            "<em>🔗 Mapping Spotify × Meta Ads</em> (à faire <em>avant</em> la collecte, "
            "pour relier dépenses et streams dès le premier run).",
            "<strong>Lancer la collecte</strong> via le bouton "
            "« 🚀 Lancer TOUTES les collectes » dans la barre latérale.",
            "Explorer vos dashboards analytics et la prédiction ML « Road to Algo ».",
        ), start=1)
    )
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <h2 style="color: #1DB954;">{_tr('email.welcome.title',
            "🎵 Bienvenue sur streaMLytics, {username} !", lang, username=username)}</h2>
        <p>{_tr('email.welcome.trial',
            "Votre compte est créé avec <strong>{trial_days} jours d'accès complet (Premium)</strong> offerts. 🎁",
            lang, trial_days=trial_days)}</p>
        <h3>{_tr('email.welcome.steps_header', "Vos premières actions, dans l'ordre :", lang)}</h3>
        <ol>{steps}</ol>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{onboarding_url}"
               style="display: inline-block; background-color: #1DB954; color: white;
                      padding: 14px 28px; text-decoration: none; border-radius: 6px;
                      font-size: 16px; line-height: 1.4;">
                {_tr('email.welcome.cta', "Configurer mon dashboard (2 min)", lang)}
            </a>
        </p>
        <p style="color: #888; font-size: 12px;">
            {_tr('email.welcome.guide_note',
                "📎 Le <strong>guide PDF de démarrage (API + import CSV)</strong> est en pièce jointe.<br>"
                "Besoin d'aide ? Consultez la page « 📋 Guide de démarrage » dans l'application.", lang)}
        </p>
        {unsub_footer}
    </body></html>
    """
    subject = _tr('email.welcome.subject',
                  "🎵 Bienvenue — vos premières actions sur streaMLytics", lang)
    return _send_html(to_email, subject, html, attachments=_guide_pdf_paths())


def _unsub_secret() -> bytes:
    """Signing key for unsubscribe tokens — same value in app + DAG so links verify
    in both contexts. Prefers env FERNET_KEY (set in the Airflow container), falls back
    to config.yaml fernet_key (app context), then a constant last-resort."""
    key = os.environ.get('FERNET_KEY')
    if not key:
        try:
            from src.utils.config_loader import config_loader
            key = config_loader.load().get('fernet_key')
        except Exception:
            key = None
    return str(key or 'streamlytics-unsub-fallback').encode()


def unsubscribe_token(user_id: int) -> str:
    """Stable HMAC token tying an unsubscribe link to one user id (no DB column needed)."""
    import hashlib
    import hmac
    return hmac.new(_unsub_secret(), str(user_id).encode(), hashlib.sha256).hexdigest()[:32]


def verify_unsubscribe_token(user_id: int, token: str) -> bool:
    """Constant-time check that `token` matches the expected token for `user_id`."""
    import hmac
    if not token:
        return False
    return hmac.compare_digest(unsubscribe_token(user_id), token)


def _unsubscribe_footer(user_id: int | None, lang: str = "fr") -> str:
    """One-click unsubscribe link (sets marketing_consent=FALSE), or a static notice."""
    style = ("color:#aaa;font-size:11px;margin-top:24px;border-top:1px solid #eee;"
             "padding-top:8px;")
    if user_id is None:
        static = _tr('email.unsub.static',
                     "Pour ne plus recevoir ces emails, décochez l'option dans "
                     "<em>Mon compte → Communications</em>.", lang)
        return f"<p style='{style}'>{static}</p>"
    url = f"{_BASE_URL}?page=unsubscribe&uid={user_id}&t={unsubscribe_token(user_id)}"
    notice = _tr('email.unsub.notice',
                 "Vous recevez cet email car vous avez un compte streaMLytics. ", lang)
    link = _tr('email.unsub.link', "Se désinscrire des communications", lang)
    suffix = _tr('email.unsub.suffix',
                 " (décoche automatiquement l'option email de votre compte).", lang)
    return (f"<p style='{style}'>{notice}"
            f"<a href='{url}' style='color:#aaa;'>{link}</a>{suffix}</p>")


def _guide_pdf_paths() -> list[str]:
    """Prebuilt onboarding guide PDFs to attach (FR + EN), existing files only."""
    try:
        import os
        from src.dashboard.guides.guide_pdf import output_pdf_path
        candidates = [str(output_pdf_path('fr')), str(output_pdf_path('en'))]
        return [p for p in candidates if os.path.exists(p)]
    except Exception as e:  # noqa: BLE001 — attachment is best-effort, never blocks signup
        logger.warning("Guide PDF paths unavailable: %s", e)
        return []


def send_verification_email(to_email: str, username: str, token: str,
                            lang: str = "fr") -> bool:
    """Send a verification email with a link containing the token.

    Localised (FR/EN) via `lang`. The link carries `&lang=` so the post-verification
    welcome email (sent server-side at click time) renders in the same language.
    Returns True on success, False on failure (non-raising).
    """
    cfg = _smtp_config()
    smtp_host = cfg.get('host', 'smtp.gmail.com')
    smtp_port = int(cfg.get('port', 587))
    smtp_user = cfg.get('user', '')
    smtp_pass = cfg.get('password', '')
    from_name = cfg.get('from_name', 'streaMLytics')
    from_email = cfg.get('from_email') or smtp_user

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured — skipping verification email.")
        return False

    verify_url = f"{_BASE_URL}?page=verify&token={token}&lang={lang}"

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <h2 style="color: #1DB954;">{_tr('email.verify.title',
            "🎵 Confirmez votre compte streaMLytics", lang)}</h2>
        <p>{_tr('email.verify.greeting', "Bonjour <strong>{username}</strong>,", lang, username=username)}</p>
        <p>{_tr('email.verify.body',
            "Cliquez sur le bouton ci-dessous pour vérifier votre adresse email et activer votre compte.", lang)}</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}"
               style="display: inline-block; background-color: #1DB954; color: white;
                      padding: 14px 28px; text-decoration: none; border-radius: 6px;
                      font-size: 16px; line-height: 1.4;">
                {_tr('email.verify.button', "Vérifier mon email", lang)}
            </a>
        </p>
        <p style="color: #888; font-size: 12px;">
            {_tr('email.verify.copy', "Ou copiez ce lien : {url}", lang, url=verify_url)}<br>
            {_tr('email.verify.expiry',
                "Ce lien expire dans 48 heures. "
                "Si vous n'avez pas créé de compte, ignorez cet email.", lang)}
        </p>
    </body></html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['From']    = f"{from_name} <{from_email}>"
        msg['To']      = to_email
        msg['Subject'] = _tr('email.verify.subject',
                             "🎵 Vérifiez votre compte streaMLytics", lang)
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"Verification email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")
        return False

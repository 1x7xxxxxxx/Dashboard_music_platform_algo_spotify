"""Email verification sender — registration flow.

Type: Utility
Uses: config_loader, smtplib
Depends on: smtp section in config/config.yaml
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

_BASE_URL = "http://localhost:8501"


def _smtp_config() -> dict:
    from src.utils.config_loader import config_loader
    return config_loader.load().get('smtp', {})


def _send_html(to_email: str, subject: str, html: str) -> bool:
    """Send one HTML email via the configured SMTP relay. Non-raising.

    Returns False (and logs) when SMTP is not configured or sending fails.
    """
    cfg = _smtp_config()
    smtp_host = cfg.get('host', 'smtp.gmail.com')
    smtp_port = int(cfg.get('port', 587))
    smtp_user = cfg.get('user', '')
    smtp_pass = cfg.get('password', '')
    from_name = cfg.get('from_name', 'Music Dashboard')

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured — skipping email '%s'.", subject)
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['From']    = f"{from_name} <{smtp_user}>"
        msg['To']      = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info("Email '%s' sent to %s", subject, to_email)
        return True
    except Exception as e:
        logger.error("Failed to send email '%s' to %s: %s", subject, to_email, e)
        return False


def send_welcome_email(to_email: str, username: str, trial_days: int = 30) -> bool:
    """Welcome email recapping the first onboarding actions. Non-raising.

    Sent right after signup. Recaps: enter credentials, launch collection,
    map Meta campaigns to Spotify tracks. Also announces the full-access trial.
    """
    onboarding_url = f"{_BASE_URL}?page=onboarding"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <h2 style="color: #1DB954;">🎵 Bienvenue sur streaMLytics, {username} !</h2>
        <p>Votre compte est créé avec <strong>{trial_days} jours d'accès complet (Premium)</strong> offerts. 🎁</p>
        <h3>Vos premières actions :</h3>
        <ol>
            <li><strong>Saisir vos credentials API</strong> (Spotify, YouTube, Meta Ads…)
                dans la page <em>🔑 Credentials API</em>.</li>
            <li><strong>Lancer la collecte</strong> via le bouton
                « 🚀 Lancer TOUTES les collectes » dans la barre latérale.</li>
            <li><strong>Mapper vos campagnes Meta Ads à vos titres Spotify</strong>
                dans <em>🔗 Mapping Spotify × Meta Ads</em> pour relier dépenses et streams.</li>
            <li>Explorer vos dashboards analytics et la prédiction ML « Road to Algo ».</li>
        </ol>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{onboarding_url}"
               style="background-color: #1DB954; color: white; padding: 14px 28px;
                      text-decoration: none; border-radius: 6px; font-size: 16px;">
                Configurer mon dashboard (2 min)
            </a>
        </p>
        <p style="color: #888; font-size: 12px;">
            Besoin d'aide ? Consultez la page « 📋 Guide de démarrage » dans l'application.
        </p>
    </body></html>
    """
    return _send_html(to_email, "🎵 Bienvenue — vos premières actions sur streaMLytics", html)


def send_verification_email(to_email: str, username: str, token: str) -> bool:
    """Send a verification email with a link containing the token.

    Returns True on success, False on failure (non-raising).
    """
    cfg = _smtp_config()
    smtp_host = cfg.get('host', 'smtp.gmail.com')
    smtp_port = int(cfg.get('port', 587))
    smtp_user = cfg.get('user', '')
    smtp_pass = cfg.get('password', '')
    from_name = cfg.get('from_name', 'Music Dashboard')

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured — skipping verification email.")
        return False

    verify_url = f"{_BASE_URL}?page=verify&token={token}"

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <h2 style="color: #1DB954;">🎵 Confirm your Music Dashboard account</h2>
        <p>Hi <strong>{username}</strong>,</p>
        <p>Click the button below to verify your email address and activate your account.</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verify_url}"
               style="background-color: #1DB954; color: white; padding: 14px 28px;
                      text-decoration: none; border-radius: 6px; font-size: 16px;">
                Verify my email
            </a>
        </p>
        <p style="color: #888; font-size: 12px;">
            Or copy this link: {verify_url}<br>
            This link expires in 24 hours.
            If you did not create an account, ignore this email.
        </p>
    </body></html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['From']    = f"{from_name} <{smtp_user}>"
        msg['To']      = to_email
        msg['Subject'] = "🎵 Verify your Music Dashboard account"
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

"""App-error notifier — surfaces unhandled Streamlit view exceptions to the admin.

Type: Utility
Uses: usage_tracker (DB log), error_fingerprint, verification_email (config SMTP)
Persists in: usage_events ('error' rows), app_error_log (one row per DEFECT)

Logs the exception, records it, and emails the admin (config.yaml SMTP).
FAIL-SILENT: never raises — it runs inside the page error handler, so it must not
itself break the page.

Since 2026-09-04 the record is the point, not the e-mail. An inbox cannot be counted,
cannot be closed, and cannot be linked to an error class: the same defect arrived three
times in two days as three unrelated-looking messages. `app_error_log` holds ONE row per
fingerprint (migration 083), and `tools/error_inbox.py` renders it into
`.claude/dev-docs/error-inbox.md`, which the roadmap links.

The row is written BEFORE the mail is attempted, deliberately: an SMTP outage must not
also lose the defect.
"""
import logging
import traceback
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Per-process rate-limit: (page, exc_type) -> last-sent datetime. A Streamlit app
# is single-process, so a module-level cache de-dups within the running server.
_last_sent: dict[tuple[str, str], datetime] = {}
_COOLDOWN_MIN = 15

# Streamlit control-flow exceptions must NEVER be treated as errors (they ARE the
# mechanism behind st.stop()/st.rerun()); the caller re-raises them, this is a
# second guard in case one slips through.
_CONTROL_EXC = {"RerunException", "StopException", "RerunData"}


def is_control_flow(exc: BaseException) -> bool:
    """True for Streamlit st.stop()/st.rerun() signals — must be re-raised, not alerted."""
    return type(exc).__name__ in _CONTROL_EXC


def notify_app_error(page: str, exc: BaseException) -> None:
    """Log + record + (rate-limited) email an unhandled view exception. Never raises."""
    if is_control_flow(exc):
        return
    try:
        logger.error("App error on page '%s': %s", page, exc, exc_info=exc)
    except Exception:
        pass
    try:
        from src.dashboard.utils.usage_tracker import track
        from src.utils.safe_error import redact
        track('error', page=page,
              meta={'type': type(exc).__name__, 'msg': redact(exc)[:200]})
    except Exception:
        pass
    # La LIGNE d'abord, l'e-mail ensuite, et jamais l'inverse. Une boîte mail n'est pas
    # un registre : on ne peut ni compter, ni fermer, ni relier à une classe d'erreur.
    # L'ordre compte aussi : si l'envoi échoue (SMTP en panne, quota Brevo), le défaut
    # reste enregistré. L'inverse perdrait exactement ce qu'on cherche à garder.
    fingerprint = None
    try:
        fingerprint = _record(page, exc)
    except Exception:
        pass
    try:
        _maybe_email(page, exc, fingerprint)
    except Exception:
        pass


def _record(page: str, exc: BaseException) -> str | None:
    """Resolve who and where, then hand the write to the framework-free registry."""
    from src.dashboard.utils import get_db_connection
    from src.utils.error_registry import record_error
    from src.utils.instance_identity import instance_env

    # `st.session_state` outside a script run raises in some Streamlit versions, and
    # the tenant is a NICE-TO-HAVE on an error row: never let it cost us the row.
    artist_id = None
    try:
        import streamlit as st
        artist_id = st.session_state.get('artist_id')
    except Exception:      # noqa: BLE001
        pass

    db = get_db_connection()
    if db is None:
        return None
    try:
        return record_error(db, page, exc, artist_id, instance_env())
    finally:
        try:
            db.close()
        except Exception:      # noqa: BLE001
            pass


def _maybe_email(page: str, exc: BaseException, fingerprint: str | None = None) -> None:
    key = (page or '?', type(exc).__name__)
    now = datetime.now(timezone.utc)
    last = _last_sent.get(key)
    if last and (now - last).total_seconds() < _COOLDOWN_MIN * 60:
        return
    # Le garde de débit qui SURVIT à un redémarrage. `_last_sent` est un dict de
    # processus : recréer le conteneur renvoyait le même e-mail, et c'est arrivé.
    if fingerprint and not _email_due(fingerprint, now):
        return
    from src.utils.verification_email import _send_html, _smtp_config
    to = (_smtp_config() or {}).get('user')
    if not to:
        return
    # Rédaction AVANT l'envoi. Ce mail part par Brevo — un tiers — et se dépose
    # dans une boîte. Un message d'exception `requests` embarque l'URL préparée,
    # donc `access_token=` / `key=` en clair, et la traceback en contient
    # plusieurs. Le rapport reste complet ; seules les VALEURS de credentials
    # partent. Trouvé le 2026-08-24 en cherchant les fonctions qui interpolent une
    # exception REÇUE en paramètre — la question que le garde anti-fuite ne posait
    # pas : sa portée suit le graphe d'imports, et une exception passée en
    # ARGUMENT ne laisse aucune trace dans ce graphe.
    from src.utils.safe_error import redact

    tb = redact(''.join(
        traceback.format_exception(type(exc), exc, exc.__traceback__))[-2500:])
    # L'empreinte dans le corps du mail : c'est ce qui relie CE message à la ligne du
    # registre, donc à `make error-inbox` et à la commande qui le referme. Sans elle,
    # le lecteur du mail doit retrouver la ligne à la main.
    fp_line = (f"<p style='color:#666'>Empreinte <code>{fingerprint[:12]}</code> — "
               f"<code>make error-inbox</code> pour le registre, "
               f"<code>make error-resolve FP={fingerprint[:12]} NOTE=\"…\"</code> "
               f"pour la fermer.</p>") if fingerprint else ""
    html = (f"<h3>⚠️ Erreur app — page <code>{page}</code></h3>"
            f"<p><b>{type(exc).__name__}</b>: {redact(exc)}</p>"
            f"{fp_line}"
            f"<pre style='font-size:11px'>{tb}</pre>")
    if _send_html(to, f"⚠️ streaMLytics — erreur sur '{page}'", html):
        _last_sent[key] = now
        _mark_emailed(fingerprint)


def _email_due(fingerprint: str, now: datetime) -> bool:
    """A defect emailed less than `_COOLDOWN_MIN` ago stays quiet — across restarts.

    Fail-OPEN: if the registry cannot be read, the mail goes out. Losing an alert to a
    database hiccup is worse than one duplicate.
    """
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return True
        try:
            rows = db.fetch_query(
                "SELECT last_emailed_at FROM app_error_log WHERE fingerprint = %s",
                (fingerprint,))
        finally:
            db.close()
    except Exception:      # noqa: BLE001 — la télémétrie ne bloque jamais l'alerte
        return True
    if not rows or rows[0][0] is None:
        return True
    return (now - rows[0][0]).total_seconds() >= _COOLDOWN_MIN * 60


def _mark_emailed(fingerprint: str | None) -> None:
    if not fingerprint:
        return
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return
        try:
            db.execute_query(
                "UPDATE app_error_log SET last_emailed_at = NOW() WHERE fingerprint = %s",
                (fingerprint,))
        finally:
            db.close()
    except Exception:      # noqa: BLE001 — un horodatage manqué renvoie un doublon, rien de plus
        pass

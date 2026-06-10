"""App-error notifier — surfaces unhandled Streamlit view exceptions to the admin.

Type: Utility
Uses: usage_tracker (DB log), verification_email (config SMTP)
Persists in: usage_events ('error' rows)

Logs the exception, records a usage_events 'error' row, and emails the admin
(config.yaml SMTP), rate-limited per (page, exception-type) to avoid an error
loop spamming the inbox. FAIL-SILENT: never raises — it runs inside the page
error handler, so it must not itself break the page.
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
        track('error', page=page,
              meta={'type': type(exc).__name__, 'msg': str(exc)[:200]})
    except Exception:
        pass
    try:
        _maybe_email(page, exc)
    except Exception:
        pass


def _maybe_email(page: str, exc: BaseException) -> None:
    key = (page or '?', type(exc).__name__)
    now = datetime.now(timezone.utc)
    last = _last_sent.get(key)
    if last and (now - last).total_seconds() < _COOLDOWN_MIN * 60:
        return
    from src.utils.verification_email import _send_html, _smtp_config
    to = (_smtp_config() or {}).get('user')
    if not to:
        return
    tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-2500:]
    html = (f"<h3>⚠️ Erreur app — page <code>{page}</code></h3>"
            f"<p><b>{type(exc).__name__}</b>: {exc}</p>"
            f"<pre style='font-size:11px'>{tb}</pre>")
    if _send_html(to, f"⚠️ streaMLytics — erreur sur '{page}'", html):
        _last_sent[key] = now

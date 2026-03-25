"""MonitoredSession — requests.Session wrapper with automatic HTTP logging.

Logs every request: method, host (URL masked), status code, response time.
Warns on 4xx/5xx and tracks consecutive failures per host.

Usage:
    from src.utils.http_logger import MonitoredSession
    session = MonitoredSession(platform='soundcloud')
    resp = session.get('https://api.soundcloud.com/tracks', params={...})

Drop-in replacement for requests.Session / requests.get.
"""
import logging
import time
import re
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)

# Number of consecutive failures before emitting a warning summary
_FAILURE_WARN_THRESHOLD = 3

# Patterns in URLs that may contain secrets — masked in logs
_SECRET_PARAMS = re.compile(
    r'(client_secret|access_token|token|secret|password|api_key|apikey|key)=[^&]+',
    re.IGNORECASE,
)


def _mask_url(url: str) -> str:
    """Remove sensitive query params from URL for safe logging."""
    return _SECRET_PARAMS.sub(r'\1=***', url)


def _classify_status(status: int) -> tuple[str, str]:
    """Return (emoji, level_name) for a status code."""
    if status < 300:
        return '✅', 'info'
    if status < 400:
        return '↩️', 'info'
    if status == 401:
        return '🔑', 'error'
    if status == 403:
        return '🚫', 'error'
    if status == 404:
        return '🔍', 'warning'
    if status == 429:
        return '⏳', 'warning'
    if status >= 500:
        return '💥', 'error'
    return '⚠️', 'warning'


class MonitoredSession(requests.Session):
    """requests.Session with automatic per-request logging and anomaly detection."""

    def __init__(self, platform: str = 'unknown', slow_threshold_ms: int = 3000):
        super().__init__()
        self.platform = platform
        self.slow_threshold_ms = slow_threshold_ms
        self._failure_counts: dict[str, int] = {}  # host → consecutive failures

    def request(self, method: str, url: str, **kwargs):
        host = urlparse(url).netloc
        safe_url = _mask_url(url)
        t0 = time.monotonic()

        try:
            resp = super().request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            self._failure_counts[host] = self._failure_counts.get(host, 0) + 1
            logger.error(
                f"[{self.platform}] CONNECTION ERROR {method} {safe_url} — {e} "
                f"(consecutive failures: {self._failure_counts[host]})"
            )
            raise
        except requests.exceptions.Timeout as e:
            logger.warning(f"[{self.platform}] TIMEOUT {method} {safe_url} — {e}")
            raise

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        emoji, level_name = _classify_status(resp.status_code)

        log_line = (
            f"[{self.platform}] {emoji} {method} {safe_url} "
            f"→ {resp.status_code} ({elapsed_ms}ms)"
        )

        # Consecutive failure tracking
        if resp.status_code >= 400:
            self._failure_counts[host] = self._failure_counts.get(host, 0) + 1
            count = self._failure_counts[host]
            if count >= _FAILURE_WARN_THRESHOLD:
                log_line += f" ⚠️ [{count} consecutive failures on {host}]"
        else:
            self._failure_counts[host] = 0  # reset on success

        # Slow request warning
        if elapsed_ms > self.slow_threshold_ms:
            log_line += f" 🐢 SLOW (>{self.slow_threshold_ms}ms)"

        getattr(logger, level_name)(log_line)

        # Extra context for 4xx/5xx
        if resp.status_code == 401:
            logger.error(
                f"[{self.platform}] 401 Unauthorized — "
                "token expired or invalid. Action: Dashboard → Credentials → renew token."
            )
        elif resp.status_code == 429:
            retry_after = resp.headers.get('Retry-After', 'unknown')
            logger.warning(
                f"[{self.platform}] 429 Rate limited — Retry-After: {retry_after}s. "
                "Reduce collection frequency or wait before retrying."
            )

        return resp

    def get_failure_count(self, host: str = None) -> int:
        if host:
            return self._failure_counts.get(host, 0)
        return sum(self._failure_counts.values())

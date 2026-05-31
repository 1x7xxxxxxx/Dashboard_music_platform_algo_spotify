"""Subscription plan-history logging.

Type: Utility
Uses: PostgresHandler (caller-provided)
Persists in: subscription_plan_history (append-only)

Records one row per plan transition so the Alerts view can chart artists-per-plan
over time. Append-only; non-raising — a logging failure must never break the
business action that triggered it (signup, promo grant, admin edit, webhook).
"""
import logging

logger = logging.getLogger(__name__)

_VALID_PLANS = {'free', 'basic', 'premium'}


def log_plan_change(db, artist_id: int, plan: str, source: str = 'unknown') -> None:
    """Append a plan transition. Swallows errors (logs a warning)."""
    if plan not in _VALID_PLANS:
        logger.warning("log_plan_change: unexpected plan '%s' for artist %s", plan, artist_id)
    try:
        db.execute_query(
            "INSERT INTO subscription_plan_history (artist_id, plan, source) "
            "VALUES (%s, %s, %s)",
            (artist_id, plan, source),
        )
    except Exception as e:  # noqa: BLE001 — best-effort audit log
        logger.warning("plan_history log failed for artist %s: %s", artist_id, e)

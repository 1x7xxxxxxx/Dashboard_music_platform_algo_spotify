"""Alerting Dashboard — Brick 30.

Type: Feature
Uses: get_db_connection, AirflowMonitor, get_source_freshness, freshness_status
Depends on: etl_circuit_breaker, etl_run_log, saas_users, artist_subscriptions
Accessible to all authenticated users (artists see their own data; admins see all).
"""
import html as _html
from datetime import datetime, timezone, timedelta

import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
)


# ── Section 1: Circuit breakers ───────────────────────────────────

def _section_circuit_breakers(db, artist_id) -> int:
    """Returns count of OPEN/HALF_OPEN circuits."""
    if artist_id is not None:
        rows = db.fetch_query(
            """
            SELECT platform, artist_id, state, failure_count, last_failure_at, last_error
            FROM etl_circuit_breaker
            WHERE artist_id = %s AND state != 'closed'
            ORDER BY state DESC, failure_count DESC
            """,
            (artist_id,),
        )
    else:
        rows = db.fetch_query(
            """
            SELECT platform, artist_id, state, failure_count, last_failure_at, last_error
            FROM etl_circuit_breaker
            WHERE state != 'closed'
            ORDER BY state DESC, failure_count DESC
            """
        )

    if not rows:
        st.success("✅ All circuits closed — no platform collection failures.")
        return 0

    for row in rows:
        platform, aid, state, failures, last_fail, last_error = row
        color = "#e74c3c" if state == "open" else "#f39c12"
        icon  = "🔴" if state == "open" else "🟡"
        fail_str = pd.to_datetime(last_fail).strftime("%d/%m %H:%M") if last_fail else "—"
        st.markdown(
            f"{icon} **{_html.escape(str(platform))}** "
            f"(artist #{int(aid)}) — "
            f"<span style='color:{_html.escape(color)};font-weight:bold'>"
            f"{_html.escape(state.upper())}</span> "
            f"— {int(failures)} failure(s) — last: {_html.escape(fail_str)}",
            unsafe_allow_html=True,
        )
        if last_error:
            st.caption(f"↳ {str(last_error)[:120]}")
    return len(rows)


# ── Section 2: Data freshness ─────────────────────────────────────

def _section_freshness_alerts(db, artist_id) -> int:
    """Returns count of stale (orange/red) sources."""
    freshness = get_source_freshness(db, artist_id)
    stale = [
        (label, info)
        for label, info in freshness.items()
        if freshness_status(info['last_dt'])[1] in ('#e74c3c', '#f39c12')
    ]
    if not stale:
        st.success("✅ All data sources are fresh.")
        return 0

    for label, info in stale:
        emoji, color, age_label = freshness_status(info['last_dt'])
        date_str = info['last_dt'].strftime("%d/%m %H:%M") if info['last_dt'] else "never"
        icon = "🔴" if color == '#e74c3c' else "🟡"
        st.markdown(
            f"{icon} **{_html.escape(label)}** — "
            f"<span style='color:{_html.escape(color)}'>{_html.escape(age_label)}</span> "
            f"(last: {_html.escape(date_str)})",
            unsafe_allow_html=True,
        )
    return len(stale)


# ── Section 3: Recent DAG failures ───────────────────────────────

def _section_dag_failures(db, artist_id) -> int:
    """Returns count of DAG failures in the last 24 hours."""
    if artist_id is not None:
        df = db.fetch_df(
            """
            SELECT dag_id, platform, started_at, error_type, error_message
            FROM etl_run_log
            WHERE artist_id = %s AND status = 'failed'
              AND started_at >= NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC LIMIT 50
            """,
            (artist_id,),
        )
    else:
        df = db.fetch_df(
            """
            SELECT dag_id, platform, artist_id, started_at, error_type, error_message
            FROM etl_run_log
            WHERE status = 'failed'
              AND started_at >= NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC LIMIT 50
            """
        )

    if df.empty:
        st.success("✅ No DAG failures in the last 24 hours.")
        return 0

    df['started_at'] = pd.to_datetime(df['started_at']).dt.strftime('%d/%m %H:%M')
    st.dataframe(df, hide_index=True, width="stretch")
    return len(df)


# ── Section 4: Suspicious login activity (admin only) ────────────

def _section_login_alerts(db) -> int:
    """Returns count of currently locked accounts."""
    rows = db.fetch_query(
        """
        SELECT username, email, failed_login_attempts, locked_until
        FROM saas_users
        WHERE locked_until > NOW()
        ORDER BY locked_until DESC
        """
    )
    if not rows:
        st.success("✅ No accounts currently locked.")
        return 0

    for uname, email, attempts, locked_until in rows:
        lu_str = pd.to_datetime(locked_until).strftime("%d/%m %H:%M") if locked_until else "—"
        st.markdown(
            f"🔒 **{_html.escape(str(uname))}** ({_html.escape(str(email))}) — "
            f"{int(attempts)} failed attempt(s) — locked until {_html.escape(lu_str)}"
        )
    return len(rows)


# ── Section 5: Billing / subscription alerts (admin only) ─────────

def _section_billing_alerts(db) -> int:
    rows = db.fetch_query(
        """
        SELECT a.name, asub.status, asub.current_period_end
        FROM artist_subscriptions asub
        JOIN saas_artists a ON a.id = asub.artist_id
        WHERE asub.status IN ('past_due', 'canceled', 'unpaid')
           OR (asub.status = 'active' AND asub.current_period_end < NOW() + INTERVAL '7 days')
        ORDER BY asub.current_period_end ASC
        """
    )
    if not rows:
        st.success("✅ No billing issues detected.")
        return 0

    for artist_name, status, period_end in rows:
        end_str = pd.to_datetime(period_end).strftime("%d/%m/%Y") if period_end else "—"
        icon = "🔴" if status in ('past_due', 'unpaid', 'canceled') else "🟡"
        st.markdown(
            f"{icon} **{_html.escape(str(artist_name))}** — "
            f"status: `{_html.escape(str(status))}` — period ends: {_html.escape(end_str)}"
        )
    return len(rows)


# ── Entry point ───────────────────────────────────────────────────

def show():
    st.title("🚨 Alerting Dashboard")
    st.caption("Real-time status of platform health, data freshness, and security events.")

    db = get_db_connection()
    if db is None:
        st.error("❌ Database unreachable.")
        return

    artist_id = get_artist_id()
    if artist_id is None and not is_admin():
        st.error("Session invalide.")
        st.stop()

    admin = is_admin()

    try:
        # Summary banner
        total_alerts = 0

        st.subheader("🔌 Circuit Breakers")
        total_alerts += _section_circuit_breakers(db, artist_id)
        st.markdown("---")

        st.subheader("📡 Data Freshness")
        total_alerts += _section_freshness_alerts(db, artist_id)
        st.markdown("---")

        st.subheader("❌ DAG Failures (last 24h)")
        total_alerts += _section_dag_failures(db, artist_id)

        if admin:
            st.markdown("---")
            st.subheader("🔒 Locked Accounts")
            total_alerts += _section_login_alerts(db)
            st.markdown("---")
            st.subheader("💳 Billing Alerts")
            total_alerts += _section_billing_alerts(db)

        if total_alerts == 0:
            st.balloons()
            st.success("✅ Everything looks healthy. No active alerts.")
        else:
            st.sidebar.error(f"🚨 {total_alerts} active alert(s)")

    finally:
        db.close()

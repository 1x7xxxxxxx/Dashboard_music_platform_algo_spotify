"""Alerting Dashboard — Brick 30.

Type: Feature
Uses: get_db_connection, AirflowMonitor, get_source_freshness, freshness_status
Depends on: etl_circuit_breaker, etl_run_log, saas_users, artist_subscriptions
Accessible to all authenticated users (artists see their own data; admins see all).
"""
import html as _html

import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
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
        st.success(t("alerts.circuits_all_closed", "✅ All circuits closed — no platform collection failures."))
        return 0

    for row in rows:
        platform, aid, state, failures, last_fail, last_error = row
        color = "#e74c3c" if state == "open" else "#f39c12"
        icon  = "🔴" if state == "open" else "🟡"
        fail_str = pd.to_datetime(last_fail).strftime("%d/%m %H:%M") if last_fail else "—"
        st.markdown(
            f"{icon} **{_html.escape(str(platform))}** "
            + t(
                "alerts.circuit_line",
                "(artist #{aid}) — <span style='color:{color};font-weight:bold'>{state}</span> — {failures} failure(s) — last: {fail_str}",
            ).format(
                aid=int(aid),
                color=_html.escape(color),
                state=_html.escape(state.upper()),
                failures=int(failures),
                fail_str=_html.escape(fail_str),
            ),
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
        st.success(t("alerts.sources_all_fresh", "✅ All data sources are fresh."))
        return 0

    for label, info in stale:
        emoji, color, age_label = freshness_status(info['last_dt'])
        date_str = info['last_dt'].strftime("%d/%m %H:%M") if info['last_dt'] else "never"
        icon = "🔴" if color == '#e74c3c' else "🟡"
        st.markdown(
            f"{icon} **{_html.escape(label)}** — "
            + t(
                "alerts.freshness_line",
                "<span style='color:{color}'>{age_label}</span> (last: {date_str})",
            ).format(
                color=_html.escape(color),
                age_label=_html.escape(age_label),
                date_str=_html.escape(date_str),
            ),
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
        st.success(t("alerts.no_dag_failures", "✅ No DAG failures in the last 24 hours."))
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
        st.success(t("alerts.no_locked_accounts", "✅ No accounts currently locked."))
        return 0

    for uname, email, attempts, locked_until in rows:
        lu_str = pd.to_datetime(locked_until).strftime("%d/%m %H:%M") if locked_until else "—"
        st.markdown(
            f"🔒 **{_html.escape(str(uname))}** ({_html.escape(str(email))}) — "
            + t(
                "alerts.locked_line",
                "{attempts} failed attempt(s) — locked until {lu_str}",
            ).format(attempts=int(attempts), lu_str=_html.escape(lu_str))
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
        st.success(t("alerts.no_billing_issues", "✅ No billing issues detected."))
        return 0

    for artist_name, status, period_end in rows:
        end_str = pd.to_datetime(period_end).strftime("%d/%m/%Y") if period_end else "—"
        icon = "🔴" if status in ('past_due', 'unpaid', 'canceled') else "🟡"
        st.markdown(
            f"{icon} **{_html.escape(str(artist_name))}** — "
            + t(
                "alerts.billing_line",
                "status: `{status}` — period ends: {end_str}",
            ).format(status=_html.escape(str(status)), end_str=_html.escape(end_str))
        )
    return len(rows)


# ── Admin: subscription analytics ─────────────────────────────────

def _section_plan_evolution(db) -> None:
    """Stacked-area chart of the number of artists per plan over time.

    Reconstructs each artist's effective plan as-of monthly snapshots from the
    append-only subscription_plan_history table (seeded by migration 029's
    backfill). Returns nothing — purely informational (no alert count).
    """
    import plotly.express as px

    rows = db.fetch_query(
        "SELECT artist_id, plan, changed_at FROM subscription_plan_history "
        "ORDER BY changed_at"
    )
    if not rows:
        st.info(
            t(
                "alerts.no_plan_history",
                "Aucun historique de plan pour l'instant. Le graphique se remplit "
                "au fil des inscriptions et des changements de plan.",
            )
        )
        return

    hist = pd.DataFrame(rows, columns=['artist_id', 'plan', 'changed_at'])
    # Normalise to tz-naive UTC so comparisons with the bucket timestamps work.
    hist['changed_at'] = pd.to_datetime(hist['changed_at'], utc=True).dt.tz_localize(None)

    start = hist['changed_at'].min().normalize().replace(day=1)
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    buckets = pd.date_range(start=start, end=today, freq='MS')
    # Always include "now" as the final point so the latest state is shown.
    buckets = buckets.append(pd.DatetimeIndex([today])).unique()

    records = []
    for b in buckets:
        asof = hist[hist['changed_at'] <= b]
        if asof.empty:
            continue
        latest = asof.sort_values('changed_at').groupby('artist_id').tail(1)
        counts = latest['plan'].value_counts()
        for plan in ('free', 'basic', 'premium'):
            records.append({'Date': b, 'Plan': plan.capitalize(),
                            'Artistes': int(counts.get(plan, 0))})

    chart_df = pd.DataFrame(records)
    fig = px.area(
        chart_df, x='Date', y='Artistes', color='Plan',
        category_orders={'Plan': ['Free', 'Basic', 'Premium']},
        color_discrete_map={'Free': '#9E9E9E', 'Basic': '#2196F3', 'Premium': '#1DB954'},
        title=t("alerts.plan_chart_title", "Évolution du nombre d'artistes — total et par plan"),
    )
    # Explicit total-artists line on top of the per-plan stacked areas.
    totals = chart_df.groupby('Date', as_index=False)['Artistes'].sum()
    fig.add_scatter(
        x=totals['Date'], y=totals['Artistes'],
        mode='lines+markers', name=t("alerts.total_artists", "Total artistes"),
        line=dict(color='#FFFFFF', width=2, dash='dot'),
    )
    fig.update_layout(hovermode='x unified', height=400, legend_title_text='')
    st.plotly_chart(fig, width="stretch")

    # Current snapshot KPIs (latest bucket).
    latest_date = chart_df['Date'].max()
    snap = chart_df[chart_df['Date'] == latest_date]
    cols = st.columns(4)
    cols[0].metric(t("alerts.total_artists", "Total artistes"), int(snap['Artistes'].sum()))
    for col, plan in zip(cols[1:], ['Free', 'Basic', 'Premium']):
        val = int(snap[snap['Plan'] == plan]['Artistes'].sum())
        col.metric(plan, val)


def _section_users_table(db) -> None:
    """Table of every user: email, signup date, and effective plan."""
    from datetime import datetime, timezone

    rows = db.fetch_query(
        "SELECT u.email, u.username, u.role, u.created_at, "
        "       a.tier, a.promo_plan, a.promo_plan_expires_at "
        "FROM saas_users u "
        "LEFT JOIN saas_artists a ON a.id = u.artist_id "
        "ORDER BY u.created_at DESC"
    )
    if not rows:
        st.info(t("alerts.no_users", "Aucun utilisateur enregistré."))
        return

    now = datetime.now(timezone.utc)

    def _effective_plan(tier, promo_plan, promo_exp) -> str:
        if promo_plan and (promo_exp is None or promo_exp > now):
            return promo_plan
        return tier or 'free'

    table = []
    for email, username, role, created_at, tier, promo_plan, promo_exp in rows:
        table.append({
            t("alerts.col_email", "Email"): email,
            t("alerts.col_username", "Username"): username,
            t("alerts.col_role", "Rôle"): role,
            t("alerts.col_signup", "Inscription"): created_at.strftime('%Y-%m-%d') if created_at else "—",
            t("alerts.col_plan", "Plan"): _effective_plan(tier, promo_plan, promo_exp).capitalize(),
        })
    st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)


# ── Entry point ───────────────────────────────────────────────────

def show():
    st.title(t("alerts.title", "🚨 Alerting Dashboard"))
    st.caption(t("alerts.caption", "Real-time status of platform health, data freshness, and security events."))

    db = get_db_connection()
    if db is None:
        st.error(t("alerts.db_unreachable", "❌ Database unreachable."))
        return

    artist_id = get_artist_id()
    if artist_id is None and not is_admin():
        st.error(t("alerts.invalid_session", "Session invalide."))
        st.stop()

    admin = is_admin()

    try:
        # Summary banner
        total_alerts = 0

        st.subheader(t("alerts.section_circuits", "🔌 Circuit Breakers"))
        total_alerts += _section_circuit_breakers(db, artist_id)
        st.markdown("---")

        st.subheader(t("alerts.section_freshness", "📡 Data Freshness"))
        total_alerts += _section_freshness_alerts(db, artist_id)
        st.markdown("---")

        st.subheader(t("alerts.section_dag_failures", "❌ DAG Failures (last 24h)"))
        total_alerts += _section_dag_failures(db, artist_id)

        if admin:
            st.markdown("---")
            st.subheader(t("alerts.section_locked", "🔒 Locked Accounts"))
            total_alerts += _section_login_alerts(db)
            st.markdown("---")
            st.subheader(t("alerts.section_billing", "💳 Billing Alerts"))
            total_alerts += _section_billing_alerts(db)
            st.markdown("---")
            st.subheader(t("alerts.section_plan_evolution", "📈 Évolution des plans"))
            _section_plan_evolution(db)
            st.markdown("---")
            st.subheader(t("alerts.section_users", "👥 Utilisateurs (email & date d'inscription)"))
            _section_users_table(db)

        if total_alerts == 0:
            st.balloons()
            st.success(t("alerts.all_healthy", "✅ Everything looks healthy. No active alerts."))
        else:
            st.sidebar.error(
                t("alerts.active_count", "🚨 {n} active alert(s)").format(n=total_alerts)
            )

    finally:
        db.close()

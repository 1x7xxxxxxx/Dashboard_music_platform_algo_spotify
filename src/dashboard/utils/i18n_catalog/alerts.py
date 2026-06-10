"""EN catalog for the alerts view."""

EN = {
    # Entry point
    "alerts.title": "🚨 Alerting Dashboard",
    "alerts.caption": "Real-time status of platform health, data freshness, and security events.",
    "alerts.db_unreachable": "❌ Database unreachable.",
    "alerts.invalid_session": "Invalid session.",
    "alerts.all_healthy": "✅ Everything looks healthy. No active alerts.",
    "alerts.active_count": "🚨 {n} active alert(s)",
    # Section headers
    "alerts.section_circuits": "🔌 Circuit Breakers",
    "alerts.section_freshness": "📡 Data Freshness",
    "alerts.section_dag_failures": "❌ DAG Failures (last 24h)",
    "alerts.section_locked": "🔒 Locked Accounts",
    "alerts.section_billing": "💳 Billing Alerts",
    "alerts.section_plan_evolution": "📈 Plan evolution",
    "alerts.section_users": "👥 Users (email & signup date)",
    # Circuit breakers
    "alerts.circuits_all_closed": "✅ All circuits closed — no platform collection failures.",
    "alerts.circuit_line": "(artist #{aid}) — <span style='color:{color};font-weight:bold'>{state}</span> — {failures} failure(s) — last: {fail_str}",
    # Freshness
    "alerts.sources_all_fresh": "✅ All data sources are fresh.",
    "alerts.freshness_line": "<span style='color:{color}'>{age_label}</span> (last: {date_str})",
    # DAG failures
    "alerts.no_dag_failures": "✅ No DAG failures in the last 24 hours.",
    # Locked accounts
    "alerts.no_locked_accounts": "✅ No accounts currently locked.",
    "alerts.locked_line": "{attempts} failed attempt(s) — locked until {lu_str}",
    # Billing
    "alerts.no_billing_issues": "✅ No billing issues detected.",
    "alerts.billing_line": "status: `{status}` — period ends: {end_str}",
    # Plan evolution
    "alerts.no_plan_history": "No plan history yet. The chart fills up as signups and plan changes accumulate.",
    "alerts.plan_chart_title": "Artist count over time — total and per plan",
    "alerts.total_artists": "Total artists",
    # Users table
    "alerts.no_users": "No registered users.",
    "alerts.col_email": "Email",
    "alerts.col_username": "Username",
    "alerts.col_role": "Role",
    "alerts.col_signup": "Signup",
    "alerts.col_plan": "Plan",
}

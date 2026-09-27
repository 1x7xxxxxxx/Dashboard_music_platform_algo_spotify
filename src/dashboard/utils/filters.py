"""The shared filters — ONE import for period, entity (track) and ad account.

Type: Utility
Uses: src/dashboard/utils/period_filter.py, src/dashboard/utils/meta_accounts.py
Triggers: the views that filter what they draw
Persists in: nothing

R232 (2026-09-27). The owner asked for one filter architecture: time, track, platform,
account — the same labels everywhere. The layer already existed in pieces; this module
is its front door, and adds NO logic of its own (code-critic, R232): a second
implementation next to `period_filter` would have to be kept in sync forever.

  period()   → smart_period_filter  — presets, grain, custom range, span-bounded
  span()     → span_period_filter   — the same selector over a span already known (R259)
  entity()   → entity_period_filter — a track by its canonical key (`match_key`)
  account()  → account_scope / account_clause — the Meta ad account (ADR-013)

A view that draws an analysis window uses `period()`. A date typed INTO a form (a
cost's start month, a promo code's expiry, a manual campaign entry) is data entry,
not a filter, and stays a plain `st.date_input`.
Guard: tests/test_a_view_filters_through_the_shared_layer.py

Deliberately NOT here yet (code-critic): a period shared across pages, or carried in
the URL. Views anchor differently (last release, data span, fixed window) — carrying
one page's window to another shows an empty page; `st.query_params` already routes
auth and navigation. A separate, reviewed change.
"""
from src.dashboard.utils.meta_accounts import account_clause, account_scope, table_carries_account
from src.dashboard.utils.period_filter import (
    EntitySpec,
    PeriodWindow,
    entity_period_filter,
    latest_release_date,
    smart_period_filter,
    span_period_filter,
)

period = smart_period_filter
span = span_period_filter
entity = entity_period_filter
account = account_scope

__all__ = ["EntitySpec", "PeriodWindow", "account", "account_clause", "account_scope",
           "entity", "entity_period_filter", "latest_release_date", "period",
           "smart_period_filter", "span", "span_period_filter", "table_carries_account"]

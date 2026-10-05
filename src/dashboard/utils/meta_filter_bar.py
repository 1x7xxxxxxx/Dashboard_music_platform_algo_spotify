"""One filter set for the Meta cross view: account, campaign, period (R399).

Type: Utility
Uses: streamlit, src.dashboard.utils.meta_accounts, src.dashboard.utils.period_filter,
      src.dashboard.utils.campaign_pair
Triggers: src/dashboard/views/meta_ads_overview.py (`show`), once per render
Persists in: st.session_state (widget keys only)

Before R399 each of the four Meta sections drew its OWN account, campaign and period
selectors — four account widgets, three campaign lists ordered three ways, two second-
campaign pickers — and a campaign chosen in « Performance » was forgotten one click away
in « Visuels ». The owner's demand (2026-10-05): « les mêmes filtres à chaque fois ».

The bar is drawn once, at the head of the page, and every section reads its result:
  - the account (`account_scope`) and the campaign (« Toutes » or one, plus the shared
    second campaign of R350);
  - the period FOLLOWS the campaign when one is chosen (`campaign_window`: the campaign,
    the campaign + its tail, or up to today), and is the shared free filter on « Toutes »;
  - « Qui a vu tes pubs » has no date dimension: the period is shown greyed, `window=None`;
  - Instagram (organic) sits outside the bar — no ad account, no campaign — and says so.

Any other selector of these sections is allowlisted by key with its reason in
`tests/test_the_meta_page_has_one_filter_bar.py`.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src.dashboard.utils import filters
from src.dashboard.utils.campaign_pair import second_campaign
from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.i18n import t
from src.dashboard.utils.meta_accounts import account_clause, account_scope, tenant_ad_accounts
from src.dashboard.utils.period_filter import PeriodWindow

ALL = "Toutes"           # internal sentinel; only its display is translated
TAIL_DAYS = 28           # the rémanence a campaign is judged on after its last euro
ACCOUNT_KEY = "meta_acct"  # pragma: allowlist secret
CAMPAIGN_KEY = "meta_campaign"
SECOND_KEY = "meta_second"
PERIOD_KEY = "meta_period"
WINDOW_KEY = "meta_win"


@dataclass(frozen=True)
class MetaFilters:
    account: str | None             # None = no account predicate
    campaigns: tuple[str, ...]      # every campaign offered, most recently launched first
    campaign: str | None            # None = « Toutes »
    second: str | None              # the R350 comparison campaign, only beside one campaign
    window: PeriodWindow | None     # None = the section has no date dimension

    def acct(self, alias: str = "") -> tuple[str, tuple]:
        return account_clause(self.account, alias)

    @property
    def scope(self) -> tuple[str, ...]:
        """The campaigns in scope — `()` means all of them."""
        return tuple(c for c in (self.campaign, self.second) if c)


def _campaign_spans(db, artist_id: int, account: str | None) -> pd.DataFrame:
    acct, acct_p = account_clause(account)
    return db.fetch_df(
        "SELECT campaign_name, MIN(day) AS first_day, MAX(day) AS last_day "
        f"FROM v_meta_campaign_daily WHERE artist_id = %s{acct} AND campaign_name IS NOT NULL "
        "GROUP BY campaign_name ORDER BY first_day DESC NULLS LAST, campaign_name DESC",
        (artist_id, *acct_p))


def campaign_window(start: _dt.date, end: _dt.date) -> PeriodWindow:
    """The window of THE chosen campaign(s) — not a generic period.

    A preset ending today drew a 31-day campaign on a 662-day axis (measured 2026-09-21
    on « O chiotte l'arbitre Tucome Back ») and divided 31 days of spend by 646 days of
    streams. The default is the tail: what remains when the campaign stops is the point.
    """
    choix = {
        "tail": t("meta_x_spotify.win_tail", "📈 Campagne + {n} j (rémanence)").format(n=TAIL_DAYS),
        "camp": t("meta_x_spotify.win_camp", "🎯 La campagne seule"),
        "all": t("meta_x_spotify.win_all", "♾️ Jusqu'à aujourd'hui"),
    }
    key = st.segmented_control(
        t("meta_x_spotify.window", "Fenêtre"), list(choix), key=WINDOW_KEY,
        format_func=lambda k: choix[k], default="tail") or "tail"
    end = {"camp": end, "all": _dt.date.today()}.get(key, end + _dt.timedelta(days=TAIL_DAYS))
    return PeriodWindow(start, end, choix[key], f"campaign_{key}", False)


def _greyed_period() -> None:
    st.selectbox(t("meta_filter_bar.period", "Période"),
                 [t("meta_filter_bar.all_time", "Toute la période")],
                 disabled=True, key="meta_period_off")
    st.caption(t("meta_filter_bar.no_date",
                 "Meta ne date pas ces ventilations : elles couvrent toute la période."))


def _period(db, artist_id: int, spans: pd.DataFrame, scope: tuple[str, ...],
            section: str) -> PeriodWindow | None:
    if section == "breakdowns":
        _greyed_period()
        return None
    rows = spans[spans["campaign_name"].isin(scope)] if scope else spans
    if scope and not rows.empty:
        start, end = pd.to_datetime(rows["first_day"]).min(), pd.to_datetime(rows["last_day"]).max()
        win = campaign_window(start.date(), end.date())
        st.caption(t("meta_filter_bar.window_caption", "Campagne du {a} au {b}.")
                   .format(a=format_date(start.date()), b=format_date(end.date())))
        return win
    launch = pd.to_datetime(spans["first_day"]).min() if not spans.empty else None
    return filters.period(db, table="v_meta_campaign_daily", date_column="day",
                          artist_id=artist_id, key=PERIOD_KEY,
                          latest_release=None if pd.isna(launch) else launch.date())


def filter_bar(db, artist_id: int, section: str) -> MetaFilters:
    """Draw the bar once and return what every section reads."""
    # One ad account draws no account widget: its column would sit empty on the left.
    if len(tenant_ad_accounts(db, artist_id)) > 1:
        c_acct, c_camp, c_period = st.columns([1, 2, 2])
        with c_acct:
            account = account_scope(db, artist_id, key=ACCOUNT_KEY)
    else:
        (c_camp, c_period), account = st.columns(2), None
    spans = _campaign_spans(db, artist_id, account)
    names = tuple(spans["campaign_name"].tolist())
    with c_camp:
        # Opens on the latest campaign: the funnel tells ONE campaign's story, and the
        # performance section opened on it before R399.
        picked = st.selectbox(
            t("meta_filter_bar.campaign", "Campagne"), [ALL, *names], index=1 if names else 0,
            key=CAMPAIGN_KEY,
            format_func=lambda c: t("meta_filter_bar.all_campaigns", "Toutes") if c == ALL else c)
        campaign = picked if picked in names else None
        second = (second_campaign(list(names), campaign, key=SECOND_KEY)
                  if campaign and section != "funnel" else None)
    scope = tuple(c for c in (campaign, second) if c)
    with c_period:
        window = _period(db, artist_id, spans, scope, section)
    return MetaFilters(account, names, campaign, second, window)


def say_instagram_is_outside() -> None:
    st.caption(t("meta_filter_bar.instagram_outside",
                 "📸 Instagram organique : ni compte publicitaire ni campagne ne s'y "
                 "appliquent — chaque graphique garde sa propre période."))

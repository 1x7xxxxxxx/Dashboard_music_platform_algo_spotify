"""Did the last Meta campaign lift the artist's daily Spotify listeners? — the verdict, pure.

Type: Utility
Uses: pandas
Depends on: nothing (the caller reads v_s4a_audience_daily and v_meta_daily)
Persists in: nothing

R187 (2026-09-26), asked by the owner: the « auditeurs-jour » figure answered no decision;
replace it with something that says what a Meta campaign did. The number an artist reads as a
verdict must not lie, so it is refused — « non concluant », with the reason — whenever the data
cannot support it (code-critic, same day):

- `listeners` in S4A is UNIQUE LISTENERS PER DAY. Averaging days and multiplying by days gives
  LISTENER-DAYS, not people: the gain is named « auditeurs-jour », never « auditeurs ».
- the campaign must be OVER (a running one compares a partial lift to a partial spend);
- the 28 days before it need ≥ 14 MEASURED days (S4A arrives by episodic CSV imports — a mean
  over gaps is a mean over nothing), and the campaign ≥ 7 measured days;
- no OTHER campaign (any ad account) may spend in the baseline or the campaign window — two
  campaigns cannot be told apart;
- a lift smaller than the baseline's own day-to-day standard deviation is NOT a lift.
Only then: « +N auditeurs-jour par jour, ≈ X € par auditeur-jour gagné ».
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

BASELINE_DAYS = 28
MIN_BASELINE_MEASURED = 14
MIN_CAMPAIGN_MEASURED = 7
ENDED_AFTER_DAYS = 2          # no spend for 2 days ⇒ the campaign is over


@dataclass(frozen=True)
class Campaign:
    account: str
    name: str
    start: dt.date
    end: dt.date
    spend: float


@dataclass(frozen=True)
class Verdict:
    conclusive: bool
    text: str
    lift_per_day: float | None = None
    eur_per_listener_day: float | None = None


def campaigns(spend: pd.DataFrame) -> list[Campaign]:
    """One Campaign per (ad account, campaign name) with spend > 0, oldest first. Pure.

    `spend` columns: ad_account_id, campaign_name, day, spend."""
    if spend.empty:
        return []
    live = spend[spend["spend"].fillna(0) > 0]
    out = []
    for (acct, name), g in live.groupby(["ad_account_id", "campaign_name"], dropna=False):
        days = pd.to_datetime(g["day"]).dt.date
        out.append(Campaign(str(acct), str(name), min(days), max(days),
                            float(g["spend"].sum())))
    return sorted(out, key=lambda c: (c.end, c.start))


def verdict(listeners: pd.Series, camps: list[Campaign], today: dt.date) -> Verdict:
    """The verdict on the LAST campaign. `listeners`: daily unique listeners indexed by date,
    MEASURED days only (a missing day is absent, never 0). Pure."""
    if not camps:
        return Verdict(False, "Aucune campagne Meta avec dépense : rien à juger.")
    return verdict_for(camps[-1], camps, listeners, today)


#: The words of a lift, per series: listeners-per-day are LISTENER-DAYS (see module doc).
LISTENERS = ("auditeurs-jour", "auditeur-jour")
STREAMS = ("écoutes", "écoute")


def verdict_for(c: Campaign, camps: list[Campaign], series: pd.Series, today: dt.date,
                unit: tuple[str, str] = LISTENERS) -> Verdict:
    """The verdict on campaign `c` among ALL `camps` — the same refusals for every campaign
    (R291: the per-campaign « écoutes gagnées » of the Meta page reuse them, code-critic).
    `series`: a daily measure indexed by date, MEASURED days only. Pure."""
    many, one = unit
    if (today - c.end).days < ENDED_AFTER_DAYS:
        return Verdict(False, f"« {c.name} » tourne encore : le verdict viendra à la fin.")
    base_start = c.start - dt.timedelta(days=BASELINE_DAYS)
    others = [o for o in camps if o is not c and o.end >= base_start and o.start <= c.end]
    if others:
        return Verdict(False, f"Non concluant : « {others[-1].name} » dépensait aussi pendant "
                              f"« {c.name} » ou juste avant — impossible de les séparer.")
    idx = pd.to_datetime(pd.Series(series.index)).dt.date
    s = pd.Series(series.values, index=idx).dropna()
    base = s[(s.index >= base_start) & (s.index < c.start)]
    during = s[(s.index >= c.start) & (s.index <= c.end)]
    if len(during) < MIN_CAMPAIGN_MEASURED:
        return Verdict(False, f"Non concluant : {len(during)} jour(s) d'écoute mesuré(s) pendant "
                              f"« {c.name} » — importe le CSV Spotify for Artists de cette période.")
    if len(base) < MIN_BASELINE_MEASURED:
        return Verdict(False, f"Non concluant : {len(base)} jour(s) mesuré(s) dans les "
                              f"{BASELINE_DAYS} jours avant « {c.name} » (il en faut "
                              f"{MIN_BASELINE_MEASURED}).")
    lift = float(during.mean() - base.mean())
    noise = float(base.std(ddof=1)) if len(base) > 1 else 0.0
    if lift <= noise:
        return Verdict(True, f"« {c.name} » n'a pas soulevé tes {many} au-delà de leur "
                             f"variation normale (±{noise:.0f}/jour).", lift_per_day=lift)
    gained = lift * len(during)
    eur = c.spend / gained if gained > 0 else None
    return Verdict(True, f"« {c.name} » : +{lift:.0f} {many} par jour, "
                         f"≈ {eur:.2f} € par {one} gagné{'e' if unit == STREAMS else ''}.",
                   lift_per_day=lift, eur_per_listener_day=eur)


def waves(camps: list[Campaign]) -> list[tuple[Campaign, list[str]]]:
    """Campaigns that overlap — or follow within the 28-day baseline — merged into ONE wave,
    with the names it groups. Pure.

    R291 (measured 2026-09-28, artist 1): judged one by one, 21 of 21 campaigns were
    « non concluant », almost all because another campaign spent at the same time. Two
    campaigns that cannot be told apart CAN be judged together: a wave is the unit the data
    can answer for, and the verdict's own overlap rule decides what goes in it — so no wave
    can overlap another's window."""
    out: list[tuple[Campaign, list[str]]] = []
    for c in sorted(camps, key=lambda c: c.start):
        if out and c.start <= out[-1][0].end + dt.timedelta(days=BASELINE_DAYS):
            w, names = out[-1]
            out[-1] = (Campaign(w.account, w.name, w.start, max(w.end, c.end),
                                w.spend + c.spend), [*names, c.name])
        else:
            out.append((c, [c.name]))
    return out

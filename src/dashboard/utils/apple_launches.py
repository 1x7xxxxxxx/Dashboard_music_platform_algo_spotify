"""Shazams of two releases, aligned on J0 — pure functions for the Apple Music page.

Type: Utility
Uses: pandas, src.utils.track_matching.normalize_track_title
Depends on: nothing (the caller reads track_release_reference via `get_release_dates`
            and the readings via `platform_timeseries.apple_launch_readings`)
Triggers: views/apple_music.py (section « ⚡ Shazams depuis la sortie »)
Persists in: nothing

R351 (owner's screen review, 2026-10-04): « l'évolution des Shazam entre deux campagnes —
la dernière sortie par défaut, une seconde au choix », both on the same clock so they compare.

WHAT A « CAMPAIGN » IS HERE, AND WHY NOT A META CAMPAIGN
---------------------------------------------------------
J0 is a RELEASE DATE (`track_release_reference`, the same source the page already uses
to preselect « la dernière sortie »). A Meta campaign was the other candidate (its window
is `meta_impact.campaigns()`), and it is refused for a measured reason: a Meta J0 needs
the Shazam level ON its start day, and Apple readings are dropped by hand — for artist 1
the first Apple reading is 2025-11-29, fourteen months after the last Meta spend day
(2024-09-30). No Meta campaign is bracketed by a reading, so every series would be empty.
A release needs no starting reading: a title has no Shazam before it exists, so J0 = 0 is
true by construction.

THE GRAIN — CUMULATIVE, AND SAID SO
-----------------------------------
Apple gives a CUMULATIVE count per reading, not a daily one (`v_apple_song_cumulative`).
For a release, the lifetime cumulative at J+k IS « Shazams since J0 » — no differencing
is needed, and none is done. Only readings whose export covers the title's whole life
qualify: no period (`period_start` NULL — a « depuis le début » export) or a period
starting on or before J0. An export of « 2025 only » for a 2024 title would understate
it and is dropped. The figure is never relabelled « per day »: readings are 12 to 179
days apart, and a slope between two of them is an average nobody measured.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from src.utils.track_matching import normalize_track_title


@dataclass(frozen=True)
class Launch:
    """One release — the « campaign » of R351: an Apple title and its J0."""
    song: str
    j0: dt.date


def release_launches(songs, release_by_key: dict) -> list[Launch]:
    """One Launch per Apple title that has a release date, NEWEST FIRST. Pure.

    `songs`: Apple `song_name`s; `release_by_key`: `get_release_dates()` →
    {match_key: date}. The title → key mapping is `normalize_track_title`, the same
    one the page used for its default (it lived inline in `show()` until R351)."""
    out = []
    for song in dict.fromkeys(songs or []):
        rd = release_by_key.get(normalize_track_title(song))
        if rd is not None:
            out.append(Launch(str(song), pd.Timestamp(rd).date()))
    return sorted(out, key=lambda x: (x.j0, x.song), reverse=True)


def align_on_j0(readings: pd.DataFrame, launches: list[Launch]) -> pd.DataFrame:
    """Shazams since J0, one series per launch, on a common « days since J0 » axis. Pure.

    `readings`: song_name, day, shazam_count (cumulative), period_start (NaN/None =
    the export covers the title's whole life). Returns columns
    `song, j0, offset, shazams, measured`: every series starts with
    (offset 0, 0 Shazam, measured=False) — the release anchor — then its qualifying
    readings with offset ≥ 0, ascending. Readings before J0 are dropped (they would
    belong to a title that did not exist)."""
    cols = ["song", "j0", "offset", "shazams", "measured"]
    rows = []
    r = readings if readings is not None else pd.DataFrame()
    if not r.empty:
        r = r.assign(day=pd.to_datetime(r["day"]).dt.date,
                     shazam_count=pd.to_numeric(r["shazam_count"], errors="coerce"))
        start = (pd.to_datetime(r["period_start"]).dt.date
                 if "period_start" in r else pd.Series([None] * len(r), index=r.index))
        r = r.assign(period_start=start)
    for launch in launches:
        rows.append({"song": launch.song, "j0": launch.j0, "offset": 0,
                     "shazams": 0.0, "measured": False})
        if r.empty:
            continue
        mine = r[(r["song_name"] == launch.song) & r["shazam_count"].notna()]
        covers = mine["period_start"].map(lambda s: s is None or pd.isna(s) or s <= launch.j0)
        mine = mine[covers & (mine["day"] >= launch.j0)]
        mine = mine.sort_values("day").drop_duplicates("day", keep="last")
        for d, n in zip(mine["day"], mine["shazam_count"]):
            rows.append({"song": launch.song, "j0": launch.j0,
                         "offset": (d - launch.j0).days, "shazams": float(n),
                         "measured": True})
    out = pd.DataFrame(rows, columns=cols)
    # The anchor and a reading ON J0 share offset 0: the measure wins over the anchor.
    out = out.sort_values(["song", "offset", "measured"]) \
             .drop_duplicates(["song", "offset"], keep="last")
    order = {lc.song: i for i, lc in enumerate(launches)}
    return out.assign(_o=out["song"].map(order)) \
              .sort_values(["_o", "offset"]).drop(columns="_o").reset_index(drop=True)

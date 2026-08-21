"""Coerce a partial date returned by an external API into a real DATE value.

Type: Utility
Uses: nothing (stdlib)
Triggers: src/collectors/spotify_api.py
Persists in: nothing (pure)

Spotify returns `album.release_date` with a precision it declares separately in
`album.release_date_precision`: "2013", "2013-05" or "2013-05-21". The `tracks.
release_date` column is DATE, so the first two forms make the INSERT fail with
`invalid input syntax for type date: "2013"` -- and because the write is batched
per artist, that ONE album costs the artist every top track of the run.

Measured 2026-08-21 by the canary tenant on its first real collection. It had never
fired before because the admin's own catalogue happens to carry full dates only --
a defect only a second tenant could reveal.

The trade-off, stated rather than hidden: padding "2013" to 2013-01-01 fabricates a
precision the source did not give, and up to 364 days of error land in any recency or
lifecycle feature computed from this column. The alternative -- storing NULL -- is
honest but drops the album out of every date-based analysis entirely. Padding is the
lesser loss for a catalogue where release YEAR is the signal that matters, and it is
what the CSV path already does implicitly via `pandas.to_datetime`. Keeping the two
paths consistent is worth more than the fabricated days.
"""

from __future__ import annotations

import datetime as _dt

_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y")


def coerce_api_date(value: object) -> _dt.date | None:
    """Return a date for a full, month- or year-precision string; None if unusable.

    Padding is to the FIRST day of the declared period, never to today: an unknown
    day must not read as "released this month".
    """
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    text = str(value).strip()
    for fmt in _FORMATS:
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None

"""Read a `timestamptz` column into pandas without tripping over daylight saving.

Type: Utility
Uses: pandas
Triggers: nothing
Depends on: nothing
Persists in: nothing

The defect
----------
`pd.to_datetime(series)` raises when the values carry **different UTC offsets**:

    ValueError: Tz-aware datetime.datetime cannot be converted to datetime64
                unless utc=True, at position 2

That is not an exotic case here. Every `timestamptz` column read through psycopg2
comes back as datetimes bearing the offset in force *at that instant*, so a table
holding rows from March and June holds `+01:00` and `+02:00` side by side. Measured
on production `saas_users.created_at` on 2026-08-30:

    id 1  2026-03-25 21:36:50+01     <- winter
    id 2  2026-03-25 21:55:22+01
    id 10 2026-06-14 14:38:27+02     <- "position 2", where it raised

`src/dashboard/views/admin.py` crashed on exactly this, in production, on the user
list. Four more sites had the same shape and had simply not been asked for a window
spanning a DST change yet — the trigger is a date on the calendar, not a code path.

Why not just pass `utc=True` at each call site
----------------------------------------------
Because `utc=True` alone silently changes what the reader sees: a timestamp rendered
in UTC instead of Paris shifts by one or two hours, and near midnight that moves the
DATE. The fix has to normalise AND convert back, which is two steps nobody will
remember at the fifth call site. So it lives here, once.
"""
from __future__ import annotations

import pandas as pd

# The timezone the product is read in. Timestamps are stored as instants
# (`timestamptz`); this is only about how they are shown.
DISPLAY_TZ = "Europe/Paris"


def to_local_datetime(values, tz: str = DISPLAY_TZ) -> pd.Series:
    """Parse `values` to tz-aware datetimes in `tz`, whatever offsets they carry.

    `utc=True` is what makes mixed offsets legal; the `tz_convert` that follows is
    what keeps the rendered value identical to what it was before this function
    existed. Naive input is treated as already being in `tz`.
    """
    out = pd.to_datetime(values, utc=True)
    if isinstance(out, pd.Series):
        return out.dt.tz_convert(tz)
    return out.tz_convert(tz)


def to_local_naive(values, tz: str = DISPLAY_TZ) -> pd.Series:
    """Same, then drop the tzinfo — for plotting and `.dt.date`.

    Matplotlib/Plotly axes and `.dt.date` want a wall clock, not an instant. Dropping
    the offset AFTER converting is the only order that yields the local wall clock;
    dropping it before would leave whichever offset the row happened to carry.
    """
    out = to_local_datetime(values, tz)
    if isinstance(out, pd.Series):
        return out.dt.tz_localize(None)
    return out.tz_localize(None)

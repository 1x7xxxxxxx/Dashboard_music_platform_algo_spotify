"""R505 — what a dedup, a bucket or a cover keeps: totals, uniqueness, no double count.

Type: Feature
Uses: hypothesis, src/transformers/distrokid_parser.py,
      src/dashboard/utils/{platform_chart,platform_timeseries}.py, src/utils/track_matching.py
Depends on: nothing — pure functions, no DB, no Streamlit

Each function below sums, groups or chooses — the three gestures where a figure is
silently counted twice or lost. An example covers the case imagined; these state what
must hold for every input of the shape.
"""
import datetime as dt

from hypothesis import given, settings
from hypothesis import strategies as st

from src.dashboard.utils.platform_chart import _aggregate, _bucket_days, _bucket_key
from src.dashboard.utils.platform_timeseries import non_overlapping_cover
from src.transformers.distrokid_parser import CONFLICT_KEYS, DistroKidParser
from src.utils.track_matching import track_title_matches

_DETERMINISTIC = settings(derandomize=True, database=None, deadline=None,
                          max_examples=300)
_DAYS = st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 12, 31))
_STEPS = st.sampled_from(["day", "week", "month", "year"])

_MONEY = ("quantity", "earnings_usd", "songwriter_royalties_usd", "recoup_usd")
_SALE = st.fixed_dictionaries({
    **{k: st.sampled_from(["a", "b"]) for k in CONFLICT_KEYS},
    "quantity": st.integers(0, 10**6),
    **{k: st.integers(0, 10**6) for k in _MONEY[1:]},
})


@_DETERMINISTIC
@given(st.lists(_SALE, max_size=30))
def test_a_distrokid_dedup_keeps_every_total_under_unique_keys(rows):
    before = {k: sum(r[k] for r in rows) for k in _MONEY}
    snapshot = [dict(r) for r in rows]
    out = DistroKidParser._dedup(rows)
    assert {k: sum(r[k] for r in out) for k in _MONEY} == before
    keys = [tuple(r[k] for k in CONFLICT_KEYS) for r in out]
    assert len(keys) == len(set(keys))
    assert rows == snapshot, "the dedup must not mutate the rows it was given"


@_DETERMINISTIC
@given(day=_DAYS, step=_STEPS)
def test_a_day_falls_in_exactly_the_bucket_its_key_names(day, step):
    key = _bucket_key(day, step)
    assert key <= day and _bucket_key(key, step) == key
    assert _bucket_days(key, step, day, day) == 1


@_DETERMINISTIC
@given(start=_DAYS, n=st.integers(1, 800), step=_STEPS,
       values=st.lists(st.integers(0, 10**5), min_size=800, max_size=800))
def test_a_fully_measured_series_keeps_its_total_in_any_step(start, n, step, values):
    rows = [(start + dt.timedelta(days=i), values[i]) for i in range(n)]
    out = _aggregate({"s": rows}, step)["s"]
    assert sum(v for _, v in out) == sum(v for _, v in rows)


_READING = st.tuples(_DAYS, st.integers(0, 400), st.integers(0, 10**6)).map(
    lambda t: (t[0], t[0] + dt.timedelta(days=t[1]), t[2]))


@_DETERMINISTIC
@given(st.lists(_READING, max_size=12))
def test_a_cover_never_counts_a_day_twice_and_drops_only_an_overlap(readings):
    kept = non_overlapping_cover(readings)
    for i, (s1, e1, _) in enumerate(kept):
        for s2, e2, _ in kept[i + 1:]:
            assert e1 < s2 or e2 < s1
    for r in readings:
        assert r in kept or any(r[0] <= e and s <= r[1] for s, e, _ in kept)


_TITLE = st.text(alphabet="abcdefgh -()", min_size=1, max_size=24)
_TAG = st.sampled_from(["", " (Remix)", " - Remix", " (Live)", " - Radio Edit"])


@_DETERMINISTIC
@given(a=_TITLE, b=_TITLE, ta=_TAG, tb=_TAG)
def test_a_title_match_does_not_depend_on_which_side_asks(a, b, ta, tb):
    assert track_title_matches(a + ta, b + tb) == track_title_matches(b + tb, a + ta)


@_DETERMINISTIC
@given(st.text(alphabet="abcdefgh ", min_size=1, max_size=20).filter(str.strip))
def test_a_dash_remix_is_the_parenthesised_remix(title):
    assert track_title_matches(f"{title} - Remix", f"{title} (Remix)")

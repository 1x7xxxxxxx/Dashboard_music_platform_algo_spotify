"""Cross-platform track-link suggestion engine (pure, unit-testable, no Streamlit/DB).

Type: Utility
Uses: src.utils.track_matching.normalize_track_title (normalization — never re-done here)
Depends on: nothing at import time (pure functions)
Persists in: nothing

Scores a platform-local title (or a Meta campaign name) against the canonical tracks
held in track_release_reference (keyed by match_key). track_matching gives the boolean
matcher + normalization; this module adds a *continuous* ranking score on top so the
mapping view can auto-suggest + sort + threshold. Confidences live in [0, 1] so the
bulk-accept threshold (e.g. 0.80) is interpretable. All functions fail soft.
"""
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher

from src.utils.track_matching import normalize_track_title

# Weights / decay — tune here only.
W_CAMP_TITLE = 0.65          # campaign score: title vs date split (sums to 1.0)
W_CAMP_DATE = 0.35
DATE_HALFLIFE_DAYS = 14      # campaign-vs-release proximity half-life
W_TRACK_TITLE = 0.7          # cross-platform track score: title vs date split (sums to 1.0)
W_TRACK_DATE = 0.3
TRACK_DATE_HALFLIFE_DAYS = 30  # platform-upload vs release proximity (looser than a campaign)
CONTAINMENT_SCORE = 0.9      # one base-title token-set ⊆ the other (artist prefix / suffix noise)


@dataclass(frozen=True)
class Candidate:
    match_key: str
    title: str
    score: float          # 0..1
    method: str           # 'exact' | 'title_sim' | 'date_proximity'


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def title_similarity(a: str, b: str) -> float:
    """0..1 similarity of two raw titles. Exact normalized equality → 1.0. Returns
    0.0 when remix-status disagrees (a base title must never outrank its own remix)."""
    na, nb = normalize_track_title(a), normalize_track_title(b)
    if not na or not nb:
        return 0.0
    ta, tb = na.split(), nb.split()
    if ('remix' in ta) != ('remix' in tb):      # remix is a distinct release
        return 0.0
    if na == nb:
        return 1.0
    sa, sb = set(ta), set(tb)
    ba, bb = sa - {'remix'}, sb - {'remix'}
    if ba and bb and (ba <= bb or bb <= ba):     # containment absorbs prefixes/suffixes
        return CONTAINMENT_SCORE
    seq = SequenceMatcher(None, na, nb).ratio()
    jac = len(sa & sb) / len(sa | sb)
    return round(0.5 * seq + 0.5 * jac, 4)


def date_proximity(campaign_start, release_date, half_life: float = DATE_HALFLIFE_DAYS) -> float:
    """0..1 exp-decay on |days| between two dates (default half-life 14d for campaigns;
    pass TRACK_DATE_HALFLIFE_DAYS for cross-platform track timing).
    Same day → 1.0; missing either date → 0.0."""
    cs, rd = _as_date(campaign_start), _as_date(release_date)
    if cs is None or rd is None:
        return 0.0
    days = abs((cs - rd).days)
    return round(0.5 ** (days / half_life), 4)


def mapping_boost(match_key: str, confirmed_keys) -> float:
    """1.0 if this canonical track already has confirmed links elsewhere (tie-breaker)."""
    return 1.0 if match_key in (confirmed_keys or ()) else 0.0


def confidence_badge(score: float) -> str:
    """Per-row reliability marker matching the legend: 🟢 ≥80 % · 🟡 50–80 % · 🔴 <50 %.
    Low scores (junk titles like DJ sets / other artists) are flagged 🔴, not hidden."""
    s = score or 0.0
    return "🟢" if s >= 0.8 else "🟡" if s >= 0.5 else "🔴"


def rank_track_candidates(platform_title, canonical_tracks, confirmed_keys=None,
                          top_n: int = 3, platform_date=None):
    """Rank canonical tracks for one platform-local title. Score = title similarity,
    optionally combined with release-date proximity when the platform exposes an upload
    date (Spotify/SoundCloud/YouTube): score = 0.7·title + 0.3·date. Title-only at FULL
    scale when no platform_date (Apple / S4A) — never capped at 0.7. The date term breaks
    remix-vs-original ties (same base title, different release dates) and sinks junk titles
    (DJ sets) whose upload date is far. mapping_boost only breaks remaining ties.
    canonical_tracks: [{match_key, title, release_date, ...}]."""
    confirmed_keys = confirmed_keys or set()
    scored = []
    for t in canonical_tracks:
        sim = title_similarity(platform_title, t['title'])
        if sim <= 0:
            continue
        if platform_date is not None and t.get('release_date'):
            prox = date_proximity(platform_date, t['release_date'], TRACK_DATE_HALFLIFE_DAYS)
            score = round(W_TRACK_TITLE * sim + W_TRACK_DATE * prox, 4)
            method = 'exact' if sim >= 1.0 else 'title+date'
        else:
            score = round(sim, 4)
            method = 'exact' if sim >= 1.0 else 'title_sim'
        scored.append((score, mapping_boost(t['match_key'], confirmed_keys),
                       Candidate(t['match_key'], t['title'], score, method)))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [c for _, _, c in scored[:top_n]]


def rank_campaign_candidates(campaign_name, campaign_start, canonical_tracks,
                             confirmed_keys=None, top_n: int = 3):
    """Rank canonical tracks for a Meta campaign: score = title·0.65 + date·0.35
    (campaigns often name the track AND launch near its release). boost breaks ties."""
    confirmed_keys = confirmed_keys or set()
    scored = []
    for t in canonical_tracks:
        sim = title_similarity(campaign_name, t['title'])
        prox = date_proximity(campaign_start, t.get('release_date'))
        score = round(W_CAMP_TITLE * sim + W_CAMP_DATE * prox, 4)
        if score <= 0:
            continue
        if sim >= 1.0:
            method = 'exact'
        elif W_CAMP_DATE * prox > W_CAMP_TITLE * sim:
            method = 'date_proximity'
        else:
            method = 'title_sim'
        scored.append((score, mapping_boost(t['match_key'], confirmed_keys),
                       Candidate(t['match_key'], t['title'], score, method)))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [c for _, _, c in scored[:top_n]]

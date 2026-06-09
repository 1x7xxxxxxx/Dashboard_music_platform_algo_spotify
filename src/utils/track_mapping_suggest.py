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


def date_proximity(campaign_start, release_date) -> float:
    """0..1 exp-decay on |days| between a campaign start and a release (half-life 14d).
    Same day → 1.0; missing either date → 0.0."""
    cs, rd = _as_date(campaign_start), _as_date(release_date)
    if cs is None or rd is None:
        return 0.0
    days = abs((cs - rd).days)
    return round(0.5 ** (days / DATE_HALFLIFE_DAYS), 4)


def mapping_boost(match_key: str, confirmed_keys) -> float:
    """1.0 if this canonical track already has confirmed links elsewhere (tie-breaker)."""
    return 1.0 if match_key in (confirmed_keys or ()) else 0.0


def rank_track_candidates(platform_title, canonical_tracks, confirmed_keys=None,
                          top_n: int = 3):
    """Rank canonical tracks for one platform-local title. Confidence = title similarity;
    mapping_boost only breaks ties. canonical_tracks: [{match_key, title, ...}]."""
    confirmed_keys = confirmed_keys or set()
    scored = []
    for t in canonical_tracks:
        sim = title_similarity(platform_title, t['title'])
        if sim <= 0:
            continue
        method = 'exact' if sim >= 1.0 else 'title_sim'
        scored.append((sim, mapping_boost(t['match_key'], confirmed_keys),
                       Candidate(t['match_key'], t['title'], round(sim, 4), method)))
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

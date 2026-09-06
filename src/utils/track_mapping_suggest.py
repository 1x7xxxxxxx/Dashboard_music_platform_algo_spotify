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

from src.utils.track_matching import split_version

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


# Les jetons qui ne disent rien du morceau. Retirés AVANT de mesurer l'inclusion :
# ce sont eux, et non le titre, qui font la longueur des libellés SoundCloud.
_NOISE_TOKENS = frozenset({
    'free', 'download', 'downloads', 'dl', 'feat', 'ft', 'featuring', 'prod',
    'official', 'audio', 'video', 'lyrics', 'lyric', 'hd', 'hq', 'out', 'now',
})


def _content_tokens(base: str, noise=()) -> set:
    """Les jetons de `base` qui portent du sens, hors bruit connu et nom d'artiste."""
    drop = _NOISE_TOKENS | {n for n in noise if n}
    return {tok for tok in base.split() if tok and tok not in drop}


def title_similarity(a: str, b: str, noise_tokens=()) -> float:
    """0..1 similarity of two raw titles. Exact normalized equality → 1.0.

    Rend 0.0 dès que les MARQUEURS DE VERSION divergent : un radio edit, un live et
    un instrumental sont trois sorties distinctes, avec trois dates, et une base ne
    doit jamais l'emporter sur sa propre version.

    L'INCLUSION EST PONDÉRÉE PAR CE QU'ELLE LAISSE DE CÔTÉ. Elle rendait un 0,90
    plat dès qu'un jeu de jetons était inclus dans l'autre, sans regarder ce qui
    restait — mesuré le 2026-09-06 : « Mix » ⊆ « house music mix 3 back to old
    school » valait 0,90, soit au-dessus du seuil d'auto-acceptation de 0,80. Tant
    que les titres sont longs et distinctifs, c'est sans conséquence ; un artiste
    dont un morceau s'appelle « Solo » ou « Nuit » verrait un mix DJ s'y associer
    tout seul.

    La couverture est la part des jetons de CONTENU du titre le plus long qui sont
    expliqués par le plus court. Le bruit (« free download », « feat », le nom de
    l'artiste passé en `noise_tokens`) est retiré des deux côtés d'abord : sans quoi
    un libellé SoundCloud serait pénalisé pour du texte qui ne dit rien du morceau.
    """
    ba, ta = split_version(a)
    bb, tb = split_version(b)
    if not ba or not bb:
        return 0.0
    if ta != tb:                                 # versions distinctes
        return 0.0
    if ba == bb:
        return 1.0

    noise = {str(n).lower() for n in (noise_tokens or ())}
    ca, cb = _content_tokens(ba, noise), _content_tokens(bb, noise)
    if not ca or not cb:
        return 0.0
    if ca == cb:                                 # égaux une fois le bruit retiré
        return 1.0
    if ca <= cb or cb <= ca:
        short, long_ = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
        coverage = len(short) / len(long_)
        return round(CONTAINMENT_SCORE * coverage, 4)

    seq = SequenceMatcher(None, ba, bb).ratio()
    jac = len(ca & cb) / len(ca | cb)
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


def artist_noise_tokens(artist_name: str) -> frozenset:
    """Les jetons du NOM D'ARTISTE, à ignorer quand on compare deux titres.

    SoundCloud et YouTube préfixent le nom de l'artiste au titre
    (« 1x7xxxxxxx - Kimono À Semelle De Fer »). Sans cette liste, ce nom compte
    comme un mot du titre : le filet de rapprochements réels l'a mesuré le
    2026-09-06 — la couverture tombait à 5/6, soit 0,75, sous le seuil de 0,80, et
    un rapprochement qui marchait en production cessait de s'appliquer tout seul.
    """
    from src.utils.track_matching import split_version
    base, _tags = split_version(artist_name or '')
    return frozenset(base.split())


def rank_track_candidates(platform_title, canonical_tracks, confirmed_keys=None,
                          top_n: int = 3, platform_date=None, noise_tokens=()):
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
        sim = title_similarity(platform_title, t['title'], noise_tokens)
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
                             confirmed_keys=None, top_n: int = 3, noise_tokens=()):
    """Rank canonical tracks for a Meta campaign: score = title·0.65 + date·0.35
    (campaigns often name the track AND launch near its release). boost breaks ties."""
    confirmed_keys = confirmed_keys or set()
    scored = []
    for t in canonical_tracks:
        sim = title_similarity(campaign_name, t['title'], noise_tokens)
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

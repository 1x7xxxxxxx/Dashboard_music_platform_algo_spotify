"""Per-artist onboarding readiness — the closed-loop check that a tenant is wired AND collecting.

Type: Utility
Uses: freshness_monitor.check_freshness (per-tenant data recency), artist_credentials (identity)
Depends on: artist_credentials, saas_artists.spotify_artist_id
Persists in: nothing

Answers, per artist × platform: does the artist have the IDENTITY we need, and is data actually
LANDING? Converts the silent per-tenant gaps the Benken week exposed (connected-but-0-rows,
account-not-shared, empty channel) into a visible status + the exact next action. Surfaced by
the admin onboarding-health view, the home tracker, and alert_monitor. The pure status logic
(`platform_status`, `next_action`) is unit-tested; `artist_readiness` wires it to the DB.
"""
# status values, worst → best. QUIET sits next to OK on purpose: it is not a
# degraded state, it is the correct state of a source that has nothing to send.
TODO, NO_DATA, STALE, QUIET, OK = "todo", "no_data", "stale", "quiet", "ok"

# Worst → best. Used to pick the best answer when several sources can prove the
# same platform; the order is the one the module docstring already documents.
_RANK = {TODO: 0, NO_DATA: 1, STALE: 2, QUIET: 3, OK: 4}

_ICON = {TODO: "⚪", NO_DATA: "🔴", STALE: "🟡", QUIET: "⏸️", OK: "🟢"}
_LABEL = {
    TODO: "À connecter",
    NO_DATA: "Connecté — aucune donnée",
    STALE: "Données anciennes",
    QUIET: "Silence normal — rien à collecter",
    OK: "OK",
}

# platform → presentation only: label, and the hints. Which freshness sources prove a
# platform is collecting lives in `freshness_monitor.SOURCES_FOR_PLATFORM` — restating
# it here is what let readiness judge Spotify on the CSV table while three other
# surfaces judged it on three other tables.
_PLATFORMS = (
    {"key": "soundcloud", "label": "☁️ SoundCloud",
     "id_hint": "ton User ID SoundCloud numérique",
     "nodata_hint": "vérifie le User ID ; l'app SoundCloud partagée doit être configurée (admin)"},
    {"key": "spotify", "label": "🎵 Spotify",
     "id_hint": "l'URL de ta page Spotify Artist",
     "nodata_hint": "importe ton CSV Spotify for Artists, ou vérifie l'ID artiste"},
    {"key": "youtube", "label": "🎬 YouTube",
     "id_hint": "ton Channel ID (UC…)",
     "nodata_hint": "ta chaîne n'a peut-être aucune vidéo publique (cherche ta chaîne « … - Topic »)"},
    {"key": "meta", "label": "📱 Meta Ads",
     "id_hint": "ton Ad Account ID",
     "nodata_hint": "partage ton compte publicitaire avec le Business Manager admin (asset sharing)"},
    {"key": "instagram", "label": "📸 Instagram",
     "id_hint": "ton Instagram Business Account ID",
     "nodata_hint": "partage ton compte Instagram/Page avec le Business Manager admin"},
)


def platform_status(identity_present: bool, last_dt, stale: bool,
                    expected_silence: str | None = None) -> str:
    """Pure: identity + data-recency → one of TODO/NO_DATA/STALE/QUIET/OK.

    `expected_silence` is a MEASURED reason why this source has nothing to send
    (freshness_monitor sets it, e.g. an ad account with no ACTIVE campaign). It
    outranks the row count: a tenant whose campaigns are all paused is not
    "connected with no data", and telling them to share their ad account again is
    a wrong instruction. It never outranks a missing identity — that is still the
    tenant's move, and the probe that produces a reason cannot even run without it.
    """
    if not identity_present:
        return TODO
    if expected_silence:
        return QUIET
    if last_dt is None:
        return NO_DATA
    return STALE if stale else OK


def next_action(platform: dict, status: str, expected_silence: str | None = None) -> str:
    """Pure: the exact next step for an (platform, status)."""
    if status == OK:
        return ""
    if status == QUIET:
        # The reason travels with the status. A quiet light with nothing behind it
        # is read as a bug the next time someone looks at it — which is how a
        # suppressed alert becomes worse than the noisy one it replaced.
        return f"Rien à faire — {expected_silence}" if expected_silence else "Rien à faire."
    if status == TODO:
        return f"Renseigne {platform['id_hint']}."
    if status == NO_DATA:
        return platform["nodata_hint"]
    return f"Données anciennes — vérifie le DAG {platform['key']}."


def _identity(platform_key: str, creds: dict, spotify_artist_id) -> bool:
    """Has this tenant declared the identity this platform needs?

    Reads the registry rather than restating it as an if-chain: the chain was a
    sixth copy of "which field is this platform's identity, and which row holds it",
    and the copies disagreed about Instagram.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    spec = PLATFORM_IDENTITIES.get(platform_key)
    if spec is None:
        return False
    declared = bool(str((creds.get(spec.storage) or {}).get(spec.field) or "").strip())
    if platform_key == "spotify":
        # The one mirrored identity: either copy counts as declared. This cannot
        # detect the two drifting apart — that is `identity-mirrored-but-written-once`,
        # closed by routing every writer through `write_platform_identity`.
        return bool(spotify_artist_id) or declared
    return declared


def _load_extra(db, artist_id: int) -> dict:
    """{platform: extra_config dict} — non-secret identity fields (no Fernet needed)."""
    import json
    df = db.fetch_df(
        "SELECT platform, extra_config FROM artist_credentials WHERE artist_id = %s",
        (artist_id,),
    )
    out = {}
    for _, row in df.iterrows():
        extra = row["extra_config"] or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        out[row["platform"]] = extra
    return out


def artist_readiness(db, artist_id: int) -> list:
    """Per-platform readiness matrix for one artist.

    Returns [{key, label, icon, status, status_label, expected_silence, last_dt,
    next_action}, …].
    """
    from src.utils.freshness_monitor import check_freshness, sources_for

    creds = _load_extra(db, artist_id)
    sp = db.fetch_query(
        "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,)
    )
    spotify_artist_id = sp[0][0] if sp else None
    fresh = {r["source"]: r for r in check_freshness(db, artist_id)}

    matrix = []
    for p in _PLATFORMS:
        identity = _identity(p["key"], creds, spotify_artist_id)
        # One platform can be proven by several sources (Spotify: the API table OR
        # the S4A CSV). Score each and keep the BEST — an artist who only uploads
        # CSVs and one who only connects the API must both reach 🟢, and neither
        # should be told to do the other's work.
        sources = sources_for(p["key"]) or ()
        best = None
        for src in sources:
            f = fresh.get(src, {})
            silence = f.get("expected_silence")
            cand = platform_status(
                identity, f.get("last_dt"), f.get("stale", True), silence,
            )
            if best is None or _RANK[cand] > _RANK[best[0]]:
                best = (cand, silence, f.get("last_dt"))
        status, silence, last_dt = best or (
            platform_status(identity, None, True, None), None, None)
        matrix.append({
            "key": p["key"], "label": p["label"], "icon": _ICON[status],
            "status": status, "status_label": _LABEL[status],
            "expected_silence": silence,
            "last_dt": last_dt, "next_action": next_action(p, status, silence),
        })
    return matrix


def readiness_red_flags(db, artist_id: int) -> list:
    """Platforms that are CONNECTED but producing NO data (the silent-0-row gap) for one artist."""
    return [m for m in artist_readiness(db, artist_id) if m["status"] == NO_DATA]

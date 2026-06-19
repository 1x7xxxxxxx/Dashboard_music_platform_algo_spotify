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
# status values, worst → best
TODO, NO_DATA, STALE, OK = "todo", "no_data", "stale", "ok"

_ICON = {TODO: "⚪", NO_DATA: "🔴", STALE: "🟡", OK: "🟢"}
_LABEL = {
    TODO: "À connecter",
    NO_DATA: "Connecté — aucune donnée",
    STALE: "Données anciennes",
    OK: "OK",
}

# platform → identity location + the per-tenant freshness source (freshness_monitor labels) +
# the action hint when connected but no data flows.
_PLATFORMS = (
    {"key": "soundcloud", "label": "☁️ SoundCloud", "source": "SoundCloud",
     "id_hint": "ton User ID SoundCloud numérique",
     "nodata_hint": "vérifie le User ID ; l'app SoundCloud partagée doit être configurée (admin)"},
    {"key": "spotify", "label": "🎵 Spotify", "source": "Spotify S4A",
     "id_hint": "l'URL de ta page Spotify Artist",
     "nodata_hint": "importe ton CSV Spotify for Artists, ou vérifie l'ID artiste"},
    {"key": "youtube", "label": "🎬 YouTube", "source": "YouTube",
     "id_hint": "ton Channel ID (UC…)",
     "nodata_hint": "ta chaîne n'a peut-être aucune vidéo publique (cherche ta chaîne « … - Topic »)"},
    {"key": "meta", "label": "📱 Meta Ads", "source": "Meta Ads",
     "id_hint": "ton Ad Account ID",
     "nodata_hint": "partage ton compte publicitaire avec le Business Manager admin (asset sharing)"},
    {"key": "instagram", "label": "📸 Instagram", "source": "Instagram",
     "id_hint": "ton Instagram Business Account ID",
     "nodata_hint": "partage ton compte Instagram/Page avec le Business Manager admin"},
)


def platform_status(identity_present: bool, last_dt, stale: bool) -> str:
    """Pure: identity + data-recency → one of TODO/NO_DATA/STALE/OK."""
    if not identity_present:
        return TODO
    if last_dt is None:
        return NO_DATA
    return STALE if stale else OK


def next_action(platform: dict, status: str) -> str:
    """Pure: the exact next step for an (platform, status)."""
    if status == OK:
        return ""
    if status == TODO:
        return f"Renseigne {platform['id_hint']}."
    if status == NO_DATA:
        return platform["nodata_hint"]
    return f"Données anciennes — vérifie le DAG {platform['key']}."


def _identity(platform_key: str, creds: dict, spotify_artist_id) -> bool:
    if platform_key == "soundcloud":
        return bool(creds.get("soundcloud", {}).get("user_id"))
    if platform_key == "spotify":
        return bool(spotify_artist_id or creds.get("spotify", {}).get("spotify_artist_id"))
    if platform_key == "youtube":
        return bool(creds.get("youtube", {}).get("channel_id"))
    if platform_key == "meta":
        return bool(creds.get("meta", {}).get("account_id"))
    if platform_key == "instagram":
        return bool(creds.get("meta", {}).get("ig_user_id"))
    return False


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

    Returns [{key, label, icon, status, status_label, last_dt, next_action}, …].
    """
    from src.utils.freshness_monitor import check_freshness

    creds = _load_extra(db, artist_id)
    sp = db.fetch_query(
        "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,)
    )
    spotify_artist_id = sp[0][0] if sp else None
    fresh = {r["source"]: r for r in check_freshness(db, artist_id)}

    matrix = []
    for p in _PLATFORMS:
        f = fresh.get(p["source"], {})
        status = platform_status(
            _identity(p["key"], creds, spotify_artist_id),
            f.get("last_dt"), f.get("stale", True),
        )
        matrix.append({
            "key": p["key"], "label": p["label"], "icon": _ICON[status],
            "status": status, "status_label": _LABEL[status],
            "last_dt": f.get("last_dt"), "next_action": next_action(p, status),
        })
    return matrix


def readiness_red_flags(db, artist_id: int) -> list:
    """Platforms that are CONNECTED but producing NO data (the silent-0-row gap) for one artist."""
    return [m for m in artist_readiness(db, artist_id) if m["status"] == NO_DATA]

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
TODO, BROKEN, NO_DATA, STALE, QUIET, OK = (
    "todo", "broken", "no_data", "stale", "quiet", "ok")

# Worst → best. Used to pick the best answer when several sources can prove the
# same platform; the order is the one the module docstring already documents.
# BROKEN sits just above TODO: a probe that FAILED must not outrank a source that
# actually answered, and it must not be mistaken for the tenant's own move.
_RANK = {TODO: 0, BROKEN: 1, NO_DATA: 2, STALE: 3, QUIET: 4, OK: 5}

_ICON = {TODO: "⚪", BROKEN: "⚠️", NO_DATA: "🔴", STALE: "🟡", QUIET: "⏸️", OK: "🟢"}
_LABEL = {
    TODO: "À connecter",
    BROKEN: "Vérification impossible — on regarde",
    NO_DATA: "Connecté — aucune donnée",
    STALE: "Données anciennes",
    QUIET: "Silence normal — rien à collecter",
    OK: "OK",
}

# platform → presentation only: label, and the hints. Which freshness sources prove a
# platform is collecting lives in `freshness_monitor.SOURCES_FOR_PLATFORM` — restating
# it here is what let readiness judge Spotify on the CSV table while three other
# surfaces judged it on three other tables.
# `where` = l'endroit EXACT où cette plateforme se règle, tel qu'il s'appelle dans le
# menu. Ajouté le 2026-09-04 : « on a meta ads et instagram séparé mais quand on
# configure meta ads on a accès à insta ??? À simplifier ». Les deux SONT deux
# plateformes — deux identités, deux collectes, deux pannes possibles — et les fondre
# perdrait l'information qui compte (Instagram peut être muet pendant que Meta Ads
# répond). Ce qui manquait, c'est que rien ne disait qu'elles se saisissent au même
# endroit. Le dire coûte cinq mots et supprime la question.
_PLATFORMS = (
    {"key": "soundcloud", "label": "☁️ SoundCloud",
     "where": "Credentials API → SoundCloud",
     "id_hint": "ton User ID SoundCloud numérique",
     "nodata_hint": "vérifie le User ID ; l'app SoundCloud partagée doit être configurée (admin)"},
    {"key": "spotify", "label": "🎵 Spotify",
     "where": "Credentials API → Spotify",
     "id_hint": "l'URL de ta page Spotify Artist",
     "nodata_hint": "importe ton CSV Spotify for Artists, ou vérifie l'ID artiste"},
    {"key": "youtube", "label": "🎬 YouTube",
     "where": "Credentials API → YouTube",
     "id_hint": "ton Channel ID (UC…)",
     "nodata_hint": "ta chaîne n'a peut-être aucune vidéo publique (cherche ta chaîne « … - Topic »)"},
    {"key": "meta", "label": "📱 Meta Ads",
     "where": "Credentials API → Meta / Instagram",
     "id_hint": "ton Ad Account ID",
     "nodata_hint": "partage ton compte publicitaire avec le Business Manager admin (asset sharing)"},
    {"key": "instagram", "label": "📸 Instagram",
     "where": "Credentials API → Meta / Instagram",
     "id_hint": "ton Instagram Business Account ID",
     "nodata_hint": "partage ton compte Instagram/Page avec le Business Manager admin"},
)


def platform_status(identity_present: bool, last_dt, stale: bool,
                    expected_silence: str | None = None,
                    error: str | None = None) -> str:
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
    if error:
        # The check FAILED — missing table, bad identifier, dead connection. Saying
        # "connected, no data" here blames the artist for our outage and hands them
        # a next action that cannot work. `check_freshness` sets this field for
        # exactly this reason and, until 2026-08-22, nothing read it.
        return BROKEN
    if expected_silence:
        return QUIET
    if last_dt is None:
        return NO_DATA
    return STALE if stale else OK


def next_action(platform: dict, status: str, expected_silence: str | None = None,
                live_reason: str | None = None) -> str:
    """Pure: the exact next step for an (platform, status).

    `live_reason` is what the platform's API actually answered, when someone asked.
    It REPLACES the static `nodata_hint` guess, because a measurement beats a guess
    every time — GRiNCH's SoundCloud was answered with "vérifie le User ID ; l'app
    partagée doit être configurée (admin)" for weeks when the true answer, available
    from one API call, was "ce profil n'a aucun titre public".
    """
    if status == OK:
        return ""
    if status == QUIET:
        # The reason travels with the status. A quiet light with nothing behind it
        # is read as a bug the next time someone looks at it — which is how a
        # suppressed alert becomes worse than the noisy one it replaced.
        return f"Rien à faire — {expected_silence}" if expected_silence else "Rien à faire."
    if status == BROKEN:
        # Deliberately asks the artist for NOTHING: this is our failure, not theirs.
        return "Rien à faire de ton côté — la vérification a échoué, on regarde."
    if status == TODO:
        return f"Renseigne {platform['id_hint']}."
    if status == NO_DATA:
        return live_reason or platform["nodata_hint"]
    # STALE — this sentence is READ BY THE ARTIST. "vérifie le DAG youtube" told them
    # to fix something they cannot reach: nobody outside the team has an Airflow login.
    # Cooper, About Face p.311, names exactly this failure — a message that "demands
    # that he fix a situation that the application can and should usually fix just as
    # well". Same contract as BROKEN: collection stopping is our problem, not theirs.
    # The operator gets the DAG name and the literal cause through the run ledger
    # (etl_run_log) and the nightly email, which is where an operator actually looks.
    return live_reason or ("Rien à faire de ton côté — la collecte s'est arrêtée, "
                           "on regarde.")


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


def artist_readiness(db, artist_id: int, probe=None) -> list:
    """Per-platform readiness matrix for one artist.

    Returns [{key, label, icon, status, status_label, expected_silence, last_dt,
    next_action, live_reason, probe_ran}, …].

    `probe` is an optional `callable(logical_platform) -> (ok, message) | None`
    (see `src.utils.platform_probes`). Three rules, all load-bearing:

      1. It defaults to None, so every existing caller — the dashboard, the home
         tracker, preflight step 4 — behaves exactly as before. Nobody is forced to
         change, and no page starts making API calls on render.
      2. It is called ONLY when the computed status is NO_DATA or BROKEN. Fresh rows
         already prove the credential produced data; probing green costs an API call
         to learn nothing and adds a transient-blip path to a false red.
      3. It NEVER changes the status, only the wording of `next_action`. A network
         hiccup must not be able to turn a collecting tenant red — that would make
         this the noise generator it exists to remove.
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
        # Le détail PAR SOURCE, en plus du meilleur. Spotify en a deux — l'API et
        # l'import CSV Spotify for Artists — et la ligne unique ne montrait que le
        # meilleur des deux : un artiste dont l'API remonte et qui n'a jamais déposé
        # de CSV lisait « 🟢 » sans savoir que la moitié CSV n'existe pas, et
        # réciproquement. Demandé le 2026-09-04 : « séparer spotify de spotify 4
        # artist qui sont 2 process différents ».
        #
        # C'est un AJOUT, pas un changement de contrat : le nombre de lignes, les
        # statuts et les actions ne bougent pas. La matrice s'en sert pour afficher
        # deux lignes ; l'alerte nocturne, le canari et `artist-preflight` continuent
        # de lire exactement ce qu'ils lisaient. Une ligne de plus dans le tableau
        # aurait fait crier l'alerte chaque nuit sur une source que personne
        # n'alimente (R46, S4A muette depuis 88 jours) — le bruit qu'on a mis un mois
        # à supprimer.
        by_source = {}
        for src in sources:
            f = fresh.get(src, {})
            silence = f.get("expected_silence")
            cand = platform_status(
                identity, f.get("last_dt"), f.get("stale", True), silence,
                f.get("error"),
            )
            by_source[src] = {"status": cand, "icon": _ICON[cand],
                              "status_label": _LABEL[cand],
                              "last_dt": f.get("last_dt"),
                              "expected_silence": silence}
            if best is None or _RANK[cand] > _RANK[best[0]]:
                best = (cand, silence, f.get("last_dt"))
        status, silence, last_dt = best or (
            platform_status(identity, None, True, None), None, None)

        # Rule 2: ask the API only where the database already says something is wrong.
        live_reason, probe_ran = None, False
        if probe is not None and status in (NO_DATA, BROKEN):
            result = probe(p["key"])
            if result is not None:          # None = not measured, NOT "measured fine"
                probe_ran = True
                ok, message = result
                if not ok:
                    live_reason = message

        matrix.append({
            "key": p["key"], "label": p["label"], "icon": _ICON[status],
            "where": p.get("where", ""), "by_source": by_source,
            "status": status, "status_label": _LABEL[status],
            "expected_silence": silence,
            "last_dt": last_dt,
            "next_action": next_action(p, status, silence, live_reason),
            "live_reason": live_reason, "probe_ran": probe_ran,
        })
    return matrix


def readiness_red_flags(db, artist_id: int, probe=None) -> list:
    """Platforms that need someone to look, for one artist.

    NO_DATA (connected, silent-0-row), BROKEN (the check itself failed), and STALE
    (it collected, then stopped). Somebody must act on all three; only NO_DATA is
    ever the artist's move, and `next_action` is what says which.

    STALE was excluded until 2026-08-23, and that exclusion is what let Benken's
    YouTube fail two nights running with no signal anywhere: the DAG reported SUCCESS
    (the failure was isolated per tenant), freshness turned the tenant 🟡, and this
    function dropped 🟡 on the floor. "Collected, then stopped" IS the shape of
    "collection is broken" — it is in fact the only shape a working credential can
    take when it breaks.
    """
    return [m for m in artist_readiness(db, artist_id, probe=probe)
            if m["status"] in (NO_DATA, BROKEN, STALE)]


def readiness_stalled_flags(db, artist_id: int, min_age_days: int = 7) -> list:
    """Platforms still at TODO for a tenant who signed up a while ago.

    TODO on day one is the correct state — they have not got to it yet. TODO after a
    week is the invisible failure mode nothing reported: someone created an account,
    never declared a single identity, and no surface ever said so. `readiness_red_flags`
    cannot see them, because a tenant who declared nothing produces no NO_DATA row.
    """
    row = db.fetch_query(
        "SELECT created_at FROM saas_artists WHERE id = %s", (artist_id,))
    if not row or row[0][0] is None:
        return []
    created = row[0][0]
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if (now - created).days < min_age_days:
        return []
    return [m for m in artist_readiness(db, artist_id) if m["status"] == TODO]

"""The one place that writes a tenant's platform identity. Spotify lives in TWO tables.

Type: Utility
Uses: PostgresHandler
Triggers: the credentials form (src/dashboard/views/credentials/_render.py) and
    tools/create_canary.py
Persists in: artist_credentials.extra_config, saas_artists.spotify_artist_id

Why this module exists — measured 2026-08-21.

A tenant's Spotify artist id is stored in two places: `artist_credentials.extra_config`
(what the readiness checks and the credentials form read) and the
`saas_artists.spotify_artist_id` column (what `spotify_api_daily` reads to decide whose
catalogue to collect). The credentials form wrote both. `tools/create_canary.py` wrote
only the first.

The result was a tenant that reported "Connecte -- artiste << Daft Punk >> OK" on every
screen, passed its connection test, and collected NOTHING: the DAG succeeded in half a
second logging "aucun spotify_artist_id declare". A green that means nothing is worse
than a red -- and it happened to the canary, the tenant whose whole job is to catch
exactly this.

The duplication itself is the defect; collapsing the two columns is a migration, not a
bugfix. Until then, every writer goes through here, so no third writer can get it half
right.
"""

from __future__ import annotations

import json
import re
from typing import NamedTuple

class PlatformIdentity(NamedTuple):
    """How one logical platform's tenant identity is named and stored.

    `logical` and `storage` differ for exactly one platform, and conflating them is
    a real bug source: Instagram is a logical platform everywhere (readiness, the
    alert monitor, the connection tests) but its identity lives INSIDE the `meta`
    credentials row, because the artist types it in the Meta tab. Writing it under
    `platform='instagram'` would create a row no consumer reads -- the DAG selects
    tenants on `creds['meta']['ig_user_id']`.
    """

    logical: str
    storage: str
    field: str
    mirror: str | None
    # Regex the value MUST fully match before it is used anywhere. Not cosmetic
    # validation: these ids are interpolated into REST paths, and `requests` does
    # not percent-encode `/` or `?` in a path you build yourself. A tenant who set
    # ig_user_id to `me/accounts` turned the platform's own probe into a call to
    # /me/accounts with the shared System User token — whose response carries Page
    # access tokens. Verified 2026-08-22. The identity is attacker-controlled free
    # text; its SHAPE is the only thing standing between it and the URL.
    pattern: str


# THE registry. Five entries, and every other surface derives from it.
#
# Before 2026-08-22 this map existed in five places that disagreed: here (5 entries),
# `artist_readiness._PLATFORMS` (5), `credentials/_core.UNIQUE_IDENTITY_FIELDS` (4),
# `tools/create_canary._IDENTITY_FIELD` (4) and `tests/test_identity_fields_collectable`
# (5). The two 4-entry copies both omitted Instagram, so `find_identity_conflict`
# returned None for it -- two tenants could claim the same Instagram account in
# silence -- and the canary could not exercise the platform at all.
#
# What made it invisible: `tests/test_create_canary` asserted the tool EQUALLED the
# 4-entry copy, so a green guard held the gap in place; and
# `tests/test_identity_uniqueness` parametrised over that same copy, so the missing
# entry removed tests instead of failing one. A registry that its own guards derive
# from cannot report its own omission -- hence the literal ratchet in that file.
PLATFORM_IDENTITIES = {
    "soundcloud": PlatformIdentity("soundcloud", "soundcloud", "user_id", None,
                                   r"[0-9]{1,25}"),
    "spotify": PlatformIdentity("spotify", "spotify", "spotify_artist_id",
                                "spotify_artist_id", r"[0-9A-Za-z]{22}"),
    "youtube": PlatformIdentity("youtube", "youtube", "channel_id", None,
                                r"UC[0-9A-Za-z_-]{22}"),
    # `act_` is stripped by the collector; accept both forms, digits only after it.
    "meta": PlatformIdentity("meta", "meta", "account_id", None,
                             r"(?:act_)?[0-9]{1,25}"),
    # Rides the meta row. See PlatformIdentity's docstring.
    "instagram": PlatformIdentity("instagram", "meta", "ig_user_id", None,
                                  r"[0-9]{1,25}"),
}


def identity_is_well_formed(logical: str, value: str) -> bool:
    """Does `value` have the shape this platform's identity must have?

    Fullmatch, never search: `re.match` would accept `123/me/accounts`, which is
    the whole point of the check.
    """
    spec = PLATFORM_IDENTITIES.get(logical)
    if spec is None:
        return False
    return re.fullmatch(spec.pattern, (value or "").strip()) is not None


def malformed_identities(extra_by_platform: dict) -> dict:
    """{logical: value} for every DECLARED identity whose shape is wrong."""
    out = {}
    for logical, spec in PLATFORM_IDENTITIES.items():
        value = str((extra_by_platform.get(spec.storage) or {}).get(spec.field) or "").strip()
        if value and not identity_is_well_formed(logical, value):
            out[logical] = value
    return out


def storage_platform(logical: str) -> str:
    """The `artist_credentials.platform` value that holds this identity."""
    spec = PLATFORM_IDENTITIES.get(logical)
    return spec.storage if spec else logical


def identity_field(logical: str) -> str | None:
    """The extra_config key carrying this platform's tenant identity."""
    spec = PLATFORM_IDENTITIES.get(logical)
    return spec.field if spec else None


def declared_identities(extra_by_platform: dict, mirrors: dict | None = None) -> set:
    """Logical platforms this tenant has actually DECLARED an identity for.

    Pure — no DB, no Streamlit. `extra_by_platform` is {storage_platform: extra_config};
    `mirrors` is {logical_platform: value} for the identities this repo ALSO keeps on a
    `saas_artists` column, i.e. exactly the specs carrying a `mirror`.

    Exists because four surfaces decided "connected" from the EXISTENCE of an
    `artist_credentials` row rather than from the identity value, so an artist who
    opened a tab and saved it blank was shown ✅ while readiness said ⚪. The Meta row
    made it worse: a row holding only `ig_user_id` counted as Meta-connected.

    `mirrors` was added 2026-08-26. Reading only `extra_config` made this function
    disagree with `artist_readiness._identity`, which honours the mirror explicitly —
    two readers, one question, two answers. Measured in production: the owner (id=1)
    has NO `spotify` row at all and `saas_artists.spotify_artist_id` =
    `7sbfafbLjNZGZJZjZ3xoPB`, so the nightly mail announced a missing credential that
    is present. A mirror only the WRITER knows about is how the canary went green on
    nothing; a mirror only ONE reader knows about is how an alert cries wolf.

    Omitting `mirrors` keeps the old behaviour, so a caller that has no cheap way to
    read `saas_artists` is not forced to grow a query — it just cannot see a mirrored
    identity, which is the pre-2026-08-26 contract and is stated rather than implied.
    """
    mirrors = mirrors or {}
    out = set()
    for logical, spec in PLATFORM_IDENTITIES.items():
        value = (extra_by_platform.get(spec.storage) or {}).get(spec.field)
        if not str(value or "").strip() and spec.mirror:
            value = mirrors.get(logical)
        if str(value or "").strip():
            out.add(logical)
    return out


# Derived views, kept so existing callers and guards keep working unchanged.
# platform -> the key inside extra_config that carries the tenant's own identity.
IDENTITY_KEYS = {k: v.field for k, v in PLATFORM_IDENTITIES.items()}

# Platforms whose identity is ALSO mirrored on a saas_artists column, and where.
# A mirror that only one writer knows about is how the canary went green on nothing.
IDENTITY_MIRRORS = {k: v.mirror for k, v in PLATFORM_IDENTITIES.items() if v.mirror}


def write_platform_identity(db, artist_id: int, platform: str, extra: dict) -> None:
    """Persist `extra` for this tenant AND every mirror the platform declares.

    Callers must already have validated the identity (ownership conflict, non-empty).
    """
    if platform not in IDENTITY_KEYS:
        raise ValueError(f"unknown platform {platform!r}; known: {sorted(IDENTITY_KEYS)}")

    # The row is written under the STORAGE platform, never the logical one: an
    # `instagram` row would be an orphan nothing reads (the DAG selects tenants on
    # `creds['meta']['ig_user_id']`). The `||` merge below means the ig_user_id
    # composes with account_id in the meta row instead of clobbering it.
    #
    # `logical` is kept SEPARATE and used for every registry lookup after this
    # point. Reassigning `platform` in place would silently make the mirror lookup
    # ask about the storage row — correct today only by luck, since meta has no
    # mirror, and wrong the day a mirrored platform gains a different storage.
    logical = platform
    storage = storage_platform(logical)

    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s::jsonb) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET "
        "extra_config = COALESCE(artist_credentials.extra_config, '{}'::jsonb) "
        "|| EXCLUDED.extra_config, updated_at = CURRENT_TIMESTAMP",
        (artist_id, storage, json.dumps(extra)),
    )
    mirror_col = IDENTITY_MIRRORS.get(logical)
    if mirror_col:
        value = extra.get(IDENTITY_KEYS[logical]) or None
        # Identifier interpolated from a module-level constant, never from input
        # (cross-cutting rule #8); the value stays parameterised.
        assert mirror_col in set(IDENTITY_MIRRORS.values())
        db.execute_query(
            f"UPDATE saas_artists SET {mirror_col} = %s WHERE id = %s",  # noqa: S608
            (value, artist_id),
        )


def mirrored_columns() -> dict[str, str]:
    """Exposed so a test can assert every writer covers the same mirrors."""
    return dict(IDENTITY_MIRRORS)


# ── Meta : N comptes publicitaires sous UNE ligne de credentials ─────────────
#
# Décidé le 2026-08-24 (ADR-013), forme **séparée** : un artiste passant par une
# agence a plusieurs comptes publicitaires, et ils ne se cumulent pas — chacun a son
# budget, son CPR, ses campagnes. Le stockage suit cette forme sans multiplier les
# lignes de `artist_credentials` :
#
#   * la **credential** est unique — un seul token System User partagé (ADR-006), une
#     seule app ; ce qui est pluriel, c'est l'**identité du compte payeur**. Passer à
#     `UNIQUE(artist_id, platform, account)` aurait dupliqué le secret autant de fois
#     que de comptes, pour une valeur identique, et cassé les 6 lecteurs qui
#     supposent une ligne par plateforme ;
#   * `account_ids` (liste JSON) est **canonique** ; `account_id` reste le **premier
#     élément**, si bien qu'aucun lecteur existant ne change de comportement.
#
# Le miroir est délibéré et gardé (`tests/test_meta_multi_account.py`) : ce module
# documente ailleurs qu'un miroir dont un seul écrivain a connaissance est la façon
# dont le canari est passé au vert sur rien. Ici l'écrivain est unique — cette
# fonction et `normalise_meta_accounts` — et le lecteur aussi.

META_ACCOUNTS_FIELD = "account_ids"


def normalise_meta_account(value: str) -> str:
    """`act_` en préfixe, une fois et une seule. Chaîne vide si rien d'exploitable."""
    raw = (value or "").strip()
    if not raw:
        return ""
    return raw if raw.startswith("act_") else f"act_{raw}"


def meta_ad_account_ids(extra: dict) -> list[str]:
    """Les comptes publicitaires déclarés, normalisés `act_…`, sans doublon.

    Lit `account_ids` quand il existe, retombe sur le scalaire `account_id` pour
    toute ligne écrite avant le multi-comptes. Pure — ni base, ni Streamlit.
    """
    extra = extra or {}
    raw = extra.get(META_ACCOUNTS_FIELD)
    if isinstance(raw, str):
        # Une ligne écrite à la main (ou par un import) peut porter du texte : on
        # accepte la séparation par virgule ou par saut de ligne, jamais un split
        # implicite sur l'espace (un id n'en contient pas, mais une erreur de saisie
        # en contiendrait et produirait des comptes fantômes).
        raw = [p for p in re.split(r"[,\n;]+", raw)]
    if not isinstance(raw, list):
        raw = []
    candidates = [*raw, extra.get(PLATFORM_IDENTITIES["meta"].field)]
    out: list[str] = []
    for value in candidates:
        acct = normalise_meta_account(str(value or ""))
        if acct and acct not in out:
            out.append(acct)
    return out


def malformed_meta_accounts(extra: dict) -> list[str]:
    """Les comptes déclarés dont la FORME est fausse — la même que le scalaire.

    `malformed_identities` ne regarde que `account_id`. Sans cette fonction, le
    deuxième compte d'une agence entrait dans un chemin REST sans jamais avoir été
    confronté au motif — exactement le trou que le motif existe pour fermer.
    """
    return [a for a in meta_ad_account_ids(extra)
            if not identity_is_well_formed("meta", a)]


def with_meta_accounts(extra: dict, accounts: list[str]) -> dict:
    """`extra` portant la liste canonique ET son miroir scalaire, ou ni l'un ni l'autre.

    Le miroir n'est jamais laissé en arrière : une liste vide efface les deux clés,
    sans quoi un artiste qui retire tous ses comptes resterait « connecté » aux yeux
    de `declared_identities`, qui lit le scalaire.
    """
    out = dict(extra or {})
    cleaned: list[str] = []
    for a in accounts or []:
        acct = normalise_meta_account(a)
        if acct and acct not in cleaned:
            cleaned.append(acct)
    if not cleaned:
        out.pop(META_ACCOUNTS_FIELD, None)
        out.pop(PLATFORM_IDENTITIES["meta"].field, None)
        return out
    out[META_ACCOUNTS_FIELD] = cleaned
    out[PLATFORM_IDENTITIES["meta"].field] = cleaned[0]
    return out

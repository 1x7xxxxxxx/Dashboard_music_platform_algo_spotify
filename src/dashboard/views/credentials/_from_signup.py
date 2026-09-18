"""Matérialiser en credentials les liens saisis à l'inscription.

Type: Sub
Uses: platform_identity_resolver, extract_spotify_artist_id, parse_channel_input
Triggers: `app._verify_email`, une seule fois par compte
Depends on: saas_artists.pending_profile_links (migration 087)
Persists in: artist_credentials, saas_artists (le champ d'attente est vidé)

Demandé le 2026-09-05 : « on demande les profils à la création, et on les rentre dans
credentials à un moment pertinent ». Le moment pertinent est la **vérification de
l'e-mail**, pas la création : avant elle, l'identité serait NON vérifiée, et
`find_identity_conflict` la considérerait comme prise — une inscription jamais
confirmée pourrait squatter le profil Spotify de quelqu'un d'autre.

## Ce que cette matérialisation ne court-circuite pas

Elle passe par les **mêmes** convertisseurs que le formulaire — `extract_spotify_artist_id`,
`soundcloud_user_id_from_url`, `parse_channel_input` — et par le **même** contrôle
d'unicité multi-locataire. Un raccourci qui contournerait ces deux-là écrirait des
identités que la saisie manuelle aurait refusées, et le premier symptôme serait un
locataire lisant les chiffres d'un autre.

Chaque plateforme est **isolée** : un lien SoundCloud illisible ne doit pas faire perdre
un lien Spotify parfaitement valide. Rien ici ne lève : au pire l'artiste retrouve un
champ vide, exactement comme avant cette fonctionnalité.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Ce qu'on sait convertir depuis un lien, et sous quelle clé le formulaire l'écrit.
_FIELD = {
    "spotify": "spotify_artist_id",
    "soundcloud": "user_id",
    "youtube": "channel_id",
    # Instagram s'écrit dans la ligne `meta` (`storage_platform`), pas dans une
    # ligne à lui : c'est le modèle de stockage, et le séparer serait un autre
    # changement. La fusion ci-dessous protège `account_id`, qui vit au même endroit.
    "instagram": "ig_user_id",
}


def _existing_mirrors(db, artist_id: int) -> dict:
    """{plateforme logique: valeur} pour les miroirs déjà posés sur `saas_artists`."""
    from src.utils.tenant_identity import mirrored_columns

    colonnes = mirrored_columns()
    if not colonnes:
        return {}
    # Identifiants issus d'une constante de module, jamais d'une entrée (règle #8).
    noms = ", ".join(sorted(set(colonnes.values())))
    try:
        rows = db.fetch_query(
            f"SELECT {noms} FROM saas_artists WHERE id = %s", (artist_id,))  # noqa: S608
    except Exception as exc:  # noqa: BLE001 — un miroir illisible ne bloque pas l'onboarding
        logger.warning("mirrors unreadable for %s: %s", artist_id, type(exc).__name__)
        return {}
    if not rows:
        return {}
    ordre = sorted(set(colonnes.values()))
    par_colonne = dict(zip(ordre, rows[0]))
    return {logique: par_colonne.get(col)
            for logique, col in colonnes.items() if par_colonne.get(col)}


def _identifier(platform: str, link: str) -> str:
    """L'identifiant que le pipeline attend, ou une chaîne vide. Ne lève jamais."""
    try:
        if platform == "spotify":
            from ._core import extract_spotify_artist_id
            return extract_spotify_artist_id(link)
        if platform == "soundcloud":
            from src.utils.platform_identity_resolver import soundcloud_user_id_from_url
            user_id, _permalink = soundcloud_user_id_from_url(link)
            return user_id or ""
        if platform == "instagram":
            from src.utils.platform_identity_resolver import (
                instagram_user_id_from_handle,
            )
            ident, _name, problem = instagram_user_id_from_handle(link)
            if problem:
                logger.info("signup Instagram link unusable: %s", problem[:80])
            return ident or ""
        if platform == "youtube":
            # RÉSOUT désormais, au lieu de n'accepter qu'un `UC…` tout fait. Avant le
            # 2026-09-05, un artiste qui collait `youtube.com/@sa-chaine` à
            # l'inscription voyait son lien silencieusement jeté : le seul champ que
            # la page propose accepte justement cette forme-là. La résolution existe
            # et coûte un appel — la même que l'onglet Credentials utilise.
            import os

            from src.dashboard.views.credentials._platform_youtube import (
                resolve_channel_id,
            )
            ident, _desc, problem = resolve_channel_id(
                link, os.getenv("YOUTUBE_API_KEY", ""))
            if problem:
                logger.info("signup YouTube link unusable: %s", problem[:80])
            return ident or ""
    except Exception as exc:  # noqa: BLE001 — un lien illisible n'est pas une panne
        logger.info("signup link unusable for %s: %s", platform, type(exc).__name__)
    return ""


def materialise(db, artist_id: int) -> list:
    """Écrit ce qui est convertible. Rend les plateformes réellement branchées.

    Idempotente par construction : le champ d'attente est vidé à la fin, et une
    plateforme qui a déjà des credentials n'est jamais écrasée.
    """
    try:
        rows = db.fetch_query(
            "SELECT pending_profile_links FROM saas_artists WHERE id = %s",
            (artist_id,))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pending links unreadable for %s: %s", artist_id, type(exc).__name__)
        return []
    if not rows or not rows[0][0]:
        return []
    links = rows[0][0]
    if isinstance(links, str):
        try:
            links = json.loads(links)
        except ValueError:
            return []

    from ._core import _load_credentials, find_identity_conflict
    from src.utils.tenant_identity import (
        identity_is_well_formed,
        write_platform_identity,
    )

    existing = _load_credentials(db, artist_id)
    # LES MIROIRS DÉJÀ POSÉS, lus une fois.
    #
    # Le garde « ne jamais écraser une saisie de l'artiste » consultait la ligne de
    # `artist_credentials` SEULE. Or `write_platform_identity` écrit le miroir
    # INCONDITIONNELLEMENT : un locataire portant un miroir sans ligne de credentials —
    # l'état relevé en production pour l'artiste 1 — aurait vu un lien d'inscription
    # écraser sa clé de collecte. On consulte donc les deux.
    _mirrors = _existing_mirrors(db, artist_id)
    connected = []
    for platform, link in (links or {}).items():
        if platform not in _FIELD or not (link or "").strip():
            continue
        from src.utils.tenant_identity import identity_field, storage_platform
        row = storage_platform(platform)
        field = identity_field(platform) or _FIELD[platform]
        # `_load_credentials` rend l'ENREGISTREMENT (platform, token, extra_config,
        # updated_at…), pas `extra_config`. Le confondre a produit un `Timestamp` dans
        # le dict à écrire, donc un `TypeError` de sérialisation JSON — attrapé par le
        # `except` par-plateforme, qui a fait passer un vrai défaut pour « ce lien
        # n'était pas convertible ».
        row_extra = dict((existing.get(row) or {}).get("extra_config") or {})
        if row_extra.get(field):
            continue                       # jamais écraser une saisie de l'artiste
        if _mirrors.get(platform):
            continue                       # un miroir déjà posé est une saisie aussi
        identifier = _identifier(platform, link.strip())
        if not identifier:
            continue
        # LE MÊME contrôle de forme que le formulaire (`_render.py`, « Refuse a
        # malformed identity BEFORE anything else touches it »). Ce chemin ne
        # l'appelait pas : `malformed_identities` n'avait qu'UN site d'application
        # dans tout le dépôt, et ce n'était pas celui-ci. Une valeur libre saisie à
        # l'inscription devenait donc une identité persistée, puis un segment de
        # chemin d'URL sortante.
        if not identity_is_well_formed(platform, identifier):
            logger.info("signup link for %s has the wrong shape, skipped", platform)
            continue
        # Fusion : `_save_credentials` REMPLACE `extra_config`. Écrire `ig_user_id`
        # seul effacerait `account_id` ET `account_ids` s'ils étaient déjà là — le
        # déplacement d'une valeur ne doit jamais devenir la suppression d'une autre.
        # On repart donc de l'existant, listes comprises.
        extra = dict(row_extra)
        extra[field] = identifier
        try:
            # LE MÊME contrôle que le formulaire. Sans lui, deux comptes pourraient
            # déclarer le même profil et lire les chiffres l'un de l'autre.
            if find_identity_conflict(db, artist_id, platform, extra):
                logger.info("signup link for %s already belongs to another tenant",
                            platform)
                continue
            # `write_platform_identity` et NON `_save_credentials`, depuis le
            # 2026-09-18. Trois raisons, dans cet ordre :
            #
            # 1. Lui seul écrit le MIROIR (`saas_artists.spotify_artist_id`), que
            #    `spotify_api_daily` lit pour choisir ses locataires. Sans lui, ce
            #    chemin produisait un artiste « connecté » sur tous les écrans et
            #    jamais collecté — le scénario exact du canari du 2026-08-21, rejoué
            #    par un chemin d'écriture né APRÈS lui.
            # 2. Son `INSERT … ON CONFLICT` fusionne `extra_config` par `||` au lieu
            #    de le REMPLACER, ce qui donne gratuitement la propriété que le
            #    commentaire ci-dessus protège à la main.
            # 3. Il ne nomme jamais `token_encrypted`, donc il ne peut pas l'écraser —
            #    la convention de la chaîne vide devient inutile plutôt que subtile.
            #
            # ⚠️ `platform` et non `row` : il lui faut la plateforme LOGIQUE. Lui
            # passer `storage_platform(...)` ferait chercher `account_id` pour un lien
            # Instagram et interrogerait le mauvais miroir — correct aujourd'hui par
            # pure chance, `meta` n'ayant pas de miroir.
            write_platform_identity(db, artist_id, platform, extra)
            connected.append(platform)
        except Exception as exc:  # noqa: BLE001 — une plateforme n'en perd pas quatre
            logger.warning("could not materialise %s for %s: %s",
                           platform, artist_id, type(exc).__name__)

    try:
        db.execute_query(
            "UPDATE saas_artists SET pending_profile_links = NULL WHERE id = %s",
            (artist_id,))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pending links not cleared for %s: %s", artist_id, type(exc).__name__)
    return connected

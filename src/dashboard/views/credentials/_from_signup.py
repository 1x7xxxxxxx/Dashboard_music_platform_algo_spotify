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

    from ._core import _load_credentials, _save_credentials, find_identity_conflict

    existing = _load_credentials(db, artist_id)
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
        identifier = _identifier(platform, link.strip())
        if not identifier:
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
            # Chaîne VIDE et non `None` : c'est la convention de `_handle_save`,
            # et elle signifie « ne touche pas au secret » côté SQL. Aucune de ces
            # trois plateformes n'a de champ secret, mais la ligne en porte un en
            # production (P1 du 2026-08-22) — l'écraser serait le reperdre.
            _save_credentials(db, artist_id, row, "", extra)
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

"""What each connection gives the artist, and what it costs them to set up.

Type: Sub
Uses: nothing (pure data)
Depends on: nothing at import time
Persists in: nothing

Single source for the onboarding focus picker and the credentials page. The
onboarding step used to list six platforms flat, alphabetically-ish, with no
statement of what any of them buys you — the beta tester (Grinch, 2026-08-12)
had no basis to choose what to set up first and simply stopped. Every field
below exists to answer one of the two questions an artist actually asks:
"what do I get?" and "how long does this take?".

`recommended` marks the pair to start with — Spotify (where the streams come
from) + Instagram (whether the audience follows). Keep it to TWO: a
"recommended" set of six recommends nothing.
"""
from dataclasses import dataclass

CREDENTIALS = "credentials"  # connect with an identifier, in 🔑 Credentials API
CSV = "upload_csv"           # import a file, in 📂 Import CSV


@dataclass(frozen=True)
class PlatformValue:
    key: str
    icon: str
    label: str
    value: str          # the decision it unlocks — never a feature list
    need: str           # exactly what the artist must find
    effort_min: int     # honest minutes, first-time
    where: str          # CREDENTIALS | CSV
    recommended: bool = False
    caveat: str | None = None   # the thing that makes it fail for real people


PLATFORM_VALUES: tuple[PlatformValue, ...] = (
    PlatformValue(
        key="spotify", icon="🎵", label="Spotify",
        value="D'où viennent tes écoutes : playlists algorithmiques, radio, "
              "recherche — donc où pousser ta prochaine sortie.",
        need="le lien de ta page Spotify Artist",
        effort_min=2, where=CREDENTIALS, recommended=True,
    ),
    PlatformValue(
        key="instagram", icon="📸", label="Instagram",
        value="Si ton audience suit vraiment : followers, portée et posts qui "
              "convertissent, à mettre en face des pics d'écoutes.",
        need="l'ID de ton compte Instagram Business",
        effort_min=5, where=CREDENTIALS, recommended=True,
        caveat="compte **Business ou Créateur** relié à une Page Facebook — un "
               "compte personnel ne renvoie aucune statistique.",
    ),
    PlatformValue(
        key="soundcloud", icon="☁️", label="SoundCloud",
        value="Écoutes, likes et reposts par titre — le signal le plus rapide "
              "sur un morceau qui décolle.",
        need="ton User ID numérique",
        effort_min=2, where=CREDENTIALS,
        caveat="tes titres doivent être **publics** : un profil sans titre public "
               "ne remonte rien.",
    ),
    PlatformValue(
        key="youtube", icon="🎬", label="YouTube",
        value="Vues, likes et commentaires par vidéo — utile pour arbitrer clip "
              "vs. audio seul.",
        need="ton Channel ID (UC…)",
        effort_min=3, where=CREDENTIALS,
        caveat="si ta musique est distribuée, c'est souvent la chaîne "
               "**« … - Topic »** qu'il faut, pas ta chaîne perso.",
    ),
    PlatformValue(
        key="meta", icon="📱", label="Meta Ads",
        value="Ce que chaque euro de pub rapporte en écoutes — à ne connecter "
              "que si tu fais tourner des campagnes.",
        need="ton Ad Account ID (après `act=` dans l'URL)",
        effort_min=10, where=CREDENTIALS,
        caveat="ton compte publicitaire doit être **partagé** avec le Business "
               "Manager de la plateforme (asset sharing) — sinon zéro donnée.",
    ),
    PlatformValue(
        key="apple_music", icon="🎎", label="Apple Music",
        value="Écoutes et Shazams côté Apple, en complément de Spotify.",
        need="l'export CSV depuis Apple Music for Artists",
        effort_min=5, where=CSV,
    ),
)

BY_KEY = {p.key: p for p in PLATFORM_VALUES}

RECOMMENDED = tuple(p.key for p in PLATFORM_VALUES if p.recommended)


def ordered_for_setup(connected: set[str] | None = None) -> list[PlatformValue]:
    """Setup order: not-yet-connected first, recommended first, then cheapest.

    Sorting by effort inside each group means the artist always sees the next
    cheapest win rather than the alphabetical accident.
    """
    connected = connected or set()
    return sorted(
        PLATFORM_VALUES,
        key=lambda p: (p.key in connected, not p.recommended, p.effort_min, p.key),
    )


def total_effort(keys) -> int:
    """Minutes to set up a selection — shown before the artist commits to it."""
    return sum(BY_KEY[k].effort_min for k in keys if k in BY_KEY)

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

`recommended` marks the first column of the picker — the platforms an artist
should start with. Keep it a MINORITY of the list: a "recommended" set that
holds most of it recommends nothing. Chosen with the user on 2026-09-04:
Spotify (where the streams come from), Instagram (whether the audience
follows) and SoundCloud (the fastest signal on a track taking off) — all three
cost under five minutes and need no advertising account.

`setup_columns()` below is the grouping the picker renders. It is DERIVED from
`recommended` and `where`, never a second hand-written list: adding a platform
puts it in a column by construction, which is what a column of hard-coded keys
would silently fail to do.
"""
from dataclasses import dataclass

CREDENTIALS = "credentials"  # connect with an identifier, in 🔑 Credentials API
CSV = "upload_csv"           # import a file, on the CSV-drop page


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
        effort_min=2, where=CREDENTIALS, recommended=True,
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
        key="s4a", icon="📈", label="Spotify for Artists",
        value="Tes playlists, ton Discovery Mode et tes sources d'écoute — "
              "ce que l'API Spotify ne donne pas, et sur quoi les prédictions "
              "d'algorithme se calculent.",
        need="l'export CSV depuis Spotify for Artists",
        effort_min=5, where=CSV,
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

# L'ordre de déclaration ci-dessus porte une intention — Spotify d'abord, parce que
# c'est de là que viennent les écoutes. Départager deux plateformes de même coût par
# ordre alphabétique la perdait : SoundCloud passait devant Spotify pour la seule
# raison que « so » vient avant « sp ».
_DECLARED = {p.key: i for i, p in enumerate(PLATFORM_VALUES)}


def ordered_for_setup(connected: set[str] | None = None) -> list[PlatformValue]:
    """Setup order: not-yet-connected first, recommended first, then cheapest.

    Sorting by effort inside each group means the artist always sees the next
    cheapest win rather than the alphabetical accident — and ties fall back on the
    order of the registry, which is itself a statement of priority.
    """
    connected = connected or set()
    return sorted(
        PLATFORM_VALUES,
        key=lambda p: (p.key in connected, not p.recommended, p.effort_min,
                       _DECLARED[p.key]),
    )


def total_effort(keys) -> int:
    """Minutes to set up a selection — shown before the artist commits to it."""
    return sum(BY_KEY[k].effort_min for k in keys if k in BY_KEY)


# ── Les trois colonnes du sélecteur ─────────────────────────────────────────
#
# Demandé le 2026-09-04, après un parcours : « mettre à gauche et cochées celles
# qu'on recommande, à droite les autres, et ranger par colonne pour bien
# comprendre — 3 colonnes : prioritaire qu'on conseille, un peu plus long, CSV ».
#
# Six cases empilées se lisent comme une liste de courses : rien ne dit laquelle
# vient d'abord, et l'artiste les prend dans l'ordre où elles tombent. Le ⭐ posé
# sur trois d'entre elles ne suffisait pas — un ornement dans une colonne unique
# ne hiérarchise rien.
#
# Ce qui distingue les trois groupes n'est PAS le goût : c'est le GESTE.
#   1. coller un lien qu'on a déjà        → deux à cinq minutes
#   2. aller chercher un identifiant      → un compte tiers, parfois un partage
#   3. déposer un fichier                 → un export à télécharger d'abord
# D'où une dérivation, pas trois listes de clés : `recommended` et `where`
# répondent déjà, et une plateforme ajoutée demain atterrit dans sa colonne sans
# que personne ait à y penser.

COLUMN_QUICK = "quick"
COLUMN_LONGER = "longer"
COLUMN_CSV = "csv"

SETUP_COLUMN_ORDER: tuple[str, ...] = (COLUMN_QUICK, COLUMN_LONGER, COLUMN_CSV)


def column_of(pv: "PlatformValue") -> str:
    """La colonne d'une plateforme — une seule règle, lue depuis ses champs."""
    if pv.where == CSV:
        return COLUMN_CSV
    return COLUMN_QUICK if pv.recommended else COLUMN_LONGER


def setup_columns(
    connected: set[str] | None = None,
) -> dict[str, list[PlatformValue]]:
    """Les trois groupes, chacun déjà trié comme `ordered_for_setup`.

    Renvoie toujours les trois clés, même vides : un rendu qui compte les colonnes
    ne doit pas changer de largeur parce qu'un artiste a tout connecté d'un côté.
    """
    groups: dict[str, list[PlatformValue]] = {c: [] for c in SETUP_COLUMN_ORDER}
    for pv in ordered_for_setup(connected):
        groups[column_of(pv)].append(pv)
    return groups

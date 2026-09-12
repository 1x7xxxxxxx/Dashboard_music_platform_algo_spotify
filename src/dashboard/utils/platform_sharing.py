"""Quelles plateformes exigent un PARTAGE d'accès en plus d'un identifiant valide.

Type: Sub
Uses: rien
Depends on: rien
Persists in: nothing

Pourquoi ce module existe
-------------------------
Le fait lui-même : sur Meta, un identifiant de compte publicitaire parfaitement
valide ne suffit pas — sans partage du compte à l'app, l'appel rend
`(#3) capability` et aucune donnée n'arrive. La matrice d'état doit donc le montrer,
et `_registry.PLATFORMS` le déclarait déjà à côté des champs de la plateforme.

Ce qui a changé le 2026-09-12, et pourquoi c'est ici : `status_matrix._requires_sharing`
lisait ce booléen en important `views.credentials._registry`. Mesuré — **1 950 ms**,
parce que le paquet `credentials/__init__.py` tire son routeur et que `_registry`
tire les quatre modules de test de connexion (spotipy, googleapiclient, le SDK Meta).
Et `render_status_matrix` est rendu **sur l'accueil** pour tout artiste dont la mise
en route n'est pas finie, c'est-à-dire tout nouvel arrivant, pour un budget de page
de 287 ms.

C'est le frère de `csv_platforms.py`, trouvé le même jour par le garde qui capitalise
ce défaut (`tests/test_a_shared_path_does_not_drag_a_view_behind_it.py`). Même forme,
même remède : la DONNÉE descend dans un module partagé, et la vue la lit — jamais une
seconde copie, jamais l'utilitaire qui monte vers la vue.

⚠️ Une seule liste. `_registry.PLATFORMS` lit ce module et n'écrit plus le drapeau
lui-même ; `tests/test_the_sharing_flag_has_one_home.py` refuse la seconde copie.
"""
from __future__ import annotations

# Clés LOGIQUES de plateforme exigeant un partage d'accès explicite.
#
# Une liste, pas un `if key == "meta"` dans le rendu : la mise en page clavée sur
# une liste tapée à la main est une forme que ce dépôt a déjà payée
# (`layout-keyed-by-a-hand-written-list`), et elle devient muette le jour où une
# seconde plateforme rejoint le cas.
REQUIRES_SHARING: frozenset[str] = frozenset({"meta"})


def requires_sharing(platform_key: str) -> bool:
    """Cette plateforme exige-t-elle un partage en plus de son identifiant ?"""
    return platform_key in REQUIRES_SHARING

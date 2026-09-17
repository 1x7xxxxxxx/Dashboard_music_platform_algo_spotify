"""Une plateforme qui n'a pas de sonde garde son indice STATIQUE pour toujours.

Type: Test
Uses: ast
Depends on: src/utils/artist_readiness.py, src/dashboard/views/credentials/_registry.py
Persists in: nothing

`next_action` fait `live_reason or platform["nodata_hint"]` (`artist_readiness.py:120`) :
la mesure remplace la devinette. Mais `platform_probes.probe` dispatche par
`CONNECTION_TESTS.get(logical_platform)` et rend `None` quand la clé manque — donc une
plateforme absente de `CONNECTION_TESTS` retombe sur son indice statique **en silence**,
sans qu'aucune surface ne dise que personne n'a demandé.

C'est exactement ce que la classe `static-hint-contradicts-the-live-probe` a coûté :
le SoundCloud d'un bêta-testeur s'est vu répondre « vérifie le User ID ; l'app partagée
doit être configurée (admin) » pendant des SEMAINES, alors qu'un seul appel d'API
répondait « ce profil n'a aucun titre public ». La devinette était plausible, fausse, et
envoyait chercher le mauvais geste.

Ce que ce garde ajoute
----------------------
Le remède a été appliqué aux cinq plateformes d'alors, et **rien ne dit qu'une sixième
l'aura**. Les deux ensembles sont écrits dans deux fichiers différents, par deux
personnes à deux moments, et leur désaccord est invisible : l'indice s'affiche, il a
l'air d'une réponse, il ne dit pas qu'il est une supposition.

Balayé le 2026-09-18 : les deux ensembles portent les mêmes 5 clés (`instagram`, `meta`,
`soundcloud`, `spotify`, `youtube`). Ce fichier fige cet accord.

Ce qu'il ne couvre PAS
----------------------
La JUSTESSE d'une sonde — qu'elle existe ne dit pas qu'elle répond vrai. Et le sens
inverse est délibérément toléré : une entrée de `CONNECTION_TESTS` sans plateforme de
readiness est un test de connexion pour une surface qui n'affiche pas de statut, ce qui
ne trompe personne.

Mutation record — 2026-09-18 : en retirant `'instagram'` de `CONNECTION_TESTS`, ce
garde le nomme ; remis, il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_READINESS = _ROOT / "src" / "utils" / "artist_readiness.py"
_REGISTRY = _ROOT / "src" / "dashboard" / "views" / "credentials" / "_registry.py"


def _readiness_keys() -> set[str]:
    """Les clés de `_PLATFORMS`, lues à l'AST — pas importées.

    L'import tirerait Streamlit et une connexion ; ce fichier doit rester collectable
    sans eux (`test_a_test_file_is_collectable_without_what_it_watches`).
    """
    tree = ast.parse(_READINESS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "_PLATFORMS" for t in node.targets)):
            continue
        out = set()
        for elt in getattr(node.value, "elts", []):
            if not isinstance(elt, ast.Dict):
                continue
            for k, v in zip(elt.keys, elt.values):
                if (isinstance(k, ast.Constant) and k.value == "key"
                        and isinstance(v, ast.Constant)):
                    out.add(v.value)
        return out
    return set()


def _probed_keys() -> set[str]:
    tree = ast.parse(_REGISTRY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "CONNECTION_TESTS" for t in node.targets)
                and isinstance(node.value, ast.Dict)):
            return {k.value for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return set()


def test_both_sets_are_readable() -> None:
    """Anti-vacuité : deux ensembles vides sont d'accord, et ne prouvent rien."""
    readiness, probed = _readiness_keys(), _probed_keys()
    assert len(readiness) >= 5, (
        f"seulement {len(readiness)} plateforme(s) lues dans `_PLATFORMS` — il y en "
        "avait 5 le 2026-09-18. Le lecteur AST est cassé.")
    assert len(probed) >= 5, (
        f"seulement {len(probed)} entrée(s) lues dans `CONNECTION_TESTS` — il y en "
        "avait 5 le 2026-09-18. Le lecteur AST est cassé.")


def test_no_platform_shows_a_guess_when_nobody_can_ask() -> None:
    manquantes = sorted(_readiness_keys() - _probed_keys())
    assert not manquantes, (
        f"{manquantes} affichent un statut à l'artiste et n'ont AUCUNE sonde dans "
        "`CONNECTION_TESTS`.\n"
        "`platform_probes.probe` rend `None` pour elles, donc `next_action` retombe "
        "sur `nodata_hint` — une supposition présentée comme une réponse, sans que "
        "rien ne dise que personne n'a demandé.\n"
        "C'est ce qui a envoyé un bêta-testeur vérifier un User ID pendant des "
        "semaines alors que son profil n'avait aucun titre public.\n"
        "Remède : une entrée dans `CONNECTION_TESTS`, ou retirer la plateforme du "
        "tableau de statut tant qu'on ne peut pas lui répondre.")

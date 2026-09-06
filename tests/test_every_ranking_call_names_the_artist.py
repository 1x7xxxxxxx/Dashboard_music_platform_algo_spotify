"""Guard: tout appel de production au moteur de rapprochement nomme l'artiste.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `a-scoring-call-that-omits-its-context`.

SoundCloud et YouTube préfixent le nom de l'artiste au titre
(« 1x7xxxxxxx - Kimono À Semelle De Fer »). Depuis que l'inclusion est pondérée par
la couverture — elle rendait un 0,90 plat quel que soit le bruit, donc au-dessus du
seuil d'auto-acceptation de 0,80 — ce nom compte comme un mot du titre s'il n'est
pas déclaré.

Mesuré le 2026-09-06 en écrivant ce correctif : sans `noise_tokens`, la couverture
tombe à 5/6 et le score à **0,75**, sous le seuil. Le rapprochement continue
d'exister, il cesse simplement d'être proposé tout seul — une dégradation qu'aucune
exception ne signale et qu'aucun test de rendu ne voit.

C'est la contrepartie exacte du contrat posé dans
`test_track_mapping_suggest.test_title_similarity_containment_artist_prefix` : la
fonction est délibérément moins sûre sans le nom, donc la production doit toujours
le donner. Ce garde est ce qui rend ce « toujours » vérifiable.
"""
from __future__ import annotations

import ast
import functools
import pathlib

import pytest

_SRC = pathlib.Path("src")
_RANKERS = {"rank_track_candidates", "rank_campaign_candidates"}


@functools.lru_cache(maxsize=1)
def _call_sites() -> list[tuple[str, int, str, ast.Call]]:
    """(fichier, ligne, nom appelé, nœud) pour chaque appel aux moteurs, sous src/."""
    found = []
    for path in sorted(_SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — le hook ruff l'attrape avant
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in _RANKERS):
                found.append((str(path), node.lineno, node.func.id, node))
    return found


def test_the_rankers_are_actually_called_somewhere():
    """Sans site d'appel, ce garde serait vert en ne mesurant rien."""
    sites = _call_sites()
    assert len(sites) >= 2, (
        f"seulement {len(sites)} appel(s) aux moteurs de rapprochement sous src/ — "
        "soit ils ont été renommés, soit ce garde regarde au mauvais endroit."
    )


@pytest.mark.parametrize(
    "site", _call_sites(), ids=[f"{p}:{ln}:{fn}" for p, ln, fn, _ in _call_sites()])
def test_a_ranking_call_declares_the_artist_noise(site):
    path, lineno, fname, node = site
    passed = {kw.arg for kw in node.keywords}
    assert "noise_tokens" in passed, (
        f"{path}:{lineno} appelle `{fname}` sans `noise_tokens`. Le nom de "
        "l'artiste comptera comme un mot du titre : mesuré, le score d'un titre "
        "SoundCloud tombe de 1,00 à 0,75, sous le seuil d'auto-acceptation de "
        "0,80. La suggestion cesse d'être proposée toute seule, sans erreur et "
        "sans que rien ne l'affiche. Passe `_artist_noise(db, artist_id)`."
    )

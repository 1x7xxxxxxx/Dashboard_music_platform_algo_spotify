"""Le catalogue écrit `guard:` de DEUX façons ; le générateur doit lire les deux.

Type: Utility
Uses: tools/dev/error_class_health.py
Triggers: pytest
Persists in: nothing

Error class `a-parser-that-knows-one-of-two-syntaxes`.

Mesuré le 2026-09-17. `_guard_path()` ne lisait que la forme structurée :

    - guard: { type: pytest, ref: tests/x.py }     365 classes — lue
    - guard: tests/x.py — explication               10 classes — rendue `aucun` / `None`

**Neuf classes nomment ainsi un garde parfaitement réel**, dont
`cumulative-counter-drawn-as-its-own-history`, qui pointe un fichier de 15 tests verts.

Trois conséquences, toutes silencieuses :

  * `automatic_guard` sous-comptait de **huit** (358 au lieu de 366) ;
  * `guards_ref_missing` valait 0 **sans avoir jamais vérifié ces neuf chemins** — un
    compteur à zéro parce qu'il ne regarde pas est indiscernable d'un compteur à zéro
    parce que tout va bien ;
  * et une portée de classe a été écrite en se fiant au champ DÉRIVÉ plutôt qu'à
    l'entrée : « aucun garde automatique », sur une classe dont la même entrée porte
    `status: guarded`, `kind: deterministic`, une `signature:` et un `guard:`. Un
    `code-critic` l'a réfutée en exécutant les 15 tests.

## La forme minoritaire est celle qu'on oublie

10 sur 376. C'est exactement pourquoi elle est passée : un parseur écrit en regardant
le catalogue voit la forme dominante, et la variante ne se manifeste que par un champ
qui vaut sa valeur par défaut — `aucun`, qui est aussi une réponse légitime.

**Une valeur par défaut qui coïncide avec une réponse valable rend le défaut muet.**

Mutation record — 2026-09-17, vue rouge : `_GUARD_BARE` neutralisé → ce test nomme les
classes retombées à `None` ; remis, vert. Seconde mutation, celle qui compte :
`_type_from_path` rendu constant `"aucun"` → le CHEMIN est trouvé mais le type reste
faux, donc `guard_automatic` reste False — **corriger la moitié d'un parseur laisse le
compteur faux, et il est alors plus difficile à soupçonner qu'avant.**
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CATALOGUE = REPO / ".claude" / "dev-docs" / "error-classes.md"


def _health():
    spec = importlib.util.spec_from_file_location(
        "_health", REPO / "tools" / "dev" / "error_class_health.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _guard_lines() -> dict[str, str]:
    """`{classe: valeur du champ guard}` pour chaque entrée du catalogue."""
    text = CATALOGUE.read_text(encoding="utf-8")
    out = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        cid = block.splitlines()[0].strip()
        m = re.search(r"^- guard: (.*)$", block, re.M)
        if m:
            out[cid] = m.group(1).strip()
    return out


def test_both_forms_are_present_in_the_catalogue() -> None:
    """Non-vacuité : si la forme nue disparaissait, ce garde ne prouverait plus rien."""
    lines = _guard_lines()
    braced = [v for v in lines.values() if v.startswith("{")]
    bare = [v for v in lines.values()
            if not v.startswith(("{", "—", "-", "aucun", "none"))]
    assert len(braced) >= 300, f"seulement {len(braced)} gardes en forme structurée"
    assert len(bare) >= 5, (
        f"seulement {len(bare)} gardes en forme NUE — si elle a disparu du catalogue, "
        "ce test ne garde plus rien et doit être retiré, pas laissé vert")


def test_every_bare_guard_that_names_a_path_is_parsed() -> None:
    """La forme nue qui nomme un fichier doit rendre ce fichier, jamais None."""
    health = _health()
    missed = []
    for cid, value in _guard_lines().items():
        # ⚠️ Un champ qui COMMENCE par `—` déclare AUCUN garde, quelle que soit la prose
        # qui suit : `- guard: — (procédure humaine, `tools/.../README.md`)` nomme un
        # document de contexte, pas un garde. Ma première version le dénonçait parce
        # qu'elle cherchait un `/` n'importe où dans la valeur — le chemin entre
        # parenthèses suffisait. Un garde qui lit « y a-t-il un slash quelque part »
        # au lieu de « qu'est-ce que ce champ DÉCLARE » rend un faux positif sur la
        # seule entrée qui dit honnêtement qu'elle n'a rien.
        if value.startswith(("{", "—", "-", "aucun", "none")) or "/" not in value:
            continue
        if health._guard_path(value) is None:
            missed.append(f"{cid} → {value[:60]}")
    assert not missed, (
        "ces classes nomment un garde que le générateur ne voit pas :\n  "
        + "\n  ".join(missed)
        + "\n\nElles seront comptées comme non gardées, et `guards_ref_missing` ne "
          "vérifiera jamais que leur fichier existe.")


@pytest.mark.parametrize("value,expected", [
    ("tests/test_x.py — une explication", "pytest"),
    ("`.claude/hooks/lint_x.py` (règle 2)", "hook"),
    (".claude/scripts/audit_x.py", "error-class-signature"),
    ("{ type: pytest, ref: tests/y.py }", "pytest"),
])
def test_the_type_is_derived_not_left_at_its_default(value, expected) -> None:
    """Trouver le chemin sans corriger le TYPE laisse `guard_automatic` faux.

    C'est la moitié du correctif que j'ai failli livrer seule, et la plus dangereuse :
    le compteur bouge un peu, donc il a l'air réparé.
    """
    health = _health()
    if value.startswith("{"):
        kind = re.search(r"type:\s*([\w-]+)", value).group(1)
    else:
        kind = health._type_from_path(health._guard_path(value))
    assert kind == expected, f"{value!r} → {kind!r}, attendu {expected!r}"
    assert health._is_automatic(kind), (
        f"{kind!r} n'est pas compté comme automatique — `automatic_guard` sous-compte")

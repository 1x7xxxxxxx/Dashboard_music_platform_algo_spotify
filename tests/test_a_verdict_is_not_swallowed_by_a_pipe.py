"""Un verdict tubé dans un filtre ne peut pas précéder une livraison sur un `&&`.

Type: Test
Uses: .claude/hooks/guard_destructive
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing

Le défaut, mesuré le 2026-09-17 sur cette ligne exacte :

    pytest … -q 2>&1 | tail -3 && git add -A && git commit … && git push

La suite était ROUGE. `tail` a rendu 0, le `&&` a laissé passer, et le rouge est parti
sur `main` — le texte de l'échec était pourtant affiché dans la sortie de la même
commande. **Un tube rend le code du DERNIER étage**, jamais celui de l'étage qui portait
le verdict.

Mutation record — 2026-09-17, trois mutations jouées, **une rouge et DEUX VERTES**, et
ce sont les deux vertes qui ont appris quelque chose :
  1. s'arrêter au premier lien qui n'est pas `&&`   → **ROUGE** (8 échecs) : le garde
     s'arrêtait au tube lui-même et ne voyait jamais la livraison.
  2. remplacer `shlex` par un découpage du TEXTE    → **verte**, et c'était juste : ce
     n'est pas `shlex` qui protège de la prose, c'est la lecture de la TÊTE de l'étage
     (`_tete`). La mutation ne visait pas le bon organe.
  3. retirer l'exemption `pipefail`                 → **verte**, et ce vert était un
     DÉFAUT : `shlex.split` rendait `pipefail;` en un seul jeton, donc le `;` n'était
     jamais un opérateur — la forme passait pour une raison qui n'était pas la bonne.
     Même cause pour `make test|tail -3&&git commit`, sans espaces, qui **échappait
     entièrement au garde**. Corrigé par `punctuation_chars=True`, et le cas sans
     espaces est entré dans `_FAUTIVES`.

⚠️ La leçon est celle-ci, et elle n'était pas visible en relisant : **une mutation qui
passe au vert ne prouve pas que le garde tient — elle peut viser le mauvais organe, ou
révéler que le garde passait déjà pour une mauvaise raison.** Les deux cas se sont
produits ici, dans la même série de trois.

Les trois REJOUÉES sur le garde corrigé, le même jour : **9, 2 et 1 échecs** — les trois
rouges. Ce n'est pas la même série : c'est la série d'après, sur un garde que la première
avait fait changer.

---
rex: []
---
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude" / "hooks" / "guard_destructive.py"


def _hook():
    spec = importlib.util.spec_from_file_location("_guard_destructive", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Un verdict tubé, PUIS une livraison sur un `&&` : la livraison prétend dépendre d'un
# verdict que le shell a jeté.
_FAUTIVES = [
    "pytest tests/x.py -q 2>&1 | tail -3 && git add -A && git commit -m x",
    "make test 2>&1 | tail -5 && git push origin main",
    ".venv/bin/python -m pytest tests/x.py -q | tail -3 && git commit -m x",
    "make test | tee /tmp/o && git push",
    'pytest tests/ -q | grep -E "passed|failed" | tail -1 && git commit -m x',
    "ruff check src/ | tail -2 && gh pr create --fill",
    # ⚠️ SANS ESPACES autour des opérateurs. Cette forme passait au VERT jusqu'au
    # 2026-09-17 : `shlex.split` coupe sur les blancs, donc elle lui rendait
    # `['make','test|tail','-3&&git', …]` et le garde ne voyait aucun opérateur.
    # Trouvée en mutant — deux mutations sur trois sont d'abord passées vertes, et
    # c'est ce vert-là qui a révélé le trou, pas une relecture.
    "make test|tail -3&&git commit -m x",
]

# Ce que le garde ne doit PAS bloquer — c'est ce qui le rend tenable.
_SAINES = [
    # lire une sortie longue, sans rien livrer derrière : le geste normal
    "pytest tests/x.py -q 2>&1 | tail -3",
    # livrer sans prétendre vérifier
    "git add -A && git commit -m x && git push",
    # le code de sortie est réparé
    "set -o pipefail; pytest tests/x.py -q | tail -3 && git commit -m x",
    # `;` n'affirme aucune dépendance
    "pytest tests/x.py -q | tail -3 ; git commit -m x",
    # `||` non plus, et dans l'autre sens
    "make test | tail -3 || git commit -m x",
    # l'étage de gauche ne porte aucun verdict
    "grep -n x f.py | tail -3 && git commit -m y",
    "git log --oneline | head -3 && git push",
]


@pytest.mark.parametrize("command", _FAUTIVES)
def test_a_swallowed_verdict_before_a_delivery_is_blocked(command: str) -> None:
    assert _hook()._verdict_swallowed_by_a_pipe(command) is not None, command


@pytest.mark.parametrize("command", _SAINES)
def test_the_safe_forms_stay_allowed(command: str) -> None:
    assert _hook()._verdict_swallowed_by_a_pipe(command) is None, command


def test_writing_about_the_gesture_is_not_the_gesture() -> None:
    """Le garde lit la STRUCTURE : les marques dans un argument n'en sont pas.

    Ce dépôt a payé trois commandes bloquées d'affilée le 2026-09-12, toutes en train de
    DOCUMENTER le geste. Le garde neuf est tenu au même standard que les anciens.
    """
    prose = 'echo "pytest | tail && git commit est un piege"'
    assert _hook()._verdict_swallowed_by_a_pipe(prose) is None


def test_the_detector_is_not_vacuous() -> None:
    """Un garde qui ne trouve jamais rien passe aussi tous les tests négatifs."""
    hook = _hook()
    trouvees = [c for c in _FAUTIVES if hook._verdict_swallowed_by_a_pipe(c)]
    assert len(trouvees) == len(_FAUTIVES)


def test_the_block_message_names_the_three_safe_forms() -> None:
    """Un garde qui arrête le travail sans dire par quoi le remplacer coûte plus qu'il
    ne protège — la leçon de `a-blocking-hook-that-writes-its-reason-to-stdout`."""
    verdict = _hook().check_command(
        "pytest tests/x.py -q 2>&1 | tail -3 && git commit -m x")
    assert verdict is not None
    level, message = verdict
    assert level == "block"
    for aide in ("pipefail", "`;`", "second appel"):
        assert aide in message, aide

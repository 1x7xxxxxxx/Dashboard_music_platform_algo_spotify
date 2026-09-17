"""Deux préconditions qui gardent la même chose la lisent au même endroit.

Type: Test
Uses: re
Depends on: Makefile
Persists in: nothing

Le défaut
---------
`check-db` lit `DATABASE_URL` et en déduit hôte et port. `check-env` codait
`127.0.0.1:5433` **en dur**. Sur une machine où la base écoute ailleurs, `make dashboard`
échouait sur sa précondition pendant que `make error-inbox` passait — **même question,
deux vérités**. `deux-surfaces-deux-nombres`, appliqué à un port.

Trouvé le 2026-09-17 en auditant les refus du dépôt sous une question :
**« ce critère peut-il être faux dans l'usage prévu ? »** Sur cinq refus lus, deux
défauts et trois sains — `check-db`, `check-guide-deps` et la partie imports de
`check-env` EXERCENT vraiment ce qu'ils vérifient (socket ouverte, `import` réel).

⚠️ Ce garde ne vérifie pas que les deux cibles se comportent pareil à l'exécution —
il vérifie qu'aucune ne code l'adresse en dur là où l'autre lit l'environnement. La
preuve d'exécution a été faite à la main : `DATABASE_URL` pointant un port mort fait
refuser les DEUX, et sans lui les deux passent.
"""
from __future__ import annotations

import re
from pathlib import Path

_MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"

# Les cibles qui décident si la base applicative est joignable.
_DB_PRECONDITIONS = ("check-db", "check-env")


def _recipe(name: str) -> str:
    r"""Le corps d'une cible, CONTINUATIONS COMPRISES.

    ⚠️ La première version cherchait `(?:\t.*\n)+` — des lignes indentées par une
    tabulation. Mais une commande shell coupée par `\` continue en **colonne 0** :

        \t@python3 -c "import os,sys,socket;\\
        u=os.environ.get('DATABASE_URL');\\

    Le motif s'arrêtait donc à la première ligne, et les deux cibles paraissaient ne
    pas lire `DATABASE_URL` — y compris celle qui le lit. Un garde qui lit la structure
    doit lire la structure RÉELLE, pas celle qu'on imagine.
    """
    lines = _MAKEFILE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.startswith(f"{name}:")), None)
    assert start is not None, f"la cible `{name}` a disparu du Makefile"
    body, continuing = [], False
    for ln in lines[start + 1:]:
        if ln.startswith("\t"):
            body.append(ln)
            continuing = ln.rstrip().endswith("\\")
            continue
        if continuing:                      # continuation en colonne 0
            body.append(ln)
            continuing = ln.rstrip().endswith("\\")
            continue
        if not ln.strip():                  # ligne vide tolérée dans une recette
            body.append(ln)
            continue
        break                               # une autre cible commence
    return "\n".join(body)


def test_both_preconditions_still_exist() -> None:
    """Non-vacuité : si l'une disparaît, ce test ne compare plus rien."""
    for name in _DB_PRECONDITIONS:
        assert _recipe(name).strip(), f"`{name}` n'a plus de recette"


def test_no_db_precondition_hardcodes_the_address() -> None:
    """Aucune ne décide de la joignabilité sur une adresse écrite en dur."""
    offenders = []
    for name in _DB_PRECONDITIONS:
        recipe = _recipe(name)
        # Les lignes de COMMENTAIRE (`@#`) sont exclues : ce Makefile documente le
        # défaut dans la cible elle-même, et écrire sur un défaut ne doit pas le
        # déclencher — trois commandes bloquées pour cette raison le 2026-09-12.
        code = "\n".join(ln for ln in recipe.splitlines()
                         if not ln.strip().startswith("@#"))
        if "DATABASE_URL" not in code:
            offenders.append(
                f"`{name}` ne lit pas DATABASE_URL — elle décide sur une adresse fixe")
    assert not offenders, (
        "\n  ".join(offenders) + "\n\n"
        "Deux préconditions de la MÊME chose doivent la lire au même endroit. "
        "Jusqu'au 2026-09-17, `check-env` codait `127.0.0.1:5433` pendant que "
        "`check-db` lisait l'environnement : sur une base qui écoute ailleurs, "
        "`make dashboard` refusait et `make error-inbox` passait.")


def test_a_target_that_only_reports_says_so_in_its_help() -> None:
    """Un nom ne promet pas une vérification que la recette ne fait pas.

    L'aide de `check-env` disait « Verify … pip dep coherence » alors que la ligne
    `pip check` se termine par `|| true` : elle imprime et continue, TOUJOURS. C'est
    délibéré — `pip check` remonte des conflits transitifs qu'on ne corrigera pas tous
    — mais ce n'était écrit nulle part, et un nom qui promet ce qu'il ne fait pas est
    ce qui fait cesser de chercher.
    """
    body = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^check-env:\s*##\s*(.+)$", body, re.M)
    assert m, "`check-env` n'a plus de ligne d'aide"
    help_line = m.group(1).lower()
    recipe = _recipe("check-env")
    tolerant = "|| true" in recipe
    if tolerant:
        assert any(w in help_line for w in ("rapport", "report", "non bloquant",
                                            "non-bloquant", "seulement")),  (
            f"la recette de `check-env` contient `|| true` — donc une partie ne peut "
            f"pas échouer — mais son aide ne le dit pas : {m.group(1)!r}")

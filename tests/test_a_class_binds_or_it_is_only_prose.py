"""Une classe d'erreur ne retient rien tant que quelque chose la REJOUE tout seul.

Type: Test
Uses: re, pathlib
Depends on: .claude/dev-docs/error-classes.md
Persists in: nothing

Ce qui a été mesuré, et pourquoi ce cliquet existe
---------------------------------------------------
Le 2026-09-16, ce catalogue portait **366 classes**, dont 94 % avec un garde qui
s'exécute seul. La question n'est pas combien il y
en a, c'est lesquelles ont empêché une récidive. La journée a donné les deux moitiés de
la réponse, sans ambiguïté :

**Ont mordu — toutes avaient un garde qui tourne seul.** Huit gardes automatiques ont
attrapé un défaut ce jour-là, dont QUATRE sur le travail écrit dans la même séance : un
fragment qui capturait une connexion fermée (défaut de production vieux de semaines), une
duplication de roadmap commise deux fois, un dixième site qu'un balayage `grep` avait
manqué, et un `pytest tests/` en série bloqué au moment du geste.

**N'ont rien empêché — la connaissance était de la prose.**
* `a-kill-pattern-that-matches-its-own-shell` : écrite le 2026-09-12, AVEC son hook, et
  reproduite **trois fois** le 2026-09-16. Le hook gardait le verbe `pkill` ; la cause
  était le motif qui se contient lui-même, et `pgrep` la partageait. **La portée du garde
  était le défaut, pas la connaissance.**
* La leçon sur le wrapper RTK qui avale la sortie de `grep` vivait dans une mémoire de
  projet. Elle n'a atteint aucun geste : quatre conclusions fausses en ont découlé, dont
  un hook entier écrit, testé, puis supprimé.

La règle qu'on en tire, et que ce fichier tient
------------------------------------------------
**Une classe vaut par la DISTANCE entre l'endroit où la leçon est écrite et l'endroit où
le geste se produit.** Trois rangs, mesurés :

  1. un hook au moment du geste — a mordu ;
  2. un test dans la suite — a mordu huit fois ;
  3. de la prose dans un document ou une mémoire — n'a rien retenu, trois fois.

Le catalogue peut grossir ; ce qui ne doit pas grossir, c'est la part du rang 3. Ce test
ne demande donc pas que toute classe ait un garde — certaines ne peuvent pas en avoir, et
`/capitalise` dit explicitement qu'une signature jamais vue rouge vaut moins qu'aucune.
Il demande que **la proportion de prose ne monte jamais**.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CATALOGUE = _ROOT / ".claude" / "dev-docs" / "error-classes.md"

# Les types de garde qui s'exécutent SANS que personne y pense.
# ⚠️ Compare par SOUS-CHAINE, pas par egalite. La premiere version listait des valeurs
# exactes et comptait `pretooluse-hook`, `posttooluse-hook`, `pre-commit` et
# `error-class-signature` comme de la PROSE — dix faux positifs, sur des gardes qui
# s'executent vraiment. Un cliquet qui se trompe sur la moitie de sa population fait
# corriger les mauvaises entrees.
_AUTOMATIC_MARKS = ("pytest", "hook", "ci", "test", "ratchet", "make", "script",
                    "signature", "commit", "cross")
_PROSE_MARKS = ("doc", "aucun", "manual", "ops")


def _is_automatic(kind: str) -> bool:
    k = kind.lower()
    if any(m in k for m in _PROSE_MARKS):
        return False
    return any(m in k for m in _AUTOMATIC_MARKS)

# Gelé le 2026-09-16 : **18 classes sur 363 (5 %)** sans garde automatique. Ce nombre ne
# peut que BAISSER — écrire un garde pour l'une d'elles, ou retirer une classe devenue
# fausse ; les deux sont des progrès.
#
# ⚠️ La première mesure annonçait 110 (30 %), et elle était FAUSSE : la comparaison se
# faisait par égalité, donc `pretooluse-hook`, `pre-commit` et `error-class-signature`
# étaient comptés comme de la prose. Dix faux positifs. Un cliquet qui se trompe sur la
# moitié de sa population fait corriger les mauvaises entrées — et j'ai annoncé le
# chiffre faux avant de le vérifier.
# 18 → 10 le 2026-09-17, même cause : huit classes gardées étaient comptées comme
# prose seule parce que leur `guard:` est écrit en forme nue. Le dépôt n'a pas changé,
# la mesure oui.
_PROSE_CEILING = 10


# Les en-têtes qui ne sont PAS des classes. Ils ressemblent à des classes à un
# découpage sur `## `, et les compter gonflait la population de trois.
_NOT_A_CLASS = re.compile(r"^[a-z0-9][a-z0-9-]+$")


def _guard_kind(block: str) -> str:
    r"""Le TYPE de garde d'une entrée — les DEUX syntaxes, via la règle unique.

    ⚠️ Ce fichier lisait `^- guard: \{ type: ([\w-]+)` et rien d'autre jusqu'au
    2026-09-17. Le catalogue écrit `guard:` de deux façons, et la forme NUE —
    `- guard: tests/x.py — explication` — retombait donc sur `aucun`.

    C'est l'instance FRÈRE de `a-parser-that-knows-one-of-two-syntaxes`, trouvée en
    balayant après le correctif du générateur : **huit classes gardées étaient comptées
    comme prose seule** (18 au lieu de 10), et les « menteuses » — celles qui se
    déclarent `guarded` sans garde automatique — en contenaient autant à tort.

    La règle est IMPORTÉE, pas recopiée. Une troisième copie divergerait comme les deux
    premières : le générateur de santé a exactement le même besoin, et `error-classes.md`
    n'a pas à être compris de trois façons.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_health_rules", _ROOT / "tools" / "dev" / "error_class_health.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    m = re.search(r"^- guard: (.*)$", block, re.M)
    if not m:
        return "aucun"
    value = m.group(1).strip()
    braced = re.match(r"\{ type: ([\w-]+)", value)
    if braced:
        return braced.group(1)
    return mod._type_from_path(mod._guard_path(value))



def _classes() -> list[tuple[str, str]]:
    """(nom, type de garde) pour chaque classe du catalogue.

    ⚠️ Le filtre kebab-case n'est pas cosmétique. La première version prenait tout
    en-tête `## …`, donc `Contract`, `Per-class schema` et `CLASS-ID` — qui n'ont pas de
    ligne `guard:` et étaient donc comptés comme de la **prose**. Le plafond gelé le
    2026-09-16 valait 21 pour cette raison ; la vraie mesure est 18.

    Découvert par `tests/test_the_error_class_health_only_improves.py`, dont le rôle est
    précisément de refuser que deux lecteurs d'un même fichier divergent. Il a mordu sur
    le cliquet écrit six heures plus tôt, et c'est exactement ce qu'on lui demande.
    """
    text = _CATALOGUE.read_text(encoding="utf-8")
    out = []
    for block in re.split(r"\n## ", text)[1:]:
        name = (block.split("\n", 1)[0].strip().split() or [""])[0]
        if not _NOT_A_CLASS.match(name) or name == "class-id":
            continue
        out.append((name, _guard_kind(block)))
    return out


def test_the_share_of_prose_only_classes_never_grows() -> None:
    classes = _classes()
    assert len(classes) >= 300, (
        f"{len(classes)} classes lues — la lecture du catalogue est cassée, et ce "
        "cliquet serait vert à vide.")

    prose = [n for n, g in classes if not _is_automatic(g)]
    assert len(prose) <= _PROSE_CEILING, (
        f"{len(prose)} classes sans garde automatique, contre un plafond de "
        f"{_PROSE_CEILING}.\n\n"
        "Une classe dont la connaissance vit dans un document ne retient rien : mesuré "
        "le 2026-09-16, `a-kill-pattern-that-matches-its-own-shell` a été reproduite "
        "TROIS fois alors qu'elle était écrite ET munie d'un hook — parce que le hook "
        "gardait le verbe et pas le geste.\n"
        "Écrire un garde pour l'une des classes de prose, ou retirer une classe devenue "
        "fausse. Les deux font baisser ce nombre ; en ajouter une de plus sans garde, "
        "non.\n"
        f"Nouvelles : {sorted(prose)[-3:]}")


def test_a_guarded_class_names_a_guard_that_runs() -> None:
    """`status: guarded` doit correspondre à un garde AUTOMATIQUE, pas à une intention.

    Une classe qui se déclare gardée en nommant un document se lit comme une protection
    et n'en est pas une. C'est la forme `a-gate-that-can-never-be-green` appliquée au
    catalogue lui-même : on croit couvert ce qui ne l'est pas, donc on ne cherche plus.
    """
    text = _CATALOGUE.read_text(encoding="utf-8")
    liars = []
    for block in re.split(r"\n## ", text)[1:]:
        name = block.split("\n", 1)[0].strip()
        if not re.search(r"^- status: guarded\s*$", block, re.M):
            continue
        kind = _guard_kind(block)
        if not _is_automatic(kind):
            liars.append(f"{name} → guard de type `{kind}`")

    # Gelé à la MESURE du 2026-09-16 (8), pas à une estimation. Ne peut que baisser.
    # 8 → 2 le 2026-09-17, et **aucune classe n'a été corrigée pour ça** : c'est le
    # LECTEUR qui était faux. Il ne connaissait qu'une des deux syntaxes de `guard:`,
    # donc six classes parfaitement gardées étaient accusées de mentir. Une accusation
    # portée par un compteur faux est pire qu'un compteur absent — on corrige ce qui
    # n'est pas cassé, et on apprend à ignorer le rouge.
    assert len(liars) <= 2, (
        f"{len(liars)} classes se déclarent `guarded` sans garde qui s'exécute :\n  "
        + "\n  ".join(sorted(liars)[:10])
        + "\n\nSoit le statut descend (`reported`), soit le garde devient un test ou un "
          "hook. Se déclarer protégé sans l'être est pire que de ne rien déclarer : on "
          "cesse de chercher.")


def test_the_reader_is_not_fooled_by_a_missing_guard_line() -> None:
    """Non-vacuité : une classe sans ligne `guard:` compte comme PROSE, pas comme absente."""
    sample = "\n## x-sans-garde\n- status: reported\n- kind: manual\n"
    blocks = re.split(r"\n## ", sample)[1:]
    assert blocks, "le découpage du catalogue ne rend plus aucun bloc"
    m = re.search(r"^- guard: \{ type: ([\w-]+)", blocks[0], re.M)
    assert m is None, "une classe sans `guard:` doit être vue comme telle"
    assert not _is_automatic("aucun") and not _is_automatic("doc"), (
        "`aucun` ou `doc` compte désormais comme un garde automatique : toute classe "
        "sans protection passerait pour protégée, et ce cliquet ne mesurerait plus rien.")
    assert _is_automatic("pretooluse-hook") and _is_automatic("pytest"), (
        "un type de garde réel n'est plus reconnu — dix faux positifs étaient dus à une "
        "comparaison par égalité le 2026-09-16.")

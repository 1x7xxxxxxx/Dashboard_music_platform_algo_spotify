"""Une cible `make` ne s'attribue pas une barriere qu'elle ne tient pas.

Type: Sub
Uses: pathlib, re
Triggers: pytest
Depends on: Makefile, tests/
Persists in: —

Error class `a-make-target-that-claims-a-barrier-it-does-not-hold`.

Le defaut, mesure le 2026-09-17
--------------------------------
Trois cibles — `gold-coverage-check`, `error-families-check`, `error-health-check` —
portaient la mention « (CI) » dans leur ligne d'aide. Verifie par `grep` sur
`.github/workflows/` et `.pre-commit-config.yaml` : **zero occurrence**. Aucun workflow
ne les lance.

Ce n'etait pas un trou de couverture — les documents SONT gardes, par des tests pytest
qui tournent sous `make test` et donc en CI. C'etait une erreur sur le MECANISME, et
c'est ce qui la rend couteuse : un lecteur qui croit que la cible `make` est la barriere
peut supprimer le test pytest en pensant qu'il fait doublon. Le document resterait alors
garde par une cible que personne ne lance.

Ce que ce garde exige
---------------------
Une ligne d'aide qui nomme un fichier `tests/…py` le nomme correctement : le fichier
existe. On ne verifie pas la mention « (CI) » elle-meme — une cible PEUT legitimement
etre lancee par un workflow, et l'exiger dans un sens ou dans l'autre figerait un choix.
Ce qui se verifie, c'est qu'un renvoi vers un garde ne pointe pas dans le vide.

⚠️ Ce garde lit la ligne de DECLARATION de la cible (`nom: ## texte`), pas le fichier
entier : la prose du Makefile parle legitimement de tests qui n'existent plus, au passe.
"""

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_HELP = re.compile(r"^([a-zA-Z0-9_.-]+):.*?##\s*(.+)$")
_TEST_REF = re.compile(r"tests/[A-Za-z0-9_./-]+\.py")


def _help_lines() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in (_ROOT / "Makefile").read_text(encoding="utf-8").splitlines():
        m = _HELP.match(line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def test_a_help_line_that_names_a_guard_names_one_that_exists():
    """Un renvoi vers un test, depuis l'aide d'une cible, pointe un fichier reel."""
    lines = _help_lines()
    assert lines, "Makefile no longer exposes `##` help lines — this guard reads those."

    referenced = [
        (target, ref)
        for target, text in lines
        for ref in _TEST_REF.findall(text)
    ]
    assert referenced, (
        "No make help line points at a guard any more. That may be legitimate, but this "
        "test then proves nothing — say so here rather than leaving a green no-op."
    )

    for target, ref in referenced:
        assert (_ROOT / ref).exists(), (
            f"Makefile target `{target}` tells the reader its barrier is `{ref}`, which "
            f"does not exist. A help line that names the wrong mechanism is worse than "
            f"one that names none: le 2026-09-17, trois cibles annoncaient « (CI) » "
            f"alors qu'aucun workflow ne les lance, et le vrai garde etait un test qu'on "
            f"pouvait supprimer en le croyant redondant."
        )


def test_the_three_document_checks_point_at_their_real_guard():
    """Les trois cibles de fraicheur nomment le test qui bloque REELLEMENT.

    Mutation record — 2026-09-17, mutation EXECUTEE et vue rouge : le nom du test de
    `error-health-check` remplace par `tests/test_nexiste_pas.py` dans sa ligne d'aide
    → exit 1 sur les deux tests de ce fichier ; 0 apres remise en etat.

    Ces trois-la sont nommees explicitement parce que ce sont elles qui portaient la
    mention fausse. Le test precedent couvre la forme ; celui-ci couvre le cas.
    """
    # DEUX BARRIERES ONT DEMENAGE LE 2026-09-18, ET CE TEST A ETE LE PREMIER A LE DIRE.
    #
    # `gold-coverage-check` et `error-health-check` etaient tenues par un test pytest qui
    # REGENERAIT le document entier pour le comparer octet a octet — 23,06 s et 6,97 s,
    # soit 30,0 s de la suite pour deux assertions. Les deux tests sont retires et les
    # deux cibles sont desormais lancees par `.github/workflows/ci.yml`.
    #
    # Le contrat de ce test ne change pas d'un iota : une ligne d'aide nomme le mecanisme
    # qui bloque REELLEMENT, et ce mecanisme doit exister. Seule la NATURE du mecanisme
    # change — un pas de workflow au lieu d'un fichier de test — donc on verifie que le
    # workflow appelle bien la commande, pas seulement qu'il porte le mot « CI ».
    par_workflow = {
        "gold-coverage-check": "tools/dev/gold_coverage.py --check",
        "error-health-check": "tools/dev/error_class_health.py --check",
    }
    par_pytest = {
        "error-families-check": "tests/test_the_error_class_families_only_improve.py",
    }
    seen = dict(_help_lines())
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    for target, guard in par_pytest.items():
        assert target in seen, f"make target `{target}` disappeared from the help index."
        assert guard in seen[target], (
            f"`{target}` no longer names `{guard}` as what blocks. If the barrier moved, "
            f"update both the help line and this expectation together — they exist to "
            f"disagree loudly rather than drift quietly."
        )
        assert (_ROOT / guard).exists(), f"{guard} named by `{target}` is gone."

    for target, commande in par_workflow.items():
        assert target in seen, f"make target `{target}` disappeared from the help index."
        assert "CI" in seen[target], (
            f"`{target}` ne dit plus que son blocage vient de la CI. Si la barriere a "
            f"redemenage, mettre a jour la ligne d'aide ET cette attente ensemble.")
        assert commande in ci, (
            f"`{target}` annonce etre lancee en CI, et `.github/workflows/ci.yml` "
            f"n'appelle pas `{commande}`. C'est exactement la mention fausse que ce "
            f"fichier existe pour interdire : le 2026-09-17, trois cibles annoncaient "
            f"« (CI) » alors qu'aucun workflow ne les lancait.")
        assert (_ROOT / commande.split()[0]).exists(), (
            f"la CI appelle `{commande}`, dont le script n'existe pas.")

"""Les shards se répartissent sur des DURÉES, pas sur un nombre de tests.

Type: Test
Uses: pytest, ast, json
Depends on: .test_durations, tests/render_harness.py, .github/workflows/ci.yml
Persists in: nothing

Ce qui est en jeu — mesuré le 2026-09-16
-----------------------------------------
La CI découpe la suite en quatre groupes avec `pytest-split --splits 4`. Sans
`.test_durations`, la découpe se fait sur le NOMBRE de tests, et ici ce serait
gravement déséquilibré : la suite pèse 907 s en série, dont **172,6 s pour le seul
`test_views_render_smoke.py`** (19 %) et 82,6 s pour `test_a_render_opens_one_connection.py`.
Un rendu `AppTest` coûte mille fois un garde AST.

Avec le fichier de durées, les quatre shards ont tenu 64 / 92 / 100 / 106 s au premier
run réel. C'est la différence entre un mur de 109 s et un mur dicté par le plus gros
groupe.

Ce fichier pose deux questions, et aucune n'est « le fichier existe-t-il »
---------------------------------------------------------------------------
1. **Le fichier de durées décrit-il encore CETTE suite ?** Il se périme par
   construction : chaque fichier de tests neuf y est absent, et `pytest-split` lui
   attribue alors une durée moyenne — ce qui redéséquilibre en silence. Le plafond
   ci-dessous n'est pas une limite morale, c'est le moment où il faut relancer
   `make test-durations`.
2. **La liste des vues rendues est-elle écrite UNE fois ?** Elle vivait en double et a
   divergé neuf jours (voir `tests/render_harness.py`). Deux copies qui doivent
   s'accorder finissent par ne plus s'accorder ; une seule ne le peut pas.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TESTS = _ROOT / "tests"
_DURATIONS = _ROOT / ".test_durations"

# Combien de fichiers de tests peuvent manquer au fichier de durées avant que la
# découpe cesse d'être fiable. Gelé le 2026-09-16 à 6, sur 369 fichiers — un fichier
# neuf par jour de travail, ce qui laisse une semaine avant de régénérer.
# CE NOMBRE NE MONTE PAS : au-delà, la commande est `make test-durations`.
#
# Mutation vérifiée le 2026-09-16 : abaissé à -1, le test est VU ROUGE en nommant les
# fichiers sans durée connue ; remis à 6, il repasse. Un cliquet jamais vu rouge ne
# garde rien, et celui-ci garde un fichier qui se périme tout seul.
_MAX_FILES_WITHOUT_DURATION = 6


def _files_with_durations() -> set[str]:
    data = json.loads(_DURATIONS.read_text(encoding="utf-8"))
    return {k.split("::", 1)[0] for k in data}


def test_the_durations_file_still_describes_this_suite() -> None:
    assert _DURATIONS.is_file(), (
        "`.test_durations` a disparu. `pytest-split` répartirait alors sur le NOMBRE "
        "de tests, et `test_views_render_smoke.py` (172,6 s, 19 % de la suite) "
        "tomberait entier dans un shard. Remède : `make test-durations`."
    )
    known = _files_with_durations()
    present = {
        str(p.relative_to(_ROOT)).replace("\\", "/")
        for p in _TESTS.glob("test_*.py")
    }
    missing = sorted(present - known)
    assert len(missing) <= _MAX_FILES_WITHOUT_DURATION, (
        f"{len(missing)} fichier(s) de tests n'ont aucune durée connue, contre un "
        f"plafond de {_MAX_FILES_WITHOUT_DURATION}. `pytest-split` leur donne une durée "
        "MOYENNE, ce qui redéséquilibre les shards en silence.\n"
        "Remède : `make test-durations` (puis commiter `.test_durations`).\n  "
        + "\n  ".join(missing)
    )


def test_the_ceiling_is_not_vacuous() -> None:
    """Non-vacuité : le prédicat doit voir de vrais fichiers des deux côtés."""
    known = _files_with_durations()
    assert len(known) > 300, (
        f"seulement {len(known)} fichiers dans `.test_durations` — soit il a été "
        "tronqué, soit la lecture est cassée. Dans les deux cas le test d'à côté ne "
        "garde plus rien."
    )
    present = {str(p.relative_to(_ROOT)).replace("\\", "/") for p in _TESTS.glob("test_*.py")}
    assert len(present) > 300, f"seulement {len(present)} fichiers de tests trouvés"
    assert known & present, "aucun recouvrement : les chemins ne sont pas comparables"


# ── La liste des vues, écrite une fois ───────────────────────────────────────

def _declares_a_view_list(path: Path) -> list[str]:
    """Les constantes de ce fichier qui RECOPIENT une liste du harnais, à l'identique.

    Structurel : on lit l'AST et on demande « cette liste est-elle, EN TANT
    QU'ENSEMBLE, l'une de celles du harnais ? ». Un commentaire qui cite `VIEWS` ne
    compte pas, ni une variable locale dans une fonction.

    **Le prédicat a d'abord été trop large**, et c'est instructif : il flaggait toute
    liste faite majoritairement de noms de vues connus, donc il a attrapé deux
    SOUS-ENSEMBLES légitimes — les vues qui lisent de la donnée scopée (22) et celles
    qui doivent montrer quelque chose (11). Ce ne sont pas des copies : ce sont trois
    questions différentes. La duplication qu'on combat est l'IDENTITÉ, pas la parenté.
    """
    from tests.render_harness import EMPTY_TENANT_VIEWS, VIEWS
    catalogue = [set(VIEWS), set(EMPTY_TENANT_VIEWS)]
    out = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return out
    for node in tree.body:                        # niveau module uniquement
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        if not isinstance(value, list) or len(value) < 5:
            continue
        if not all(isinstance(x, str) for x in value):
            continue
        if set(value) in catalogue:
            out.append(getattr(node.targets[0], "id", "?"))
    return out


def test_the_list_of_rendered_views_is_written_once() -> None:
    """Deux copies qui doivent s'accorder finissent par ne plus s'accorder."""
    offenders = []
    for path in sorted(_TESTS.glob("test_*.py")):
        for name in _declares_a_view_list(path):
            offenders.append(f"{path.name} → {name}")
    assert not offenders, (
        "ces fichiers re-déclarent la liste des vues rendues au lieu de l'importer "
        "de `tests/render_harness.py`.\n"
        "Elle a déjà vécu en double, et les deux copies ont divergé NEUF JOURS : le "
        "script levait à l'import, le rendu ouvrait zéro connexion, et `0 <= 1` "
        "passait — un garde vert sur deux vues qui n'existaient plus.\n  "
        + "\n  ".join(offenders)
    )


def test_the_view_list_detector_can_actually_see_one() -> None:
    """Non-vacuité : sans elle, un détecteur cassé rendrait le test ci-dessus vert."""
    import tempfile
    from tests.render_harness import VIEWS
    with tempfile.TemporaryDirectory() as d:
        fake = Path(d) / "test_fake.py"
        fake.write_text("MES_VUES = " + repr(list(VIEWS)) + "\n", encoding="utf-8")
        assert _declares_a_view_list(fake) == ["MES_VUES"], (
            "le détecteur ne voit pas une liste de vues re-déclarée : il ne garde rien"
        )
        fake.write_text("X = ['a', 'b', 'c', 'd', 'e', 'f']\n", encoding="utf-8")
        assert _declares_a_view_list(fake) == [], (
            "le détecteur prend une liste quelconque pour une copie du harnais"
        )
        # Et un SOUS-ENSEMBLE légitime ne doit pas être pris pour une copie : c'est
        # exactement ce que la première version faisait, sur deux fichiers justes.
        fake.write_text("SOUS = " + repr(list(VIEWS)[:11]) + "\n", encoding="utf-8")
        assert _declares_a_view_list(fake) == [], (
            "un sous-ensemble de vues est pris pour une copie — le prédicat est trop large"
        )

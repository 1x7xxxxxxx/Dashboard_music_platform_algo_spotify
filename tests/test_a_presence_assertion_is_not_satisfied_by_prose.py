"""Un garde ne doit pas être VERT grâce au commentaire du fichier qu'il inspecte.

Type: Test
Uses: ast, .claude/scripts/audit_presence_assertions.py
Depends on: tests/code_text.py
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
`assert "<mot>" in fichier.read_text()` ne distingue pas le code de la prose du
fichier visé. Trois défauts ENTIERS ont été remis en place sans faire rougir leur
garde, chacun trouvé en cherchant à dater un `seen_red`, pas en cherchant un bug :

* `pd.to_datetime(values, utc=True)` → `pd.to_datetime(values)` — `utils/tz.py`
  nomme `utc=True` quatre fois dans ses docstrings. Classe **P1**
  `timestamptz-parsed-across-a-dst-change`, et ses six tests sont restés verts.
* `PostgresHandler.from_env_or_config()` → un DSN bâti à la main — le fichier nomme
  la méthode deux fois de plus en prose. Cinq tests verts.
* `WITH linked AS MATERIALIZED (` → `WITH linked AS (` — le mot vit dans le
  commentaire qui explique pourquoi la CTE est matérialisée. Seize tests verts.

Et deux assertions étaient **déjà vertes à vide** : le mot ne vivait PLUS que dans
un commentaire, donc elles n'affirmaient rien sur le code depuis un moment.

C'est `guard-matches-its-own-comment` retourné. Là-bas le garde rougit sur sa prose
et on le corrige dans l'heure ; ici il verdit GRÂCE à elle et rien ne le dit jamais.
Classe `guard-satisfied-by-its-own-comment`.

Le remède n'est pas de bannir les assertions de présence — elles répondent à de
vraies questions — mais de leur faire lire `tests/code_text.code_of(chemin)`. Quand
c'est la présence d'un COMMENTAIRE qui est le sujet, l'exemption est nommée dans le
balayage, avec sa raison.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_AUDIT = ROOT / ".claude" / "scripts" / "audit_presence_assertions.py"


def _module():
    spec = importlib.util.spec_from_file_location("audit_presence", _AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_presence_assertion_is_satisfiable_by_the_prose_it_inspects() -> None:
    """Le cliquet : zéro, et il ne peut pas remonter sans qu'on le voie."""
    found = _module().proven()
    assert not found, (
        f"{len(found)} assertion(s) de présence tiendraient encore une fois le CODE "
        "retiré du fichier qu'elles inspectent :\n  "
        + "\n  ".join(
            f"{name}:{lineno}  {literal!r} -> {target}"
            f"  ({'verte dès que le code part' if in_code else 'DÉJÀ verte à vide'})"
            for name, lineno, literal, target, in_code in found)
        + "\n\nLire `tests.code_text.code_of(<chemin>)` au lieu de "
        "`<chemin>.read_text()`. Si c'est bien la présence d'un COMMENTAIRE qui est "
        "gardée, l'ajouter à `EXEMPTES` dans le balayage AVEC sa raison.")


def test_the_reader_keeps_the_code_and_drops_only_the_prose(tmp_path: Path) -> None:
    """Non-vacuité : `code_of` doit retirer la prose ET préserver le reste.

    Les deux moitiés, et la seconde a été payée : une première version joignait les
    jetons par des sauts de ligne, donc `from src.utils import x` devenait
    `from\\nsrc\\n.\\nutils…` et TOUTE assertion portant une phrase de plusieurs mots
    cessait de matcher. Trois gardes sont passés au rouge sur du code correct. Un
    faux positif coûte autant qu'un faux négatif.
    """
    from tests.code_text import code_of

    sujet = tmp_path / "sujet.py"
    sujet.write_text(
        '"""Ce module appelle from_env_or_config, disait la docstring."""\n'
        "# et le commentaire nomme utc=True\n"
        "from src.utils.central_apps import check_meta\n"
        "\n"
        "def door():\n"
        '    """Delegates to from_env_or_config."""\n'
        "    return PostgresHandler.from_env_or_config()\n",
        encoding="utf-8",
    )
    code = code_of(sujet)
    assert code.count("from_env_or_config") == 1, (
        f"`code_of` rend {code.count('from_env_or_config')} occurrence(s) au lieu "
        "d'une seule : la prose n'est pas retirée, donc un garde resterait vert "
        "après suppression du seul appel réel.")
    assert "utc=True" not in code, "un commentaire survit à `code_of`"
    assert "from src.utils.central_apps import check_meta" in code, (
        "une phrase de plusieurs mots ne survit pas à `code_of` : l'adjacence des "
        "jetons est détruite, et tout garde qui cherche un import complet rougirait "
        "sur du code parfaitement correct.")

    # LE MARKDOWN N'EST PAS DU CODE COMMENTÉ — mesuré le 2026-09-18, quelques heures
    # après la livraison de ce module. `#` y est un TITRE et `--` une séparation de
    # tableau ; les retirer faisait déclarer « prose seule » toute assertion portant
    # sur un en-tête de document. Un faux positif de l'outil anti-faux-positif, qui a
    # bloqué la CI sur une assertion parfaitement légitime.
    md = tmp_path / "doc.md"
    md.write_text("# Ce que le biais valait\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
                  encoding="utf-8")
    assert "Ce que le biais valait" in code_of(md), (
        "un TITRE Markdown est retiré comme s'il était un commentaire : toute "
        "assertion sur un en-tête de document serait déclarée non gardée.")
    assert "|---|---|" in code_of(md), (
        "la ligne de séparation d'un tableau Markdown est prise pour un commentaire "
        "SQL — un document rendu ne peut alors plus être gardé sur sa structure.")

    # Et le fichier NON-Python : le commentaire SQL part, la requête reste.
    sql = tmp_path / "v.sql"
    sql.write_text(
        "-- MATERIALIZED, et c'est mesuré : inlinée, la CTE coûte deux minutes.\n"
        "WITH linked AS MATERIALIZED (SELECT 1);\n",
        encoding="utf-8",
    )
    assert code_of(sql).count("MATERIALIZED") == 1, (
        "le commentaire SQL survit : c'est exactement le site qui a laissé seize "
        "tests verts sur une CTE inlinée.")


def test_the_scope_is_not_empty() -> None:
    """Sans candidats, le cliquet à zéro ne prouverait rien."""
    mod = _module()
    assert len(mod.sites()) >= 50, (
        f"seulement {len(mod.sites())} assertion(s) de présence trouvée(s) — le "
        "balayage ne lit plus les tests, et le contrôle d'à côté est vert sur du vide.")
    assert mod.EXEMPTES, (
        "aucune exemption nommée : soit le dépôt n'en a plus, soit la liste a été "
        "vidée pour faire taire le balayage. Les deux se disent, l'un des deux se "
        "vérifie en lisant les tests cités.")


def test_every_named_exemption_still_exists() -> None:
    """Une exemption qui ne désigne plus rien est une porte ouverte qu'on croit fermée."""
    for fichier, nom in _module().EXEMPTES:
        chemin = ROOT / "tests" / fichier
        assert chemin.exists(), f"l'exemption nomme {fichier}, qui n'existe plus"
        tree = ast.parse(chemin.read_text(encoding="utf-8"))
        noms = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert nom in noms, (
            f"l'exemption nomme {fichier}::{nom}, qui n'y est plus. Une exemption "
            "périmée dispense un test qui n'existe pas, et masque celui qui a pris "
            "sa place.")

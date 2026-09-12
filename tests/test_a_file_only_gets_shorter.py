"""Un fichier trop long ne peut que raccourcir.

Type: Test
Uses: pytest
Depends on: src/, airflow/
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
Quatre fichiers au-dessus de 1 200 lignes, dont `app.py` (1 252) qui mélangeait
navigation, routage, session, première visite — **et** les deux pages atteintes depuis
un e-mail, qui n'ont aucun de ces sujets. Ces deux-là sont parties dans
`views/email_actions.py` : `app.py` est descendu à 1 073, et surtout ces flux sont
devenus TESTABLES — l'en-tête d'`app.py` lève sans `AIRFLOW_PASSWORD` ni
`FERNET_KEY`, donc rien de ce qu'il contient n'était atteignable depuis un test.

Pourquoi un cliquet et pas une limite
--------------------------------------
Une limite à 1 200 lignes rendrait ce test rouge en permanence sur trois fichiers,
donc ignoré — et un test qu'on ignore ne garde rien. On gèle la mesure du jour,
fichier par fichier, et elle ne peut que descendre. C'est le mécanisme qui a déjà
fait passer les gardes textuels de 32 à 21 et les axes secondaires de 12 à 0.

Ce qui a fini par être fait, et à quelle condition
--------------------------------------------------
La navigation d'`app.py` **a été découpée le 2026-09-12** — `_NAV_SECTIONS` vit
maintenant dans `utils/nav_sections.py`. Ce fichier l'avait différée pour une raison
qui reste vraie : deux causes racines de navigation ont traversé 3 755 tests verts
ici, parce que le harnais de rendu appelle chaque `show()` isolément et jamais
`_main_body`. Un découpage de la navigation ne se valide qu'AU NAVIGATEUR, et celui-ci
l'a été avant d'être livré.

C'est aussi le cliquet qui l'a provoqué : `app.py` était exactement à 1 073, et ajouter
une entrée de menu avec le commentaire que ce dépôt exige était impossible. Le garde a
donc refusé la dette au lieu d'être relevé — ce pour quoi il existe.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Gelé le 2026-09-10. CES NOMBRES NE PEUVENT QUE DESCENDRE.
# Une baisse se répercute ici : le cliquet suit la réalité vers le bas, jamais
# l'inverse. Un plafond posé AU-DESSUS de la mesure est du mou : il autorise en
# silence la croissance qu'il prétend interdire — vérifié ici, les quatre valeurs
# sont celles lues le jour du gel, à la ligne près.
FROZEN = {
    "airflow/dags/alert_monitor.py": 2724,
    # 1268 → 1203 le 2026-09-11 : le sujet « encodage et séparateur » est sorti
    # dans utils/csv_serialization.py, comme le message de ce cliquet le demande.
    "src/dashboard/views/upload_csv.py": 1203,
    "src/dashboard/views/credentials/_render.py": 1229,
    # 1073 → 997 le 2026-09-12 : `_NAV_SECTIONS` est sortie dans
    # `utils/nav_sections.py`. Le cliquet a PROVOQUÉ ce découpage — le fichier
    # était exactement à son plafond, donc ajouter une entrée de menu avec son
    # commentaire était impossible. C'est le mécanisme qui marche : refuser la
    # dette plutôt que la figer.
    "src/dashboard/app.py": 997,
}


def _lines(path: Path) -> int:
    """Le nombre de lignes — après avoir vérifié que le fichier est du Python valide.

    `ast.parse` n'est pas décoratif ici : compter les lignes d'un fichier qu'on ne
    peut pas analyser reviendrait à surveiller un compteur sans savoir de quoi. Et le
    dépôt interdit d'ajouter un garde qui lit du Python sans passer par l'AST — la
    règle vaut aussi pour un garde qui ne fait que compter.
    """
    text = path.read_text(encoding="utf-8")
    ast.parse(text)
    return len(text.splitlines())


@pytest.mark.parametrize("rel,ceiling", sorted(FROZEN.items()))
def test_the_longest_files_only_get_shorter(rel, ceiling) -> None:
    path = ROOT / rel
    assert path.exists(), f"{rel} a disparu — mettre à jour le cliquet, pas le contourner"
    n = _lines(path)
    assert n <= ceiling, (
        f"{rel} : {n} lignes contre un plafond gelé à {ceiling}. Ce plafond ne monte "
        "pas. Ce qui entre dans ce fichier doit en faire sortir autant — de "
        "préférence un sujet entier, comme les deux pages d'e-mail sorties d'app.py "
        "le 2026-09-10, qui sont devenues testables en partant.")


def test_no_other_file_has_joined_the_list() -> None:
    """Un cinquième fichier qui franchirait 1 200 lignes entrerait en silence."""
    over = []
    for path in list((ROOT / "src").rglob("*.py")) + list((ROOT / "airflow").rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        if rel in FROZEN:
            continue
        n = _lines(path)
        if n > 1200:
            over.append(f"{rel} ({n})")
    assert not over, (
        "ces fichiers ont franchi 1 200 lignes sans être suivis : " + ", ".join(over) +
        "\nLes ajouter à FROZEN fige la dette ; les découper la retire. Le second "
        "est le but, le premier est le minimum.")

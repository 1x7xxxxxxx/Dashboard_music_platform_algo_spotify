"""Un chiffre produit par un harnais ne circule jamais sans le plancher du harnais.

Type: Test
Uses: pathlib, re
Depends on: tools/, docs/, .claude/dev-docs/, src/
Persists in: nothing

Ce qui a été mesuré
-------------------
2026-09-16. Ce dépôt affirmait dans NEUF fichiers que la barre latérale d'une page
Streamlit pesait « un facteur 8 » de plus que le rendu d'une vue. L'affirmation a
orienté l'ordre du travail de performance (R118 après R120) pendant des semaines.

Elle venait de deux nombres :

* `61 ms` — le rendu d'une VUE, mesuré en Python ;
* `468-538 ms` — une page COMPLÈTE, mesurée **sous `AppTest`**.

Et `tools/loadtest_dashboard.py` documente, **vingt lignes au-dessus du second chiffre**,
le plancher de ce harnais, pris dans le même conteneur le même jour : **352 ms pour
`st.write('hello')`** — deux lignes, pas d'app, pas de base, pas de plotly.

Le plancher n'a jamais été soustrait. Le coût réel de l'application au-dessus du harnais
valait donc ~116-186 ms, pas 468-538. Les chiffres se recollent : `instagram`, mesuré
côté serveur, vaut 12 ms de chrome + 96 ms de vue = **108 ms**.

Ce n'est pas une erreur de calcul, c'est une erreur de LECTURE : les deux nombres étaient
justes, et leur rapport ne voulait rien dire. La mesure serveur a fini par montrer
l'inverse — la chrome est plate à 11-13 ms et la vue va de 50 à 777 ms.

Ce que ce test assert
---------------------
Tout fichier suivi qui cite la valeur de page complète (`468` ou `538`) cite aussi le
plancher (`352`) ou renvoie explicitement à l'addendum qui l'explique. Le chiffre ne peut
plus circuler seul, et un lecteur qui le rencontre voit du même coup ce qu'il faut en
retrancher.

Classe : `a-ratio-between-two-instruments-that-ignores-the-floor-of-one`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# La valeur PRODUITE par le harnais, et le PLANCHER du même harnais.
_FIGURE = ("468", "538")
_FLOOR = "352"
# Un renvoi explicite vaut le plancher : il mène au raisonnement complet.
_POINTERS = ("ADR-026", "addendum", "plancher", "AppTest")


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=_ROOT,
                         capture_output=True, text=True, timeout=60)
    keep = (".py", ".md", ".yml", ".yaml", ".sql", ".sh")
    return [_ROOT / line for line in out.stdout.splitlines()
            if line.endswith(keep) and (_ROOT / line).is_file()]


def test_the_page_figure_never_travels_without_its_floor() -> None:
    offenders = []
    for path in _tracked_text_files():
        # Ce fichier-ci EXPLIQUE la classe : il cite les deux par construction.
        if path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # On ne cherche la paire que là où elle est utilisée comme un temps de rendu.
        if not any(f"{a}-{b}" in text or f"{a} à {b}" in text
                   for a, b in [(_FIGURE[0], _FIGURE[1])]):
            continue
        if _FLOOR in text or any(p in text for p in _POINTERS):
            continue
        offenders.append(str(path.relative_to(_ROOT)))

    assert not offenders, (
        "fichier(s) citant « 468-538 ms » sans son plancher :\n  " + "\n  ".join(offenders)
        + f"\n\nCe nombre est produit SOUS `AppTest`, dont le plancher mesuré vaut "
          f"{_FLOOR} ms pour `st.write('hello')` dans le même conteneur "
          "(`tools/loadtest_dashboard.py:30-33`). Non retranché, il a produit un "
          "« facteur 8 » entre la chrome et la vue qui s'est avéré INVERSE — la chrome "
          "vaut 11-13 ms et la vue 50 à 777 ms.\n"
          "Citer le plancher, ou renvoyer à l'addendum d'ADR-026.")


def test_the_harness_still_documents_its_own_floor() -> None:
    """Non-vacuité, et c'est la moitié qui compte.

    Le test ci-dessus ne vaut que si le plancher est écrit QUELQUE PART. S'il disparaît
    de `loadtest_dashboard.py`, la règle devient inapplicable et le garde vert à vide —
    exactement la situation d'avant, où le chiffre circulait sans son contexte.
    """
    tool = (_ROOT / "tools" / "loadtest_dashboard.py").read_text(encoding="utf-8")
    assert _FLOOR in tool, (
        f"`tools/loadtest_dashboard.py` ne documente plus son plancher de {_FLOOR} ms. "
        "C'est le seul endroit qui permet de lire ses autres chiffres — sans lui, "
        "`468-538 ms` redevient un temps de rendu qu'on peut comparer à n'importe quoi.")
    assert "hello" in tool, (
        "le plancher n'est plus rattaché à ce qui l'a produit (`st.write('hello')`) : "
        "un nombre sans son protocole n'est pas un plancher, c'est une anecdote.")

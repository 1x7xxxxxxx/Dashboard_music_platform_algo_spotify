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

import ast
import io
import subprocess
import tokenize
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# La valeur PRODUITE par le harnais, et le PLANCHER du même harnais.
_FIGURE = ("468", "538")
_FLOOR = "352"
# Un renvoi explicite vaut le plancher : il mène au raisonnement complet.
_POINTERS = ("ADR-026", "addendum", "plancher", "AppTest")

_TEXT_SUFFIXES = (".md", ".yml", ".yaml", ".sql", ".sh")


def _tracked(suffixes: tuple[str, ...]) -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=_ROOT,
                         capture_output=True, text=True, timeout=60)
    return [_ROOT / line for line in out.stdout.splitlines()
            if line.endswith(suffixes) and (_ROOT / line).is_file()]


def _python_prose(path: Path) -> str:
    """Les COMMENTAIRES et DOCSTRINGS d'un fichier Python, **aux bonnes lignes**.

    Rend un texte de même hauteur que le fichier, où chaque ligne porte sa prose et où
    les lignes de pur code sont vides. Les numéros de ligne restent donc ceux du fichier.

    ⚠️ La première version CONCATÉNAIT les docstrings puis les commentaires. Elle lisait
    bien la prose, et elle détruisait la LOCALITÉ : le voisinage de ±15 lignes calculé
    sur ce collage ne correspondait à rien dans le fichier réel, si bien qu'une citation
    ajoutée en fin de fichier se trouvait « expliquée » par un commentaire situé cent
    lignes plus haut. Mutation jouée trois fois avant que le garde ne morde — deux
    placements étaient les miens qui étaient mauvais, le troisième a révélé celui-ci.

    ⚠️ Et c'est de la lecture STRUCTURELLE, pas textuelle : `ast` pour les docstrings,
    `tokenize` pour les commentaires. Un `468-538` dans un littéral ou un nom de variable
    n'affirme rien et ne doit pas déclencher — `tests/test_a_guard_reads_structure_not_text.py`
    a refusé la version qui les confondait.
    """
    raw = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return ""

    out = [""] * (raw.count("\n") + 2)

    def place(start: int, text: str) -> None:
        for offset, piece in enumerate(text.splitlines()):
            k = start + offset
            if 0 <= k < len(out):
                out[k] = piece

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                place(first.lineno - 1, first.value.value)

    try:
        for tok in tokenize.generate_tokens(io.StringIO(raw).readline):
            if tok.type == tokenize.COMMENT:
                place(tok.start[0] - 1, tok.string)
    except (tokenize.TokenError, IndentationError):
        pass
    return "\n".join(out)


# Combien de lignes autour d'une citation comptent comme « à côté ». Quinze : de quoi
# couvrir un paragraphe de commentaire ou une entrée de tableau, pas un fichier entier.
_WINDOW = 15


def _unexplained_citations(text: str) -> list[int]:
    """Les lignes qui citent le chiffre SANS explication à proximité.

    ⚠️ La première version vérifiait par FICHIER : dès qu'un fichier mentionnait
    `AppTest` ou le plancher une seule fois, toutes ses citations étaient blanchies.
    Mutation jouée — ajouter une citation nue dans un commentaire de `src/utils/metrics.py`,
    qui explique déjà la classe ailleurs — le garde est resté VERT. Une vérification
    par fichier bénit ce qui est loin d'elle ; c'est la PROXIMITÉ qui décide si un
    lecteur tombera sur l'explication en lisant la citation.
    """
    a, b = _FIGURE
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if f"{a}-{b}" not in line and f"{a} à {b}" not in line:
            continue
        near = "\n".join(lines[max(0, i - _WINDOW):i + _WINDOW + 1])
        if _FLOOR in near or any(pointer in near for pointer in _POINTERS):
            continue
        out.append(i + 1)
    return out


def test_the_citation_detector_sees_a_bare_figure_and_spares_an_explained_one() -> None:
    """Non-vacuité : le chiffre nu est FABRIQUÉ ici, avec et sans son explication.

    Le balayage ci-dessous est un `assert not offenders` sur tout l'arbre : vert sur
    un dépôt propre ET sur un prédicat qui ne trouve plus rien. La seconde moitié
    compte autant — un garde qui mord sur une citation DÛMENT expliquée rendrait
    impossible d'écrire sur la classe, et la seule issue serait de le désarmer.
    """
    a, b = _FIGURE
    nu = f"Le rendu passe de {a}-{b} ms sous charge.\n"
    assert _unexplained_citations(nu) == [1], (
        f"le détecteur rend {_unexplained_citations(nu)} sur une citation nue du "
        "chiffre : un ratio entre deux instruments repartirait sans son plancher, "
        "et personne ne verrait qu'il n'en a pas.")

    explique = f"{_FLOOR}\nLe rendu passe de {a}-{b} ms sous charge.\n"
    assert _unexplained_citations(explique) == [], (
        "le détecteur mord sur une citation dont l'explication est À CÔTÉ — écrire "
        "sur la classe deviendrait impossible.")

    # Et la leçon que la docstring du prédicat porte déjà : la PROXIMITÉ décide.
    # Une explication à 200 lignes de là ne blanchit rien.
    loin = f"{_FLOOR}\n" + ("\n" * (_WINDOW * 4)) + f"Le rendu passe de {a}-{b} ms.\n"
    assert _unexplained_citations(loin), (
        "une explication située hors de la fenêtre blanchit quand même la citation : "
        "le garde est redevenu une vérification PAR FICHIER, celle qui est restée "
        "verte sur la mutation du 2026-09-17.")


def test_the_page_figure_never_travels_without_its_floor() -> None:
    offenders = []
    me = Path(__file__).name

    for path in _tracked((".py",)):
        if path.name == me:
            continue                      # ce fichier EXPLIQUE la classe
        bad = _unexplained_citations(_python_prose(path))
        if bad:
            offenders.append(f"{path.relative_to(_ROOT)} (prose, ligne(s) {bad})")

    for path in _tracked(_TEXT_SUFFIXES):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        bad = _unexplained_citations(text)
        if bad:
            offenders.append(f"{path.relative_to(_ROOT)} (ligne(s) {bad})")

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

    Lu dans la PROSE du fichier (docstrings + commentaires), pas dans son texte brut :
    un `352` qui apparaîtrait dans un calcul ou une adresse ne documenterait rien, et
    `tests/test_a_guard_reads_structure_not_text.py` a refusé la version qui les
    confondait.
    """
    prose = _python_prose(_ROOT / "tools" / "loadtest_dashboard.py")
    assert _FLOOR in prose, (
        f"`tools/loadtest_dashboard.py` ne documente plus son plancher de {_FLOOR} ms "
        "dans sa prose. C'est le seul endroit qui permet de lire ses autres chiffres — "
        "sans lui, « 468-538 ms » redevient un temps de rendu qu'on peut comparer à "
        "n'importe quoi.")
    assert "hello" in prose, (
        "le plancher n'est plus rattaché à ce qui l'a produit (`st.write('hello')`) : "
        "un nombre sans son protocole n'est pas un plancher, c'est une anecdote.")

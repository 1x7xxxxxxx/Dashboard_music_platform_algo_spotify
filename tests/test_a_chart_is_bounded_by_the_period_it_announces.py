"""Une figure sous un sélecteur de période est bornée par la période qu'elle annonce.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/views/
Persists in: nothing

La question posée (2026-09-10)
------------------------------
« Tu me garantis que mes graphiques sont robustes et sans incohérence avec le sélecteur
de période ? » La réponse honnête était non : **29 vues dessinent des figures, 12 ont un
sélecteur de période, et une seule — l'accueil — avait un garde sur leur cohérence.**

Ce fichier est la moitié mécanisable de cette garantie.

Ce que la mesure a rendu, et les trois faux départs qu'il a fallu jeter
-----------------------------------------------------------------------
Le prédicat s'est trompé **trois fois**, chaque fois en accusant du code juste, et
chaque erreur est gardée ici parce qu'elle reviendra :

1. **Portée de fonction.** Une vue Streamlit est un seul `show()` géant. Chercher « la
   fenêtre est-elle ouverte dans cette fonction ? » a accusé 24 requêtes sur 30 — dont
   les six figures de `spotify_s4a_combined`, alors que sa fenêtre est ouverte **ligne
   281, sous elles**. Une fenêtre ne borne que ce qui vient APRÈS elle : le prédicat
   compare des positions.
2. **Variables dérivées.** `window.start` dépaqueté en `start_d`, `sql_between()`
   dépaqueté en `frag, params` : la borne voyage sous d'autres noms. Il faut la
   clôture transitive des affectations, pas les noms directs.
3. **Bornage en pandas.** `soundcloud.py` lit tout l'historique en SQL — délibérément,
   c'est écrit — et applique la fenêtre par un masque pandas juste après. Un prédicat
   qui ne regarde que le SQL le déclare non borné, à tort.

Après correction : **15 requêtes sous une fenêtre ouverte, 0 figure non bornée.**

Ce que ce garde tient, et ce qu'il ne tient pas
-----------------------------------------------
Il tient : aucune requête placée sous un sélecteur ne peut alimenter une figure sans
que la borne apparaisse, en SQL ou en pandas. Il ne tient pas : que la borne soit
appliquée sur la BONNE colonne — `instagram` filtre sur la date de publication, ce qui
est juste pour une cohorte et faux pour un engagement, et c'est un jugement qu'aucun
prédicat ne rend. Ce cas-là est traité par le texte de la figure, corrigé le même jour.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

_MAKERS = {"smart_period_filter", "period_filter", "entity_period_filter"}
_FETCHERS = {"fetch_df", "fetch_query"}
_DRAWS = re.compile(r"plotly_chart|px\.(bar|line|area|scatter|pie)|st\.(bar|line|area)_chart")

# Gelé le 2026-09-10 : 15 requêtes sous une fenêtre, 0 figure non bornée.
_MAX_UNBOUNDED_FIGURES = 0

# Mutation record — 2026-09-12, et la MOITIÉ QUI A ÉCHOUÉ compte autant.
#
# ✅ Un `st.plotly_chart` ajouté sous la requête non bornée de `instagram.py:230` :
#    le cliquet le nomme et échoue. Il voit donc bien « dessine ET ne borne pas ».
#
# ❌ Retirer `{frag}` de la requête bornée d'`apple_music.py:165` — le défaut réel,
#    celui où l'artiste choisit « 30 jours » et voit tout l'historique — le laisse
#    VERT. Même en remplaçant aussi `window.sql_between("date")` par `"", ()`.
#    La raison est dans `_compares_with` : il cherche un nom de fenêtre dans une
#    comparaison à l'intérieur d'un fragment de 45 lignes, donc il voit la fenêtre
#    LIÉE, pas la fenêtre APPLIQUÉE à la requête. Un `frag` calculé puis non passé
#    lui est invisible.
#
# Écrit ici plutôt que corrigé à chaud : resserrer ce prédicat demande de suivre le
# fragment jusqu'au littéral SQL, ce qui est le même travail que la tranche arrière
# de `tools/dev/gold_coverage.py`. La classe est nommée
# `a-guard-that-sees-the-binding-not-the-application`, et le trou est déclaré plutôt
# que tu.


def _names_in(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            out.add(n.value.id)
    return out


def _window_openings(fn: ast.AST) -> list[tuple[int, set[str]]]:
    """(ligne, variables) de chaque ouverture de fenêtre, transitivement."""
    opens: list[tuple[int, set[str]]] = []
    tainted: set[str] = set()
    for _ in range(6):                       # point fixe
        before = len(tainted)
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assign):
                continue
            from_window = any(
                (getattr(c.func, "attr", None) or getattr(c.func, "id", None))
                in (_MAKERS | {"sql_between"})
                for c in ast.walk(n.value) if isinstance(c, ast.Call))
            if not (from_window or (_names_in(n.value) & tainted)):
                continue
            got: set[str] = set()
            for t in n.targets:
                if isinstance(t, ast.Name):
                    got.add(t.id)
                elif isinstance(t, ast.Tuple):
                    got |= {e.id for e in t.elts if isinstance(e, ast.Name)}
            tainted |= got
            opens.append((n.lineno, got))
        if len(tainted) == before:
            break
    return opens


@lru_cache(maxsize=1)
def _sites() -> list[tuple[bool, bool, str, int, str]]:
    """(bornée, dessine une figure, fichier, ligne, fonction) — sous une fenêtre."""
    found = []
    for path in sorted(VIEWS.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        lines = text.splitlines()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            opens = _window_openings(fn)
            if not opens:
                continue
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                name = (getattr(call.func, "attr", None)
                        or getattr(call.func, "id", None))
                if name not in _FETCHERS or not call.args:
                    continue
                # Seules les fenêtres ouvertes AVANT la requête la concernent.
                avail: set[str] = set()
                for lineno, got in opens:
                    if lineno < call.lineno:
                        avail |= got
                if not avail:
                    continue
                used: set[str] = set()
                for arg in call.args:
                    used |= _names_in(arg)
                bounded = bool(used & avail)
                after = "\n".join(lines[call.lineno - 1:call.lineno + 45])
                if not bounded:
                    # Bornage en PANDAS : la fenêtre appliquée par un masque juste
                    # après la lecture. `soundcloud.py` fait cela délibérément.
                    #
                    # Et il faut une COMPARAISON, pas une mention. Le premier jet
                    # acceptait n'importe quelle occurrence du nom dans les 45 lignes
                    # suivantes — donc `start_d.strftime()` dans le TITRE de la figure
                    # suffisait à la déclarer bornée. C'est exactement le défaut que ce
                    # garde existe pour empêcher : le libellé annonce une période que
                    # les données ne respectent pas.
                    bounded = _compares_with(after, avail)
                found.append((bounded, bool(_DRAWS.search(after)),
                              str(path.relative_to(VIEWS)), call.lineno, fn.name))
    return found


def _compares_with(src: str, window_names: set[str]) -> bool:
    """Une variable de fenêtre entre-t-elle dans une COMPARAISON, ici ?

    Un nom cité dans un `f"…{start_d:%d/%m}…"` de titre ne borne rien. Seule une
    comparaison (`>=`, `<=`, `between`, `<`, `>`) applique la fenêtre aux données.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # Le fragment coupé à 45 lignes n'est pas toujours du Python valide ; on
        # retombe sur une lecture textuelle du même prédicat, jamais sur « présent ».
        return bool(re.search(
            r"(>=|<=|[<>]|\.between\()\s*[^\n]*\b(" + "|".join(map(re.escape, window_names)) + r")\b",
            src)) or bool(re.search(
            r"\b(" + "|".join(map(re.escape, window_names)) + r")\b\s*(>=|<=|[<>])", src))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if _names_in(node) & window_names:
                return True
        if (isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) == "between"
                and _names_in(node) & window_names):
            return True
    return False


def test_no_figure_under_a_period_selector_ignores_it() -> None:
    offenders = [f"{f}:{ln} [{fn}]" for bounded, draws, f, ln, fn in _sites()
                 if draws and not bounded]
    assert len(offenders) <= _MAX_UNBOUNDED_FIGURES, (
        f"{len(offenders)} figure(s) sous un sélecteur de période qui ne la bornent "
        f"ni en SQL ni en pandas : {offenders}\n"
        "L'artiste choisit « 30 jours » et la figure lui montre autre chose, sans que "
        "rien ne le dise. Ce plafond ne monte pas.")


def test_the_predicate_still_sees_queries_under_a_window() -> None:
    """Non-vacuité : un cliquet à zéro doit prouver qu'il regarde quelque chose."""
    sites = _sites()
    assert len(sites) >= 10, (
        f"seulement {len(sites)} requête(s) trouvée(s) sous une fenêtre — il y en "
        "avait 15 le 2026-09-10. Le prédicat est devenu aveugle, et le cliquet à zéro "
        "certifie alors une propriété qu'il ne vérifie plus.")


def test_a_window_opened_below_a_query_does_not_bind_it() -> None:
    """Le faux départ n°1 : la portée de fonction accusait 24 requêtes sur 30."""
    src = (
        "def show():\n"
        "    df = db.fetch_df('SELECT 1')\n"
        "    window = smart_period_filter(db, table='t')\n"
    )
    tree = ast.parse(src)
    fn = tree.body[0]
    opens = _window_openings(fn)
    assert opens, "l'ouverture de fenêtre n'est plus reconnue"
    call = next(n for n in ast.walk(fn)
                if isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "fetch_df")
    above = [ln for ln, _ in opens if ln < call.lineno]
    assert not above, (
        "une fenêtre ouverte SOUS une requête est comptée comme la bornant. C'est le "
        "faux départ qui accusait les six figures de `spotify_s4a_combined`, dont la "
        "fenêtre est ouverte ligne 281, sous elles.")


def test_a_derived_window_variable_still_counts_as_the_window() -> None:
    """Le faux départ n°2 : `window.start` dépaqueté voyage sous un autre nom."""
    src = (
        "def show():\n"
        "    window = smart_period_filter(db, table='t')\n"
        "    start_d, end_d = window.start, window.end\n"
        "    df = db.fetch_df('SELECT 1 WHERE d >= %s', (start_d,))\n"
    )
    fn = ast.parse(src).body[0]
    names = set()
    for _ln, got in _window_openings(fn):
        names |= got
    assert {"start_d", "end_d"} <= names, (
        f"la clôture transitive ne suit plus les variables dérivées : {sorted(names)}. "
        "Sans elle, une requête bornée par `start_d` est déclarée non bornée.")

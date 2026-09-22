"""Une absence ne se prouve que sur une surface PRÉSENTE.

Type: Guard
Uses: ast
Depends on: tests/ (les tests qui rendent une vue par AppTest)
Persists in: nothing

LA PROPRIÉTÉ, ET POURQUOI LA FORME NE SUFFIT PAS
-------------------------------------------------
Un test qui affirme « cette ligne ne s'affiche pas » reste VERT quand la surface
entière s'effondre : un écran vide n'affiche rien, donc il est conforme. Le garde est
mutation-testé, il rougit sur d'autres mutations, et il ne verra jamais celle-là —
classe `a-guard-satisfied-by-the-collapse-it-should-catch`.

L'effondrement n'est pas hypothétique. `render_platform_chart` journalise
« recap metrics unavailable » et rend la figure SANS ses métriques : le 2026-09-12, une
mutation d'une ligne y a fait disparaître CINQ métriques, et l'assertion « la ligne de
variation est absente » est passée. Le harnais mentait, pas le prédicat.

⚠️ CE PRÉDICAT A ÉTÉ FAUX AU PREMIER JET, DANS LES DEUX SENS
-------------------------------------------------------------
Le premier jet cherchait des FORMES d'écriture — `not X`, `X not in Y`, `len(X) == 0`.
Il ratait `assert all("x" not in r for r in rows)`, **et la comptait en ANCRE de
présence** : un seul site de cette forme blanchissait la fonction entière. C'est
exactement `a-sweep-predicate-that-matches-a-form-not-a-property`, commis en écrivant
le garde d'une classe voisine.

Le critère qui tient est une PROPRIÉTÉ décidable :

    vraie-sur-vide  (absence)  →  not X · X not in Y · len(X)==0 · X==[] · all(...)
    fausse-sur-vide (ancre)    →  X in Y · assert X · len(X)>0 · any(...) · len(X)>0

Une fonction est saine dès qu'elle porte UNE assertion fausse-sur-vide, ou un
`next(gen)` sans défaut / un `els[0]` — qui LÈVENT sur un écran vide, donc ancrent sans
être des `assert`. Cette seconde voie n'est pas une indulgence : elle a écarté six des
neuf sites du premier entonnoir (`test_nothing_stands_between_the_title_and_the_first_field`,
dont le `next(...)` lève un `StopIteration` si le formulaire disparaît).

L'ENTONNOIR, mesuré le 2026-09-22
----------------------------------
    26 assertions vraies-sur-vide sous un rendu
    11 fonctions écartées — 10 par une ancre `assert`, 1 par un `next()` sans défaut
     2 fonctions retenues, 3 assertions  →  ANCRÉES le même jour

Et le verdict est MESURÉ, pas déduit : `_flat` rendu stérile, les deux fonctions
restaient VERTES tandis que `test_the_platform_buttons_are_the_first_line_of_the_page`,
ancrée, dans le même fichier, sur le même effondrement, ROUGISSAIT. Le témoin est ce
qui sépare « mon prédicat a raison » de « mon prédicat matche ».

CE QU'IL NE TIENT PAS
---------------------
1. **Un effondrement PARTIEL.** La ligne ancre peut survivre pendant que le bloc visé
   disparaît. Cinq métriques évanouies sous un titre intact satisfont ce garde.
   L'ancre doit viser la surface la PLUS PROCHE de l'absence ; rien ici ne le vérifie.
2. **La justesse de l'ancre.** `assert els` est fausse-sur-vide, donc acceptée, et ne
   prouve rien sur le bloc en question.
3. **Les tests qui n'appellent pas `AppTest`.** Une absence affirmée sur une valeur
   pure ne peut pas s'effondrer : elle est hors sujet, et le filtre le dit.
4. **Le geste voisin le plus proche : une absence affirmée sur une sortie NON rendue
   qui peut quand même être vide** — un `fetch_df` qui rend un DataFrame vide sur une
   panne avalée. Même cause, autre surface, non couvert ici.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TESTS = _ROOT / "tests"

#: Les accesseurs d'une sortie RENDUE. Une fonction qui n'en touche aucun n'affirme
#: rien sur un écran : son absence porte sur une valeur, et une valeur ne s'effondre
#: pas en silence.
_RENDU = frozenset({
    "markdown", "metric", "dataframe", "subheader", "header", "title", "caption",
    "info", "warning", "error", "success", "text", "button", "selectbox", "radio",
    "tabs", "expander", "columns", "table", "json", "checkbox", "multiselect",
    "code", "latex", "divider", "toggle", "text_input", "number_input",
    "date_input", "main", "sidebar",
})

#: ⚠️ CLIQUET À ZÉRO. Toute entrée ici est une absence qu'un écran vide satisfait.
_TOLERES: frozenset[str] = frozenset()


def _vraie_sur_vide(t: ast.expr) -> bool:
    """L'assertion est-elle satisfaite quand la population est VIDE ?"""
    if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
        return True
    if isinstance(t, ast.Compare):
        if any(isinstance(o, ast.NotIn) for o in t.ops):
            return True
        if any(isinstance(o, (ast.Lt, ast.LtE)) for o in t.ops):
            return True
        if any(isinstance(o, ast.Eq) for o in t.ops) and any(
                (isinstance(c, ast.Constant) and c.value in (0, "", False))
                or (isinstance(c, (ast.List, ast.Tuple, ast.Set)) and not c.elts)
                for c in t.comparators):
            return True
    # `all(...)` sur une population vide rend True — la forme qui a échappé au
    # premier jet, ET qu'il comptait en ancre.
    if isinstance(t, ast.Call) and getattr(t.func, "id", None) == "all":
        return True
    if isinstance(t, ast.BoolOp) and isinstance(t.op, ast.And):
        return all(_vraie_sur_vide(v) for v in t.values)
    return False


def _fausse_sur_vide(t: ast.expr) -> bool:
    """L'assertion TOMBE-t-elle si l'écran est vide ? C'est alors une ancre."""
    if _vraie_sur_vide(t):
        return False
    if isinstance(t, ast.Compare):
        return any(isinstance(o, (ast.In, ast.Gt, ast.GtE, ast.Eq)) for o in t.ops)
    if isinstance(t, ast.Call):
        return True
    if isinstance(t, (ast.Name, ast.Attribute, ast.Subscript, ast.ListComp)):
        return True
    if isinstance(t, ast.BoolOp):
        return any(_fausse_sur_vide(v) for v in t.values)
    return False


def _ancre_qui_leve(fn: ast.AST) -> bool:
    """`next(gen)` sans défaut et `els[0]` LÈVENT sur un écran vide."""
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "next"
                and len(n.args) == 1):
            return True
        if (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                and isinstance(n.slice.value, int)):
            return True
    return False


def _entonnoir() -> tuple[int, int, list[str]]:
    bruts, ecartees, sites = 0, 0, []
    for f in sorted(_TESTS.rglob("test_*.py")):
        src = f.read_text(encoding="utf-8")
        if "AppTest" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("test"):
                continue
            if not any(isinstance(n, ast.Attribute) and n.attr in _RENDU
                       for n in ast.walk(fn)):
                continue
            asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
            # `assert not at.exception` contrôle un PLANTAGE, pas une absence de
            # contenu : l'exiger est le contraire du défaut décrit ici.
            absences = [a for a in asserts
                        if _vraie_sur_vide(a.test)
                        and "exception" not in ast.unparse(a.test)]
            if not absences:
                continue
            bruts += len(absences)
            if any(_fausse_sur_vide(a.test) for a in asserts) or _ancre_qui_leve(fn):
                ecartees += 1
                continue
            for a in absences:
                sites.append(f"{f.relative_to(_ROOT)}:{a.lineno} [{fn.name}] "
                             f"{ast.unparse(a.test)[:90]}")
    return bruts, ecartees, sites


def test_the_predicate_still_sees_absence_assertions() -> None:
    """NON-VACUITÉ. Un prédicat qui ne matche plus rien laisse tout passer."""
    bruts, ecartees, _ = _entonnoir()
    assert bruts >= 10, (
        f"seulement {bruts} assertions vraies-sur-vide trouvées sous un rendu (26 le "
        "2026-09-22) : le prédicat a cessé de voir la forme qu'il garde.")
    assert ecartees >= 5, (
        f"seulement {ecartees} fonctions écartées par une ancre — la voie « saine » "
        "du prédicat ne s'emprunte plus, et il est donc devenu aveugle ou trop strict.")


def test_the_predicate_separates_the_two_properties() -> None:
    """Les neuf formes sur lesquelles le premier jet s'est trompé.

    ⚠️ `all(...)` est la première ligne : c'est celle que le jet initial classait à
    la fois « pas une absence » ET « une ancre », soit deux fois faux.
    """
    cas = [
        ('assert all("x" not in r for r in rows)', True),
        ("assert not rules", True),
        ('assert "x" not in joined', True),
        ("assert len(rows) == 0", True),
        ("assert rows == []", True),
        ('assert any("x" in r for r in rows)', False),
        ('assert "x" in joined', False),
        ("assert rows", False),
        ("assert len(rows) > 0", False),
    ]
    for code, attendu in cas:
        t = ast.parse(code).body[0].test          # type: ignore[attr-defined]
        assert _vraie_sur_vide(t) is attendu, (
            f"`{code}` classée {'absence' if not attendu else 'ancre'} — le prédicat "
            "cherche une forme d'écriture au lieu de la propriété « vraie sur vide ».")
        if not attendu:
            assert _fausse_sur_vide(t), f"`{code}` n'est plus reconnue comme ancre"


def test_no_absence_is_asserted_on_a_surface_that_may_be_empty() -> None:
    """LE CLIQUET. Zéro, et le zéro est mesuré — deux sites l'ont violé.

    Les deux corrigés le 2026-09-22 vivaient dans
    `tests/test_the_choice_comes_before_the_form.py` et restaient VERTS avec `_flat`
    rendu stérile, pendant qu'une fonction ancrée du même fichier rougissait.
    """
    _bruts, _ec, sites = _entonnoir()
    restants = [s for s in sites if s.split(" [")[0] not in _TOLERES]
    assert not restants, (
        f"{len(restants)} assertion(s) d'absence sans ancre de présence :\n"
        + "\n".join(f"    {s}" for s in restants)
        + "\n\nChacune est VRAIE sur un écran vide, donc satisfaite par l'effondrement "
          "qu'elle devrait attraper. Ajouter d'abord une assertion FAUSSE sur vide — "
          "`assert any(... in ...)`, `assert els`, `assert len(x) > 0` — visant la "
          "surface la plus proche de l'absence. Un `next(gen)` sans défaut ancre "
          "aussi : il lève sur un écran vide.")

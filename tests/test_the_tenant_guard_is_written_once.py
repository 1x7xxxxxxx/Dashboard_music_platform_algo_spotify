"""Le garde du locataire s'écrit à un seul endroit.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/views/
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
`hypeddit.py` portait un helper `_resolve_artist_id` créé exactement pour ce garde…
et **deux de ses quatre sites l'écrivaient encore à la main**, chacun avec sa propre
version : l'un rendait `(False, "❌ Session invalide.")`, l'autre appelait `st.stop()`
avec une clé de traduction différente. Un helper qui ne couvre que la moitié de ses
sites ne réduit pas la surface, il ajoute une troisième variante.

Pourquoi ce garde-ci, et pas seulement le garde `artist-id-or-1` existant
------------------------------------------------------------------------
Celui qui existe cherche `get_artist_id() or 1` — la forme courte, celle qui a coûté
deux séances de test artiste. Il ne peut pas voir la forme LONGUE, correcte mais
recopiée :

    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin(): ...
        artist_id = 1

Chaque recopie est un endroit de plus où l'un des deux niveaux peut être oublié à la
prochaine édition — et c'est précisément par un `is_admin()` manquant que les données
de l'artiste 1 ont fuité. Septième instance de « la portée d'un garde est le
défaut » : un garde existait, et regardait la forme voisine.

Le cliquet est à ZÉRO parce que la mesure du jour est zéro. Il ne monte pas.
"""
from __future__ import annotations

import ast
from pathlib import Path

VIEWS = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"

# Gelé le 2026-09-10, après passage de 2 à 0. CE NOMBRE NE PEUT QUE DESCENDRE.
#
# Mutation record — 2026-09-12 : un `artist_id = get_artist_id()` suivi d'un
# `if artist_id is None: artist_id = 1` réintroduit en tête de `views/sacem.py`,
# ce cliquet nomme `sacem.py:86` et échoue ; retiré, il passe.
_MAX_OPEN_CODED = 0


def _open_coded_fallbacks() -> list[str]:
    """`if <…artist_id…> is None:` dont le corps repose l'identifiant à 1."""
    sites = []
    for f in sorted(VIEWS.rglob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = ast.dump(node.test)
            if "artist_id" not in test or "NotEq" in test:
                continue
            body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            if "value=1" in body and "artist_id" in body:
                sites.append(f"{f.relative_to(VIEWS)}:{node.lineno}")
    return sites


def test_no_view_rewrites_the_admin_fallback_by_hand() -> None:
    sites = _open_coded_fallbacks()
    assert len(sites) <= _MAX_OPEN_CODED, (
        f"{len(sites)} repli(s) admin réécrit(s) en clair contre un plafond de "
        f"{_MAX_OPEN_CODED} : {sites}\n"
        "Passer par le helper de la vue (`_resolve_artist_id` / "
        "`_resolve_artist_id_or_none`) ou par `view_session()`. Chaque recopie est "
        "un endroit où le contrôle `is_admin()` peut disparaître à la prochaine "
        "édition — c'est par là que les données de l'artiste 1 ont fuité.")


def test_the_predicate_still_sees_the_shape_it_was_written_for() -> None:
    """Non-vacuité : un prédicat qui ne trouve plus rien satisferait le cliquet."""
    probe = ast.parse(
        "artist_id = get_artist_id()\n"
        "if artist_id is None:\n"
        "    if not is_admin():\n"
        "        st.stop()\n"
        "    artist_id = 1\n")
    seen = 0
    for node in ast.walk(probe):
        if not isinstance(node, ast.If):
            continue
        test = ast.dump(node.test)
        if "artist_id" not in test or "NotEq" in test:
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        if "value=1" in body and "artist_id" in body:
            seen += 1
    assert seen == 1, "le prédicat du repli admin est devenu aveugle à sa propre forme"


def test_the_two_hypeddit_helpers_share_one_decision() -> None:
    """Deux réactions, UN garde : sinon on a recréé la duplication au-dessus."""
    src = (VIEWS / "hypeddit.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    stopping = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "_resolve_artist_id")
    calls = {c.func.id for c in ast.walk(stopping)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "_resolve_artist_id_or_none" in calls, (
        "`_resolve_artist_id` ne délègue plus la décision : les deux helpers "
        "portent chacun leur copie du garde, ce que ce fichier existe pour empêcher")

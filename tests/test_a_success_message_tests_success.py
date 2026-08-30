"""
Guard — un message de succès ne s'affiche pas sans avoir testé le succès.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/app.py
Persists in: nothing

Error class: success-message-outside-its-condition.

Mesuré le 2026-08-23, remonté par un artiste en test. Dans
`show_data_collection_panel`, chaque déclenchement de DAG était bien testé
individuellement (`if result.get('success')`), mais le message final vivait **hors de
toute condition** :

        for dag_id, label in COLLECTION_DAGS:
            ...
            else:
                st.error(f"❌ {label} — …")
        st.sidebar.success("Lancé !")        # ← ici, quoi qu'il arrive

Sept échecs affichaient donc sept ❌ **puis** « Lancé ! ». L'artiste retient le dernier
message, et repart attendre des données qui ne viendront jamais.

C'est la même famille que la croix verte de collecte qui ne prouve pas l'arrivée de
données : un message d'état qui ne mesure pas l'état qu'il annonce. Le garde est
structurel — il exige que l'appel soit sous un `if`, ce qu'aucune relecture n'avait
attrapé en deux mois.

Mise à jour du 2026-08-30 — la surface a changé, pas la question
---------------------------------------------------------------
« Lancé ! » n'existe plus du tout : le panneau ne dit plus rien pendant le
déclenchement, et TOUT le résultat descend dans « Collecte en cours », qui survit aux
reruns. Le premier test de ce fichier exigeait la présence de `app.launched` — il est
devenu rouge, ce qui est exactement ce que son propre message demandait de faire
(« mettre ce garde à jour plutôt que de le laisser vert sur rien »).

La question protégée est inchangée : **quand rien n'a démarré, l'artiste doit
l'apprendre**. Ce qui la garantit maintenant, ce n'est plus une branche `else` mais le
fait que les déclenchements REFUSÉS soient mémorisés (`remember_not_launched`) et rendus
(`render_progress`). Un échec qui n'est pas mémorisé disparaît à la fermeture de la
`st.status`, c'est-à-dire aussitôt.
"""

import ast
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py"
_SUCCESS_KEYS = {"app.launched"}


def _tree() -> ast.Module:
    return ast.parse(_APP.read_text(encoding="utf-8"))


def _success_calls(tree: ast.Module) -> list[ast.Call]:
    """Appels `st(.sidebar).success(t("<clé>", ...))` pour les clés surveillées."""
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "success"):
            continue
        for arg in node.args:
            for sub in ast.walk(arg):
                if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                        and sub.value in _SUCCESS_KEYS):
                    out.append(node)
    return out


# Noms qui portent le RÉSULTAT de la boucle. Un `if` qui teste l'un d'eux répond à la
# question « est-ce que ça a marché ? ». Un `if` qui teste `st.button(...)` répond à
# « a-t-on cliqué ? » — ce n'est pas la même question, et c'est toute l'erreur.
_OUTCOME_NAMES = {"launched", "failed", "result", "results", "ok", "succeeded", "errors"}


def _guarded_lines(tree: ast.Module) -> set[int]:
    """Lignes couvertes par un `if` dont le TEST porte sur le résultat.

    Première version de ce prédicat : « la ligne est-elle dans le corps d'un `if` ? ».
    Elle était VERTE sur le défaut qu'elle devait attraper, et seule la mutation l'a dit.
    Le `st.sidebar.success("Lancé !")` fautif vivait déjà dans un `if` — celui du bouton
    `if st.sidebar.button(...)`. Être sous une condition ne suffit donc pas : il faut
    être sous la condition QUI TESTE CE QU'ON ANNONCE.
    """
    covered = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        tested = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if not (tested & _OUTCOME_NAMES):
            continue
        for stmt in node.body:
            covered |= set(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    return covered


def test_no_unconditional_success_survives_in_the_panel():
    """Aucun `success()` non gardé ne doit revenir dans le panneau de collecte."""
    tree = _tree()
    panel = next((n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "show_data_collection_panel"), None)
    assert panel is not None, "show_data_collection_panel a disparu de app.py"

    guarded = _guarded_lines(tree)
    stray = [n.lineno for n in ast.walk(panel)
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "success"
             and n.lineno not in guarded]
    assert not stray, (
        f"ligne(s) {stray} : un message de succès est réapparu dans le panneau de "
        f"collecte sans être sous un `if` qui teste le RÉSULTAT. C'est la forme exacte "
        f"de « Lancé ! » : sept échecs, puis un vert."
    )


def test_the_launch_success_is_inside_a_condition():
    tree = _tree()
    guarded = _guarded_lines(tree)
    stray = [c.lineno for c in _success_calls(tree) if c.lineno not in guarded]
    assert not stray, (
        f"ligne(s) {stray} : « Lancé ! » s'affiche sans condition. Il doit être sous un "
        f"`if` qui teste qu'au moins un déclenchement a réussi — sinon sept échecs "
        f"affichent sept ❌ puis « Lancé ! », et c'est le dernier message que l'artiste "
        f"retient."
    )


def test_a_refused_trigger_is_remembered_and_rendered():
    """Ne rien dire quand tout échoue est le second défaut possible du même correctif.

    Un déclenchement refusé n'a PAS d'identifiant de run : il n'y a donc rien à
    interroger plus tard, et s'il n'est pas mémorisé au moment du clic il n'existe
    nulle part dès que la `st.status` se referme.
    """
    tree = _tree()
    panel = next((n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "show_data_collection_panel"), None)
    assert panel is not None, "show_data_collection_panel a disparu de app.py"

    called = {getattr(n.func, "id", getattr(n.func, "attr", ""))
              for n in ast.walk(panel) if isinstance(n, ast.Call)}
    assert "remember_not_launched" in called, (
        "les déclenchements refusés ne sont plus mémorisés. Sans ça ils ne vivent que "
        "dans la `st.status` du clic, qui se referme — l'artiste voit un panneau "
        "« Collecte en cours » qui ne mentionne pas les plateformes n'ayant jamais "
        "démarré, et conclut qu'elles tournent."
    )

    # Structurel, et pas `"NOT_LAUNCHED_KEY" in source` : cette version-là est restée
    # VERTE alors que la constante était débranchée, parce que son nom subsistait dans
    # les autres fonctions du module. Ce qui compte, c'est que le RENDU la lise.
    prog_tree = ast.parse(
        (_APP.parent / "utils" / "collection_progress.py").read_text(encoding="utf-8"))
    fns = {n.name: n for n in ast.walk(prog_tree) if isinstance(n, ast.FunctionDef)}

    for fname in ("render_progress", "remember_not_launched"):
        assert fname in fns, f"collection_progress.{fname} a disparu"
        names = {n.id for n in ast.walk(fns[fname]) if isinstance(n, ast.Name)}
        assert "NOT_LAUNCHED_KEY" in names, (
            f"collection_progress.{fname} ne référence plus NOT_LAUNCHED_KEY. "
            "Mémoriser sans afficher — ou afficher sans mémoriser — remplace un faux "
            "vert par un silence, ce qui est le même défaut."
        )

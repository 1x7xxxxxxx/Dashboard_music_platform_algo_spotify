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


def test_the_success_message_exists_at_all():
    calls = _success_calls(_tree())
    assert calls, (
        "aucun appel `success('app.launched')` trouvé — la clé a été renommée ? "
        "Mettre ce garde à jour plutôt que de le laisser vert sur rien."
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


def test_a_failure_is_told_too():
    """Ne rien dire quand tout échoue est le second défaut possible du même correctif."""
    text = _APP.read_text(encoding="utf-8")
    assert "app.launch_all_failed" in text, (
        "quand aucun déclenchement ne réussit, il faut le DIRE : conditionner le succès "
        "sans ajouter la branche d'échec remplacerait un faux vert par un silence."
    )

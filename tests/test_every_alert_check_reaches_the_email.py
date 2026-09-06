"""Guard: a check that computes a finding nobody renders is a check that does nothing.

Type: Utility
Uses: ast
Triggers: pytest
Persists in: nothing

Error class `finding-computed-but-never-sent`.

The alert DAG has eighteen checks. Each one has to travel a chain of FIVE links to be
worth anything: declared as a task → wired into the dependency list → its XCom read
back by the report builder → rendered in a section → and counted in `has_issues`,
the predicate that decides whether an email is sent at all.

Le cinquième maillon m'a échappé en écrivant ce fichier, et c'est un garde VOISIN
(`test_alert_monitor_sends_what_it_finds`) qui l'a rattrapé : un constat rendu mais
absent de `has_issues` ne produit AUCUN e-mail s'il est le seul problème de la nuit.
Deux gardes qui posent la même question à des profondeurs différentes valent mieux
qu'un seul — celui-ci vérifie les quatre premiers maillons pour les 18 tâches, le
voisin vérifie le cinquième. Break any one link and the check
still runs, still logs, still turns green — and says nothing to anyone.

This is not hypothetical. Writing `check_csv_rejections` on 2026-09-06, the third link
was there and the fourth was not; `ruff` caught it as an unused variable, which is a
lucky accident — a finding read into a variable that IS used elsewhere would have
passed silently.

The repo has already paid the same shape twice: a crashing check whose `xcom_pull`
returned `None` emptied its section while the report stayed green and looked complete.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_DAG = _repo_root() / "airflow" / "dags" / "alert_monitor.py"
_SRC = None
_TREE = None


def _src() -> str:
    global _SRC
    if _SRC is None:
        _SRC = _DAG.read_text(encoding="utf-8")
    return _SRC


def _tree() -> ast.Module:
    global _TREE
    if _TREE is None:
        _TREE = ast.parse(_src())
    return _TREE


def _checks() -> dict[str, str]:
    """{variable de l'opérateur: task_id} pour chaque `check_*` du DAG."""
    out = {}
    for node in ast.walk(_tree()):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        if getattr(node.value.func, "id", "") != "PythonOperator":
            continue
        for kw in node.value.keywords:
            if kw.arg == "task_id" and isinstance(kw.value, ast.Constant) \
                    and kw.value.value.startswith("check_"):
                out[node.targets[0].id] = kw.value.value
    return out


def _pulled_task_ids() -> set[str]:
    return {kw.value.value for n in ast.walk(_tree())
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "xcom_pull"
            for kw in n.keywords
            if kw.arg == "task_ids" and isinstance(kw.value, ast.Constant)}


def test_the_dag_actually_has_checks():
    """Sans quoi tout ce fichier est vrai de l'ensemble vide."""
    assert len(_checks()) >= 10, f"seulement {len(_checks())} check_* trouvés"


@pytest.mark.parametrize("var,task_id", sorted(_checks().items()))
def test_every_check_is_wired_into_the_dependency_chain(var, task_id):
    """Déclarer un opérateur ne le fait pas tourner : il faut le brancher."""
    chain_start = _src().find("] >> t_alert")
    assert chain_start > 0, "la liste de dépendances a changé de forme"
    chain = _src()[_src().rfind("[", 0, chain_start):chain_start]
    assert var in chain, (
        f"« {task_id} » est déclarée mais absente de la chaîne `>> t_alert` : "
        "Airflow ne l'exécutera jamais.")


@pytest.mark.parametrize("var,task_id", sorted(_checks().items()))
def test_every_check_result_is_read_back(var, task_id):
    """Un XCom que personne ne relit est un calcul jeté."""
    assert task_id in _pulled_task_ids(), (
        f"aucun `xcom_pull(task_ids='{task_id}')` : le constat est calculé puis "
        "perdu, et la tâche reste verte.")


def test_every_pulled_finding_is_rendered_somewhere():
    """Le dernier maillon : relire ne suffit pas, il faut RENDRE.

    C'est celui qui a manqué le 2026-09-06. `ruff` l'a signalé comme variable
    inutilisée — coup de chance : un nom réutilisé ailleurs serait passé.
    """
    tree = _tree()
    builder = next((n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "send_consolidated_alert"), None)
    assert builder is not None, "le constructeur du rapport a disparu"

    assigned = {n.targets[0].id for n in ast.walk(builder)
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                and any(isinstance(c, ast.Call)
                        and getattr(c.func, "attr", "") == "xcom_pull"
                        for c in ast.walk(n.value))}
    # ON SUIT LA DÉRIVATION, et il a fallu que le garde se trompe pour le voir :
    # `freshness` n'apparaît dans aucun `if`, il est filtré en `stale_sources`, qui
    # lui conditionne sa section. Exiger que le nom LU apparaisse tel quel condamnait
    # un motif parfaitement sain — et un garde qui crie sur du code correct se fait
    # désarmer, emportant les vrais cas avec lui.
    #
    # On calcule donc les alias : toute variable dont l'affectation mentionne un nom
    # déjà « atteignable » l'est à son tour, jusqu'au point fixe.
    reachable = set(assigned)
    for _ in range(len(list(ast.walk(builder)))):
        grown = set(reachable)
        for node in ast.walk(builder):
            if not (isinstance(node, ast.Assign)
                    and isinstance(node.targets[0], ast.Name)):
                continue
            used = {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
            if used & reachable:
                grown.add(node.targets[0].id)
        if grown == reachable:
            break
        reachable = grown

    def _always_false(test: ast.AST) -> bool:
        """`if False and x:` mentionne `x` et ne s'exécute jamais.

        PRÉSENCE N'EST PAS ATTEIGNABILITÉ — la mutation C de ce garde est passée au
        vert dessus le 2026-09-06, et c'est la troisième fois que ce dépôt paie cette
        distinction. Chercher un NOM dans une condition ne dit pas que la branche
        tourne.
        """
        if isinstance(test, ast.Constant) and not test.value:
            return True
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
            return any(_always_false(v) for v in test.values)
        return False

    tested = {n.id for cond in ast.walk(builder)
              if isinstance(cond, ast.If) and not _always_false(cond.test)
              for n in ast.walk(cond.test) if isinstance(n, ast.Name)}
    # Un constat est rendu si LUI ou l'un de ses dérivés conditionne une section.
    orphans = sorted(
        name for name in assigned
        if not ({name} & tested) and not (
            {a for a in reachable if a != name} & tested
            and any(name in {n.id for n in ast.walk(nd.value) if isinstance(n, ast.Name)}
                    for nd in ast.walk(builder)
                    if isinstance(nd, ast.Assign)
                    and isinstance(nd.targets[0], ast.Name)
                    and nd.targets[0].id in tested)))
    assert not orphans, (
        f"{orphans} sont lus depuis un XCom et ne conditionnent aucune section : "
        "le constat existe, personne ne le lit. C'est un contrôle qui ne contrôle "
        "rien tout en restant vert.")

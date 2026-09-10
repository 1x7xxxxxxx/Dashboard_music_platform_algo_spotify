"""Un compte publicitaire n'est collecté qu'une fois par nuit.

Type: Test
Uses: pytest, ast
Depends on: airflow/dags/meta_ads_api_daily.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10, run de production du 09-09)
------------------------------------------------------------
Le bac à sable déclare le compte publicitaire du profil principal — c'est sa raison
d'être : il est exempté du garde d'unicité d'identité pour rejouer l'onboarding avec de
vrais identifiants. La collecte reprenait donc le MÊME compte une seconde fois, et Meta
la limitait.

    locataire 1   →  96 s
    locataire 18  → 535 s, dont 424 s de sommeil imposé par le throttle
    même compte, 132 publicités, 3 087,82 € contre 3 080,88 €

Meta pesait **528 s des 651 s d'ETL nocturne, soit 81 %**, et le throttle est apparu sur
4 des 5 derniers runs. Retirer la reprise ramène la nuit à environ 115 s.

S'y ajoutait un appel Graph **par créative** — 143 appels unitaires par locataire et par
nuit, ~110 s — alors que le collecteur documente lui-même cette boucle comme « le
principal moteur de limitation » et expose un interrupteur que le DAG ne câblait pas.

Ce que ce garde ne peut pas faire
----------------------------------
Il ne mesure pas la durée : elle dépend de Meta, pas de nous. Il garde la DÉCISION —
qu'un compte déjà vu soit sauté, et que la boucle par créative reste conditionnelle.
"""
from __future__ import annotations

import ast
from pathlib import Path

DAG = Path(__file__).resolve().parent.parent / "airflow" / "dags" / "meta_ads_api_daily.py"


def _collect_fn() -> ast.FunctionDef:
    tree = ast.parse(DAG.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and "collect" in n.name:
            for sub in ast.walk(n):
                if isinstance(sub, ast.For):
                    return n
    raise AssertionError("la boucle par locataire a disparu du DAG Meta")


def test_a_second_tenant_on_the_same_account_is_skipped() -> None:
    """Structurel : la boucle tient un registre des comptes vus et en sort.

    On lit l'ARBRE, pas le texte : un nom qui survivrait dans un commentaire ne doit
    pas suffire à rendre ce garde vert — c'est le mode d'aveuglement que ce dépôt
    catalogue.
    """
    fn = _collect_fn()
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "seen_accounts" in names, (
        "aucun registre des comptes déjà collectés : le bac à sable reprend le compte "
        "du profil principal, et le throttle Meta qui s'ensuit retombe sur la flotte "
        "réelle")

    # Et ce registre doit réellement faire SORTIR de l'itération.
    guarded = [
        node for node in ast.walk(fn)
        if isinstance(node, ast.If)
        and "seen_accounts" in ast.unparse(node.test)
        and any(isinstance(x, ast.Continue) for x in ast.walk(node))
    ]
    assert guarded, (
        "le registre existe mais rien n'en sort : la collecte redondante a toujours "
        "lieu — un détecteur écrit que rien n'applique")


def test_the_per_creative_loop_is_not_run_every_night() -> None:
    """`fetch_creatives` doit être conditionnel, jamais laissé à son défaut."""
    fn = _collect_fn()
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "run"]
    assert calls, "l'appel au collecteur a disparu"
    for c in calls:
        kw = {k.arg for k in c.keywords}
        assert "fetch_creatives" in kw, (
            "`fetch_creatives` n'est pas câblé : il vaut True par défaut, soit un appel "
            "Graph par créative — 143 par locataire et par nuit, que le collecteur "
            "lui-même nomme « le principal moteur de limitation »")
        arg = next(k.value for k in c.keywords if k.arg == "fetch_creatives")
        assert not (isinstance(arg, ast.Constant) and arg.value is True), (
            "`fetch_creatives=True` en dur : la boucle repart chaque nuit")

"""« MRR total » veut dire la même chose sur toutes les pages qui l'affichent.

Type: Test
Uses: ast
Depends on: src/utils/mrr, src/dashboard/views/{admin,billing,revenue_forecast}.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-18 : le MRR était calculé à **trois endroits**, avec **deux réponses**
sous le même libellé.

    admin.py:544-546        WHERE a.status = 'active'                  SQL
    billing.py:322-331      WHERE asub.status = 'active'               SQL
    revenue_forecast.py     status ∈ {'active','trialing'} ET price>0  pandas

Dès qu'un abonnement passait en `trialing` — et l'admin parle explicitement d'« essai de
bienvenue » — deux pages affichaient deux nombres différents sous le même mot. « Artistes
payants » aussi.

⚠️ **Et aucune des trois n'excluait les locataires techniques**, alors que le compteur
« Artistes actifs », QUATRE LIGNES plus haut dans le même écran, les excluait. Deux
nombres de la même page se contredisaient.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.mrr import MRR_STATUSES, mrr_by_plan_sql, mrr_params  # noqa: E402

_SURFACES = (
    "src/dashboard/views/admin.py",
    "src/dashboard/views/billing.py",
    "src/dashboard/views/revenue_forecast.py",
)


def test_the_single_definition_counts_trials() -> None:
    """La décision du 2026-09-20, écrite là où elle s'applique."""
    assert "trialing" in MRR_STATUSES and "active" in MRR_STATUSES


def test_the_single_definition_excludes_technical_tenants() -> None:
    """Le prédicat vient de `tenant_kind`, et il est bien dans la requête."""
    sql = mrr_by_plan_sql()
    assert "is_canary" in sql and "is_sandbox" in sql, (
        "la requête du MRR n'exclut pas les locataires techniques — elle compterait les "
        "canaris et le bac à sable comme du revenu, pendant que le compteur d'artistes "
        "de la même page les exclut.")


def _litteraux_qui_filtrent(arbre: ast.AST) -> list[str]:
    """Les `'trialing'` qui SERVENT À DÉCIDER, pas ceux qui servent à afficher.

    ⚠️ La première version de ce prédicat cherchait le littéral n'importe où. Elle a
    accusé `billing.py:156`, qui écrit `'trialing': '🟡'` — une table d'ICÔNES par
    statut, qui doit évidemment nommer tous les statuts. C'est la même erreur que ce
    dépôt a mesurée onze fois cette semaine : chercher une FORME D'ÉCRITURE là où la
    classe parle d'une PROPRIÉTÉ. Ici la propriété est « ce littéral décide-t-il de ce
    qui compte », et elle se lit dans la POSITION du nœud :

      * une comparaison (`status == 'trialing'`)                    → il décide
      * un argument d'appartenance (`.isin([...])`, `in (...)`)     → il décide
      * une CLÉ de dictionnaire (`{'trialing': '🟡'}`)              → il affiche
      * une valeur de dictionnaire                                  → il affiche
    """
    fautifs: list[str] = []
    cles_de_dict: set[int] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Dict):
            cles_de_dict.update(id(k) for k in n.keys if k is not None)
            cles_de_dict.update(id(v) for v in n.values)

    def _chaines(noeud) -> list[ast.Constant]:
        return [x for x in ast.walk(noeud)
                if isinstance(x, ast.Constant) and x.value in ("trialing", "active")]

    for n in ast.walk(arbre):
        if isinstance(n, ast.Compare):
            for c in _chaines(n):
                if id(c) not in cles_de_dict:
                    fautifs.append(f"comparaison sur {c.value!r} (l.{c.lineno})")
        elif isinstance(n, ast.Call):
            nom = getattr(n.func, "attr", "") or getattr(n.func, "id", "")
            if nom in ("isin", "in_", "any_"):
                for c in _chaines(n):
                    fautifs.append(f"appartenance à {c.value!r} (l.{c.lineno})")
    return fautifs


@pytest.mark.parametrize("rel", _SURFACES)
def test_no_surface_decides_the_status_set_by_hand(rel: str) -> None:
    """LE GARDE. Un statut qui DÉCIDE du MRR, hors du module unique.

    Lu à l'AST : un commentaire qui explique le défaut contient les mots, et un prédicat
    textuel rougirait sur sa propre documentation.
    """
    texte = (ROOT / rel).read_text(encoding="utf-8")
    fautifs = _litteraux_qui_filtrent(ast.parse(texte))
    for m in re.finditer(r"status\s*=\s*'active'", texte):
        if not texte[:m.start()].rsplit("\n", 1)[-1].lstrip().startswith("#"):
            fautifs.append(f"filtre SQL `{m.group(0)}`")
    assert not fautifs, (
        f"{rel} décide lui-même de ce qui compte dans le MRR : {fautifs}.\n"
        "C'est ainsi que deux pages ont affiché deux nombres sous le même mot. "
        "Importer `MRR_STATUSES` / `mrr_by_plan_sql()` depuis `src/utils/mrr.py`.")


def test_the_predicate_tells_a_filter_from_an_icon_table() -> None:
    """AUTO-PREUVE des deux sens, sur du code SYNTHÉTIQUE.

    Sans elle, un prédicat qui n'accuse plus RIEN passerait le test ci-dessus.
    """
    filtre = ast.parse("x = df[df['status'].isin(['active', 'trialing'])]")
    icones = ast.parse("ICONES = {'trialing': '🟡', 'active': '🟢'}")
    assert _litteraux_qui_filtrent(filtre), (
        "le prédicat ne voit pas un `.isin(['active','trialing'])` — c'est exactement la "
        "forme qu'il existe pour attraper.")
    assert not _litteraux_qui_filtrent(icones), (
        "le prédicat accuse une table d'icônes par statut, qui doit nommer tous les "
        "statuts. C'est le faux positif qui l'a fait resserrer.")


@pytest.mark.parametrize("rel", _SURFACES)
def test_every_surface_reads_the_single_definition(rel: str) -> None:
    """ANTI-VACUITÉ. Ne pas épeler ne suffit pas — encore faut-il LIRE la définition."""
    texte = (ROOT / rel).read_text(encoding="utf-8")
    assert re.search(r"from src\.utils\.mrr import", texte), (
        f"{rel} n'importe rien de `src/utils/mrr.py`. Il peut ne plus épeler les statuts "
        "tout en calculant le MRR autrement — le test ci-dessus serait vert pour rien.")


def test_the_query_runs_against_the_real_schema() -> None:
    """Le SQL composé doit être exécutable — une requête qui lève n'affiche rien.

    ⚠️ Ce test EXÉCUTE la requête. La version précédente de ce garde se serait contentée
    de lire le texte, et un alias oublié (`is_canary` au lieu de `sa.is_canary` dans une
    requête jointe) ne se voit qu'à l'exécution.
    """
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        pytest.skip("base injoignable")
    try:
        db.fetch_query(mrr_by_plan_sql(), mrr_params())
    finally:
        db.close()

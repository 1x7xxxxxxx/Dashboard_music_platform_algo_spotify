"""Un euro affiché à l'artiste a UNE définition, brute ou nette, jamais les deux.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/views/revenue_forecast.py,
            src/dashboard/utils/revenue_forecast.py,
            src/utils/gold_invariants.py

Le défaut, vu au navigateur le 2026-09-21
------------------------------------------
Dans UN SEUL écran, à un clic l'un de l'autre :

    la figure        SACEM = 36,49 €     (v_artist_monthly_revenue_net)
    le tiroir        SACEM = 43,06 €     (v_artist_monthly_revenue)

Les deux nombres étaient justes. L'écart est 6,57 € de charges et de TVA, et rien
à l'écran ne disait lequel on regardait. La coupable était
`load_artist_revenue_by_source()` : elle lisait le BRUT sous un nom qui dit
seulement « revenue ».

Classe : `a-metric-with-two-definitions-in-one-screen`. Elle ne lève jamais — les
deux chiffres sont calculés correctement — et elle ne se voit qu'en regardant la
page, ce qui est précisément ce qu'une suite de tests ne fait pas.

Ce que ce garde tient, et ce qu'il ne tient PAS
------------------------------------------------
Il tient : **la page de l'argent de l'artiste** ne lit qu'une source de vérité,
`v_artist_monthly_cashflow`. Il ne tient PAS « personne ne lit jamais la vue
brute » — ce serait un prédicat de FORME, pas de PROPRIÉTÉ (règle transverse 20),
et il serait faux : `_tab_ltv` lit légitimement le brut pour une moyenne de
flotte, qui n'est pas le compte d'un artiste.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_VUE = _ROOT / "src" / "dashboard" / "views" / "revenue_forecast.py"
_UTIL = _ROOT / "src" / "dashboard" / "utils" / "revenue_forecast.py"

# La vue BRUTE. Elle existe et sert ailleurs ; elle n'a rien à faire dans le
# compte d'un artiste, où le point mort se joue sur ce qui arrive vraiment.
_BRUTE = "v_artist_monthly_revenue"
_NETTE = "v_artist_monthly_cashflow"

# Le point d'entrée de la page de l'argent, et tout ce qu'elle appelle DANS ce
# module. `_tab_ltv` n'en fait pas partie : c'est l'onglet SaaS de l'exploitant.
_RACINE = "_tab_artist_forecast"


def _module() -> ast.Module:
    return ast.parse(_VUE.read_text(encoding="utf-8"))


def _fonctions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _joignables(tree: ast.Module) -> set[str]:
    """Les fonctions du module atteignables depuis la page de l'argent.

    Fermeture transitive, et c'est le point : le défaut ne vivait pas dans
    `_tab_artist_forecast` mais dans un helper qu'elle appelait.
    """
    fns = _fonctions(tree)
    vu, pile = set(), [_RACINE]
    while pile:
        nom = pile.pop()
        if nom in vu or nom not in fns:
            continue
        vu.add(nom)
        for n in ast.walk(fns[nom]):
            if isinstance(n, ast.Call):
                cible = (getattr(n.func, "id", None)
                         or getattr(n.func, "attr", None))
                if cible in fns:
                    pile.append(cible)
    return vu


def _sql(fn: ast.AST) -> list[str]:
    """Les chaînes de la fonction, DOCSTRING EXCLUE.

    ⚠️ Par l'AST, jamais par le texte. Le nom de la vue brute DOIT pouvoir être
    écrit en prose — c'est là qu'on explique pourquoi on ne la lit plus. Ce dépôt
    a pris quatre gardes textuels verts sur leur propre commentaire, et deux
    rouges sur leur propre docstring, le 2026-09-21.
    """
    docs = set()
    corps = getattr(fn, "body", None)
    if corps and isinstance(corps[0], ast.Expr) \
            and isinstance(corps[0].value, ast.Constant) \
            and isinstance(corps[0].value.value, str):
        docs.add(id(corps[0].value))
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and id(n) not in docs:
            out.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            out.append("".join(v.value for v in n.values
                               if isinstance(v, ast.Constant)
                               and isinstance(v.value, str)))
    return out


def _lit(sql: str, table: str) -> bool:
    import re
    return re.search(rf"\b(?:FROM|JOIN)\s+{re.escape(table)}\b", sql, re.I) is not None


def test_the_artist_money_page_never_reads_the_gross_view() -> None:
    tree = _module()
    fns = _fonctions(tree)
    coupables = []
    for nom in sorted(_joignables(tree)):
        for s in _sql(fns[nom]):
            # `v_artist_monthly_revenue_net` commence par le même nom : on exige
            # la FIN du mot, sinon le prédicat accuse la vue nette elle-même.
            if _lit(s, _BRUTE) and not _lit(s, _BRUTE + "_net"):
                coupables.append(f"{nom} : {' '.join(s.split())[:90]}")
                break
    assert not coupables, (
        f"la page de l'argent lit « {_BRUTE} » (le BRUT) :\n  "
        + "\n  ".join(coupables)
        + f"\nElle doit lire « {_NETTE} ». Le 2026-09-21, ce mélange affichait "
          "43,06 € de SACEM dans un tiroir sous une figure qui en dessinait "
          "36,49 € — l'écart étant les charges et la TVA. Un point mort se joue "
          "sur ce qui arrive vraiment sur le compte.")


def test_the_artist_money_page_does_read_the_cashflow_view() -> None:
    """NON-VACUITÉ. « Elle ne lit pas le brut » est vrai aussi d'une page qui ne
    lit rien : c'est ainsi qu'un garde cesse de garder sans jamais rougir."""
    tree = _module()
    fns = _fonctions(tree)
    trouve = any(_lit(s, _NETTE)
                 for nom in _joignables(tree) for s in _sql(fns[nom]))
    assert trouve, (
        f"aucune fonction atteignable depuis `{_RACINE}` ne lit « {_NETTE} ». "
        "Soit la page a changé de source, soit la fermeture transitive ne "
        "l'atteint plus — dans les deux cas le test précédent ne prouve rien.")


def test_the_detector_would_catch_the_defect_it_was_written_for() -> None:
    """La mutation, jouée dans le test : le prédicat voit-il VRAIMENT le défaut ?"""
    faute = ("SELECT source, SUM(revenue_eur) FROM v_artist_monthly_revenue "
             "WHERE artist_id = %s GROUP BY source")
    assert _lit(faute, _BRUTE) and not _lit(faute, _BRUTE + "_net")
    sain = "SELECT artist_id, SUM(net_eur) FROM v_artist_monthly_revenue_net"
    assert _lit(sain, _BRUTE + "_net")
    assert not _lit(sain, _NETTE)


def test_the_gross_helper_stays_removed() -> None:
    """Le remède durable est le RETRAIT, pas le renommage.

    Tant que la fonction existe, le prochain appelant reproduit l'écart sans le
    voir : son nom ne dit pas qu'elle rend du brut, et c'est tout le défaut.
    """
    tree = ast.parse(_UTIL.read_text(encoding="utf-8"))
    noms = {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "load_artist_revenue_by_source" not in noms, (
        "`load_artist_revenue_by_source` est revenue. Elle lit le BRUT sous un "
        "nom qui dit seulement « revenue » : c'est exactement ce qui a produit "
        "deux chiffres de SACEM dans un même écran le 2026-09-21.")


@pytest.mark.parametrize("nom", ["cashflow_revenue_vs_net_source",
                                 "cashflow_meta_spend_vs_gold"])
def test_the_cashflow_view_is_watched_by_an_invariant(nom: str) -> None:
    """Le garde statique ci-dessus lit du CODE ; celui-ci exige la mesure.

    Un test d'AST ne peut pas voir une vue SQL qui perd une ligne. Les deux
    invariants ont été mutés le 2026-09-21 et rendent le défaut qu'ils visent :
    6,57 € d'écart brut/net, et 798,65 € de dépense publicitaire perdue par un
    regroupement au mois.
    """
    from src.utils.gold_invariants import INVARIANTS

    enregistres = {i.name for i in INVARIANTS}
    assert nom in enregistres, (
        f"l'invariant « {nom} » n'est plus enregistré. La vue de trésorerie "
        "pourrait perdre une ligne sans que rien ne rougisse — et un point mort "
        "qui oublie une dépense est OPTIMISTE, la direction où personne ne va "
        "vérifier.")


# ── Les étiquettes construites par f-string ont toutes leur traduction ─────
#
# `test_i18n_orphans` exempte trois préfixes de son balayage — `source.`, `cat.`
# et `period.` — parce qu'une clé construite n'a pas de référence littérale à
# trouver. L'exemption ouvre un trou : une catégorie de coût ajoutée sans
# traduction passerait, et s'afficherait en clé brute à l'artiste. Ce test le
# bouche, comme `credentials.resolve.` et `home.mode_` avant lui.
def test_every_money_label_has_a_translation() -> None:
    from src.dashboard.utils.i18n_catalog.revenue_forecast import EN
    from src.dashboard.views.revenue_forecast import _CAT_COUTS, _FLUX_NOMS

    manquantes = [f"revenue_forecast.source.{s}" for s in _FLUX_NOMS
                  if f"revenue_forecast.source.{s}" not in EN]
    manquantes += [f"revenue_forecast.cat.{k}" for k in _CAT_COUTS
                   if f"revenue_forecast.cat.{k}" not in EN]
    manquantes += [f"revenue_forecast.period.{k}"
                   for k in ("one_off", "yearly", "monthly")
                   if f"revenue_forecast.period.{k}" not in EN]
    assert not manquantes, (
        f"étiquette(s) d'argent sans traduction : {manquantes}. Sans entrée, "
        "l'artiste anglophone lit la CLÉ BRUTE dans la légende de sa figure.")


def test_the_cost_categories_match_the_database_constraint() -> None:
    """Le menu déroulant et la contrainte SQL ne peuvent pas diverger.

    `artist_cost_entries.category` porte un `CHECK (...)`. Une catégorie offerte
    à l'écran mais absente de la contrainte fait échouer l'INSERT au moment où
    l'artiste presse « Enregistrer » — c'est-à-dire au pire moment, et avec un
    message de base de données.
    """
    import re

    from src.dashboard.views.revenue_forecast import _CAT_COUTS

    sql = (_ROOT / "migrations" / "133_gold_artist_cashflow.sql").read_text(
        encoding="utf-8")
    m = re.search(r"CHECK\s*\(category\s+IN\s*\(([^)]*)\)\)", sql, re.I | re.S)
    assert m, "la contrainte `CHECK (category IN (...))` a disparu de la migration"
    autorisees = set(re.findall(r"'([a-z_]+)'", m.group(1)))
    assert set(_CAT_COUTS) <= autorisees, (
        f"catégorie(s) offertes à l'écran et refusées par la base : "
        f"{sorted(set(_CAT_COUTS) - autorisees)}")

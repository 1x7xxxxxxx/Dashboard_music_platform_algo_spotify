"""L'instrument de concurrence ne peut plus rendre une colonne « perdu » indistincte.

Type: Test
Uses: ast, pathlib
Depends on: tools/loadtest_concurrency.py
Persists in: nothing

Ce qui a été mesuré
-------------------
La colonne « reruns perdus » de `tools/loadtest_concurrency.py` a servi de **signal de
décision à R114** — garder ou non une seconde réplique. L'audit a montré qu'elle ne
tenait pas, sur quatre points cumulables :

1. le marqueur guetté (`stStatusWidget`) n'est **pas spécifique aux reruns** : Streamlit
   le monte aussi pour `stConnectionStatus`. Un websocket dégradé faisait compter
   « perdu » un rerun qui avait pu être servi ;
2. un `except Exception` nu fusionnait trois causes dont **une seule** parle du serveur ;
3. le p50 était calculé sur les SURVIVANTS — 68 à 82 % de censure à 24 onglets ;
4. le compte n'était pas monotone (9 → 33 → **24** → 98), ce qu'aucune saturation
   serveur ne produit : le CLIENT manquait de RAM.

Ce que ce test assert
---------------------
Les quatre corrections sont **structurelles**, pas cosmétiques, et le test les lit dans
l'AST — jamais par `grep`, qui serait vert sur ce docstring.

Classes : `a-measurement-that-cannot-say-why-it-failed`,
`a-percentile-computed-on-survivors`.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "loadtest_concurrency.py"


def _tree() -> ast.Module:
    return ast.parse(_TOOL.read_text(encoding="utf-8"))


def _func(tree: ast.AST, name: str):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _code_strings(tree: ast.AST) -> set[str]:
    """Les littéraux de chaîne qui vivent dans du CODE, docstrings exclues.

    Exclues par IDENTITÉ DE NŒUD : `ast.get_docstring()` désindente, donc une comparaison
    par valeur n'exclurait jamais rien — c'est la classe
    `a-docstring-exclusion-that-compares-dedented-text`, payée le 2026-09-16.
    """
    docs = set()
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)) and body:
            first = body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docs.add(id(first.value))
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs}


def test_the_marker_is_specific_to_reruns() -> None:
    """Défaut 1 : le marqueur ne doit plus être celui que le transport partage."""
    strings = _code_strings(_tree())
    assert not any("stStatusWidget" in s for s in strings), (
        "`stStatusWidget` est de retour dans le CODE. Streamlit le monte aussi pour "
        "`stConnectionStatus` : un websocket dégradé ferait compter « perdu » un rerun "
        "qui a pu être servi, et la colonne remélangerait le rendu et le transport.")
    assert any("data-test-script-state" in s for s in strings), (
        "l'instrument ne lit plus `data-test-script-state` — le seul attribut qui parle "
        "du RERUN et de rien d'autre.")
    assert any("data-test-connection-state" in s for s in strings), (
        "l'instrument ne lit plus `data-test-connection-state` : sans lui, un rerun "
        "jamais démarré ne peut pas être distingué d'un transport coupé.")


def test_the_three_failure_causes_are_counted_separately() -> None:
    """Défaut 2 : une issue fourre-tout empêche de savoir QUI a échoué."""
    tree = _tree()
    fn = _func(tree, "_one_rerun")
    assert fn is not None, "`_one_rerun()` a disparu"

    returned = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple) and n.value.elts:
            head = n.value.elts[0]
            if isinstance(head, ast.Constant) and isinstance(head.value, str):
                returned.add(head.value)

    required = {"ok", "click_failed", "never_started", "never_finished"}
    missing = required - returned
    assert not missing, (
        f"`_one_rerun()` ne distingue pas {sorted(missing)} (elle rend {sorted(returned)}). "
        "Une seule de ces causes parle du SERVEUR — `never_finished`. Les fusionner "
        "reproduit la colonne qui a servi de signal de décision à R114 et qui ne tenait "
        "pas.")

    # Et le module doit DÉCLARER la liste, pour que le compteur ne puisse pas rater une
    # issue que la fonction rend.
    declared = None
    for n in ast.walk(tree):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "_OUTCOMES"
                and isinstance(n.value, ast.Tuple)):
            declared = {e.value for e in n.value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    assert declared is not None, "`_OUTCOMES` n'est plus déclaré"
    orphans = returned - declared
    assert not orphans, (
        f"issue(s) rendue(s) par `_one_rerun()` mais absente(s) de `_OUTCOMES` : "
        f"{sorted(orphans)}. Le compteur les perdrait silencieusement — un `KeyError` "
        "serait préférable, mais l'absence est pire : elle ne se voit pas.")


def test_the_censoring_rate_is_published() -> None:
    """Défaut 3 : un p50 calculé sur les survivants doit dire combien il en a perdu.

    ⚠️ La première rédaction de ce test cherchait le nom `censored_pct` **n'importe où**
    dans le fichier. Mutation jouée : renommer la clé PRODUITE par `_level()` — le test
    est resté vert, parce que le nom survivait chez ses lecteurs. Un garde qui cherche un
    nom plutôt qu'un lien est la forme que ce dépôt catalogue sous « un garde textuel est
    aveugle ». Il vérifie maintenant le CHEMIN : la clé est produite, puis lue.
    """
    tree = _tree()

    level = _func(tree, "_level")
    assert level is not None, "`_level()` a disparu"
    produced = set()
    for n in ast.walk(level):
        if isinstance(n, ast.Dict):
            produced |= {k.value for k in n.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert "censored_pct" in produced, (
        f"`_level()` ne produit plus de taux de censure (clés : {sorted(produced)}). "
        "Sans lui, le p50 décrit les reruns ABOUTIS et sous-estime la dégradation — à "
        "24 onglets, 68 à 82 % des échantillons étaient censurés et le chiffre publié "
        "décrivait le quart restant.")

    # ── ET LA VALEUR, PAS SEULEMENT LA CLÉ (2026-09-18) ────────────────────────
    #
    # Mutation jouée ce jour-là : garder la clé et figer sa valeur à `0.0`. Le test
    # est resté VERT — il vérifiait le CÂBLAGE (produite, puis lue) et jamais ce qui
    # circule dedans. Or un taux de censure constamment nul dit « rien n'a été perdu »,
    # c'est-à-dire exactement le chiffre rassurant que cette classe existe pour
    # interdire. Le garde attrapait le renommage et laissait passer le mensonge.
    #
    # On exige donc que la valeur DÉRIVE des mesures : une expression, pas une
    # constante. C'est le même cran que le passage « nom » → « chemin » décrit
    # au-dessus, appliqué une fois de plus.
    for n in ast.walk(level):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and k.value == "censored_pct"):
                continue
            assert not isinstance(v, ast.Constant), (
                "`censored_pct` est une CONSTANTE dans `_level()`. Un taux de censure "
                "figé annonce « rien n'a été perdu » quel que soit ce qui s'est passé — "
                "le p50 décrit alors les survivants et la valeur publiée à côté ne le "
                "corrige pas. Il doit se calculer à partir des tentatives et des "
                "aboutissements.")

    run = _func(tree, "_run")
    read = {n.slice.value for n in ast.walk(run)
            if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
            and isinstance(n.slice.value, str)}
    assert "censored_pct" in read, (
        "`_run()` ne LIT pas le taux de censure : il serait calculé, écrit dans le JSON, "
        "et absent du tableau que l'humain regarde.")

    strings = _code_strings(tree)
    assert any("BORNE" in s or "borne inf" in s.lower() for s in strings), (
        "au-delà du seuil de censure, le rapport ×N doit être annoncé comme une BORNE "
        "INFÉRIEURE. Publié comme une mesure, il ment dans le sens rassurant.")


def test_the_client_saturation_is_measured_at_every_level() -> None:
    """Défaut 4 : un compte non monotone venait du CLIENT, jamais vérifié en cours."""
    tree = _tree()
    assert _func(tree, "_browser_rss_mb") is not None, (
        "la RAM du navigateur n'est plus mesurée. C'est elle qui explique le compte non "
        "monotone 9 → 33 → 24 → 98 : 175-217 Mo par `chrome-headless-shell`, donc "
        "24 onglets ≈ 4,2 Go contre ~4,0 Go disponibles.")

    run = _func(tree, "_run")
    assert run is not None, "`_run()` a disparu"
    loops = [n for n in ast.walk(run) if isinstance(n, ast.For)]
    checked_in_loop = any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
        and c.func.id in {"_available_mb", "_browser_rss_mb"}
        for loop in loops for c in ast.walk(loop))
    assert checked_in_loop, (
        "la saturation du client n'est vérifiée qu'AVANT la rampe, pas à chaque palier. "
        "C'est précisément ce que faisait la version qui a produit le compte non "
        "monotone : elle regardait une fois, au moment le plus léger.")


def test_the_guard_does_not_count_its_own_browser() -> None:
    """`_heavy_local_processes` comptait `chromium` — ce qu'elle CRÉE elle-même.

    Rejouée en cours de mesure, elle se serait toujours trouvée trop chargée. C'est la
    forme `a-guard-that-matches-what-it-produces`, voisine du `pkill` qui tue son propre
    shell.
    """
    fn = _func(_tree(), "_heavy_local_processes")
    assert fn is not None, "`_heavy_local_processes()` a disparu"
    args = [a.arg for a in fn.args.args]
    assert "exclude_own_browser" in args, (
        f"`_heavy_local_processes()` n'a pas de quoi s'exclure elle-même (args : {args}). "
        "Elle compte `chromium` parmi ses clés, c'est-à-dire ce que cet outil lance.")


def test_each_level_is_written_before_the_next_one_starts() -> None:
    """Deux passes sur quatre sont mortes en emportant toute la série."""
    tree = _tree()
    assert _func(tree, "_write_level") is not None, "`_write_level()` a disparu"
    run = _func(tree, "_run")
    loops = [n for n in ast.walk(run) if isinstance(n, ast.For)]
    written_in_loop = any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
        and c.func.id == "_write_level"
        for loop in loops for c in ast.walk(loop))
    assert written_in_loop, (
        "les paliers ne sont plus écrits DANS la boucle. Écrits à la fin, une "
        "interruption emporte toute la série — c'est arrivé deux fois sur quatre passes, "
        "et une série partielle vaut infiniment mieux que rien.")


def test_the_detector_is_not_vacuous() -> None:
    """Non-vacuité : si l'AST ne se lit plus, tout ce fichier passerait à vide."""
    tree = _tree()
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {"_one_rerun", "_level", "_run", "main"} <= names, (
        f"l'outil a changé de forme au point que ce garde ne le décrit plus : {sorted(names)}")
    assert _code_strings(tree), "aucun littéral lu dans le code — la lecture est cassée"

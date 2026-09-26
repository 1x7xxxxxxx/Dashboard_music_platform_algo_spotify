"""Un garde de charge mesure la CHARGE, et un instrument dit ce qu'il n'observe pas.

Type: Test
Uses: ast
Depends on: tools/loadtest_concurrency.py, src/dashboard/app.py
Persists in: nothing

Deux défauts, tous deux trouvés le 2026-09-17 en essayant de lancer la re-mesure R114 —
donc AVANT qu'une seule courbe ne sorte.

1. Le garde qui ne pouvait jamais passer
----------------------------------------
`_heavy_local_processes` comptait des processus par motif de NOM, dont la clé `"node "`.
Un terminal d'IDE en fait tourner neuf (le serveur VS Code). Un développeur lançant la
mesure depuis son éditeur était refusé PAR CONSTRUCTION.

Mesuré au moment du refus : charge **1,02 sur 8 cœurs (13 %)**, et les douze « lourds »
consommaient **5,1 % de CPU à eux tous**. Famille `un-contrôle-qui-ne-peut-jamais-passer`.

⚠️ Le correctif ne SUPPRIME pas la liste : elle dit toujours *quoi* regarder. Ce qui
change est le verdict — la charge réelle, pas un compte de présences.

2. Deux instruments, deux chemins
----------------------------------
Le mode anonyme du générateur mesure la page de connexion, rendue AVANT `require_login()`.
La couture de métriques s'exécute APRÈS. Pendant une passe de 7 paliers jusqu'à 24
onglets, le client a mesuré ×15,94 de sérialisation pendant que le serveur enregistrait
`nan` et 0 rerun.

⚠️ Le piège n'est pas l'écart, c'est sa LECTURE : un zéro serveur se lit comme « aucune
perte » alors qu'il signifie « aucune observation ». J'ai conclu à un défaut de
production sur cette base, puis rétracté.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "tools" / "loadtest_concurrency.py"
_APP = _REPO / "src" / "dashboard" / "app.py"


def _fn(path: Path, name: str) -> ast.FunctionDef | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _verdict_reads_the_kernel(tree: ast.AST) -> bool:
    """`main` calls `_local_load`, and `_local_load` reads `/proc/loadavg`."""
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    load, main = fns.get("_local_load"), fns.get("main")
    if load is None or main is None:
        return False
    reads = any(isinstance(n, ast.Constant) and n.value == "/proc/loadavg" for n in ast.walk(load))
    called = any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_local_load"
                 for n in ast.walk(main))
    return reads and called


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity on FABRICATED tools: a refusal that COUNTS process names (nine IDE
    `node`s refuse a valid measurement) is seen; one that reads the kernel load is not;
    a `_local_load` that exists but that `main` never calls is still the defect."""
    counts = ast.parse("def main():\n    if len(pgrep('node')) > 3:\n        raise SystemExit(1)\n")
    measures = ast.parse("def _local_load():\n    return open('/proc/loadavg').read()\n"
                         "def main():\n    if float(_local_load().split()[0]) > 4:\n        raise SystemExit(1)\n")
    orphan = ast.parse("def _local_load():\n    return open('/proc/loadavg').read()\n"
                       "def main():\n    if len(pgrep('node')) > 3:\n        raise SystemExit(1)\n")
    assert not _verdict_reads_the_kernel(counts)
    assert _verdict_reads_the_kernel(measures)
    assert not _verdict_reads_the_kernel(orphan)


def test_the_refusal_is_based_on_a_measurement() -> None:
    """Le verdict lit une grandeur, pas un compte de processus présents."""
    fn = _fn(_TOOL, "_local_load")
    assert fn is not None, (
        "`_local_load` a disparu : le refus est probablement revenu à un COMPTE de "
        "processus. Sur une machine au repos avec neuf `node` d'IDE, il refuse une "
        "mesure parfaitement valide — c'est `un-contrôle-qui-ne-peut-jamais-passer`.")
    consts = {n.value for n in ast.walk(fn)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "/proc/loadavg" in consts, (
        "`_local_load` ne lit plus la charge du noyau — sur quoi porte alors son verdict ?")


def test_the_name_list_is_no_longer_the_verdict() -> None:
    """La liste survit comme PÉRIMÈTRE, mais ne décide plus seule du refus."""
    assert _verdict_reads_the_kernel(ast.parse(_TOOL.read_text(encoding="utf-8")))
    src = _TOOL.read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, "`main` a disparu"
    called = {n.func.id for n in ast.walk(main)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_local_load" in called, (
        "`main` n'appelle plus `_local_load` : le refus redevient un compte de noms, "
        "et la mesure redevient impossible depuis un terminal d'IDE")


def test_the_instrumented_path_is_behind_the_login_gate() -> None:
    """La couture est APRÈS `require_login` — donc le mode anonyme n'est pas observé.

    Ce test ne corrige pas le défaut : il l'ENREGISTRE, pour qu'un futur « le serveur
    n'a rien vu, donc rien ne s'est perdu » se heurte à quelque chose. Si la couture
    passait un jour AVANT la porte, ce test rougirait — et ce serait la bonne nouvelle
    à examiner, pas un faux positif.
    """
    src = _APP.read_text(encoding="utf-8")
    lines = src.splitlines()
    gate = next((i for i, ln in enumerate(lines, 1) if "require_login()" in ln), None)
    seam = next((i for i, ln in enumerate(lines, 1) if "end_chrome(" in ln
                 and not ln.strip().startswith("#")
                 and "import" not in ln), None)
    assert gate is not None and seam is not None, (
        f"porte d'authentification ({gate}) ou couture ({seam}) introuvable dans app.py")
    assert seam > gate, (
        f"la couture de métriques (ligne {seam}) est passée AVANT `require_login()` "
        f"(ligne {gate}). Ce n'est pas forcément un défaut — mais la conséquence est "
        "que le mode anonyme du générateur de charge deviendrait observable côté "
        "serveur, ce que `.claude/dev-docs/runbook-actions-utilisateur.md` §14 "
        "affirme impossible. Mettre les deux d'accord.")


def test_the_daily_summary_declares_what_it_does_not_observe() -> None:
    """Le module qui écrit les chiffres dit ce qu'ils ne voient pas.

    Troisième trou déclaré le 2026-09-17 dans le `ne couvre pas:` de
    `two-instruments-that-do-not-observe-the-same-path` : « les autres couples
    d'instruments du dépôt, dont aucun ne déclare son périmètre d'observation ».

    `src/utils/daily_ops_metrics.py` écrit `p50_render_ms`, `reruns_total` et
    `complete` depuis Prometheus. Son docstring expliquait très bien POURQUOI deux
    stockages et ce qu'il fait quand Prometheus ne répond pas — et ne disait rien du
    fait que la couture s'exécute **après `require_login()`**.

    Les trois conséquences, aucune visible dans la ligne écrite : les pages non
    authentifiées ne sont jamais comptées ; `reruns_total = 0` veut dire « personne ne
    s'est connecté », pas « personne n'a utilisé l'app » ; et `complete = TRUE`
    n'implique pas du trafic ce jour-là, la fenêtre étant un `rate(...[24h])`.

    **Le coût de ne pas l'avoir écrit** : ce zéro a été lu comme « le serveur ne mesure
    rien », conclusion publiée puis rétractée le même jour.

    ⚠️ Ce garde lit une DOCSTRING. Il vérifie qu'elle nomme la porte, pas qu'un lecteur
    en tire la bonne conclusion. C'est le maximum qu'un test puisse dire d'une
    déclaration en prose — et c'est précisément ce qui manquait.
    """
    doc = (_REPO / "src" / "utils" / "daily_ops_metrics.py").read_text(encoding="utf-8")
    head = doc.split('"""')[1] if '"""' in doc else ""
    assert "require_login" in head, (
        "le docstring de `daily_ops_metrics` ne nomme plus `require_login()`. Sans "
        "cela, rien ne dit que `reruns_total = 0` signifie « personne ne s'est "
        "CONNECTÉ » et non « personne n'a utilisé l'app » — la lecture qui a produit "
        "une conclusion fausse le 2026-09-17.")
    assert "n'observent pas" in head or "N'OBSERVENT PAS" in head, (
        "la section qui déclare le périmètre non observé a disparu du docstring")

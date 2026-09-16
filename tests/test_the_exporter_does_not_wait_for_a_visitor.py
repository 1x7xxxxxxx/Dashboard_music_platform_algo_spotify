"""L'instrument ne peut pas dépendre d'un utilisateur pour exister.

Type: Test
Uses: ast, pathlib
Depends on: src/dashboard/serve.py, Dockerfile, src/utils/metrics.py
Persists in: nothing

Ce qui a été mesuré
-------------------
2026-09-16, dans les minutes qui ont suivi un déploiement : le port 9102 n'écoutait pas,
la cible Prometheus `dashboard` était **`down`**, et `sum by (page)
(streamlytics_rerun_duration_seconds_count)` rendait **zéro page**. Tout allait bien.

`start_metrics_server()` n'était appelé que par `start_rerun()`, donc au PREMIER RENDU.
La durée de vie de l'instrument était accrochée à la visite d'un utilisateur : entre un
redémarrage et le premier visiteur — une nuit, un week-end — la surveillance était
absente, **et son absence ressemblait à une panne**.

C'est la forme la plus coûteuse de cette famille : un `down` permanent apprend à lire le
rouge comme du bruit, et le prochain vrai `down` passe avec lui.

Ce que ce test assert
---------------------
1. le lanceur démarre l'exportateur AVANT de rendre la main à Streamlit ;
2. le conteneur passe par le lanceur, pas par `streamlit run` directement ;
3. il ne le fait pas dans un autre PROCESSUS — ce qui exposerait un registre vide et
   rendrait la cible `up` en ne mesurant rien, **pire que `down`**.

Classe : `an-instrument-whose-lifetime-is-tied-to-a-visitor`.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SERVE = _ROOT / "src" / "dashboard" / "serve.py"
_DOCKERFILE = _ROOT / "Dockerfile"


def _main_fn():
    tree = ast.parse(_SERVE.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "main":
            return n
    return None


def _called_names(node) -> list[str]:
    """Les noms appelés, DANS L'ORDRE du source. Par l'AST, pas par `grep`."""
    calls = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            name = (f.id if isinstance(f, ast.Name)
                    else f.attr if isinstance(f, ast.Attribute) else None)
            if name:
                calls.append((getattr(n, "lineno", 0), name))
    return [name for _, name in sorted(calls)]


def test_the_exporter_starts_before_streamlit() -> None:
    fn = _main_fn()
    assert fn is not None, "`serve.main()` a disparu — le conteneur ne démarre plus rien"

    names = _called_names(fn)
    assert "start_metrics_server" in names, (
        f"`serve.main()` ne démarre pas l'exportateur (appels : {names}). Le port 9102 "
        "n'existerait qu'au premier rendu, et la cible Prometheus resterait `down` "
        "jusqu'à la première visite.")

    handoff = [n for n in names if n in {"main", "run"} and n != "start_metrics_server"]
    if handoff:
        assert names.index("start_metrics_server") < names.index(handoff[0]), (
            "l'exportateur démarre APRÈS la main passée à Streamlit — `stcli.main()` ne "
            "rend pas, donc la ligne suivante ne s'exécute jamais.")


def test_the_container_goes_through_the_launcher() -> None:
    """Le Dockerfile n'a pas d'arbre : le lire en texte est ici la bonne lecture."""
    text = _DOCKERFILE.read_text(encoding="utf-8")
    cmd = [ln for ln in text.splitlines() if ln.startswith("CMD ")]
    assert cmd, "aucune ligne `CMD` dans le Dockerfile"
    last = cmd[-1]

    assert "src.dashboard.serve" in last, (
        f"le conteneur ne passe pas par le lanceur : {last!r}. En appelant `streamlit "
        "run` directement, l'exportateur redevient dépendant du premier rendu.")

    assert "&" not in last.replace("&&", ""), (
        f"le `CMD` lance quelque chose en ARRIÈRE-PLAN : {last!r}. `prometheus_client` "
        "tient son registre en mémoire de PROCESSUS et Streamlit rend dans un THREAD du "
        "serveur : un exportateur démarré à côté exposerait un registre VIDE, et la "
        "cible serait `up` en ne mesurant rien — pire que `down`.")


def test_the_render_seam_still_starts_it_too() -> None:
    """La ceinture ET les bretelles, et ce n'est pas de la redondance inutile.

    Le lanceur couvre le conteneur. En développement, `streamlit run app.py` est lancé à
    la main et ne passe par aucun lanceur — l'appel depuis la couture reste donc le seul
    chemin qui instrumente ce cas-là. `start_metrics_server()` est idempotent : l'appeler
    deux fois ne coûte qu'un test de drapeau.
    """
    seam = (_ROOT / "src" / "dashboard" / "utils" / "metrics_seam.py").read_text(
        encoding="utf-8")
    tree = ast.parse(seam)
    names = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "start_metrics_server" in names, (
        "la couture de rendu ne démarre plus l'exportateur. Le conteneur est couvert par "
        "`serve.py`, mais un `streamlit run` lancé à la main en développement ne "
        "produirait plus aucune métrique — et on l'apprendrait en ne voyant rien.")

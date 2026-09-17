"""L'API mesure ce qu'elle sert, et son label de route reste borne.

Type: Sub
Uses: ast, prometheus_client, src.utils.http_metrics
Triggers: pytest
Depends on: src/utils/http_metrics.py, src/api/main.py, src/dashboard/serve.py
Persists in: —

Error classes `a-scrape-target-that-is-up-measuring-nothing`,
`a-metric-label-whose-cardinality-is-unbounded`.

Le defaut mesure le 2026-09-17
-------------------------------
La cible Prometheus `api` etait `up` et mesurait ZERO. Les quatre familles de
`metrics.py` sont declarees dans le registre de l'API par import transitif, mais aucun
`.inc()`, `.observe()` ni `.set()` n'y tournait jamais. Un service entier — routes,
latence, taux d'erreur — etait invisible, et la cible verte se lisait comme une
couverture. C'est le meme mode d'echec que `src/dashboard/serve.py` nomme « pire que
`down` ».

Les deux proprietes tenues ici
-------------------------------
1. **Le label `route` porte le PATRON, jamais l'URL brute.** Avec l'URL, chaque
   identifiant creerait sa serie : le nombre de series suivrait le nombre de ressources
   visitees, sans borne, et un scanner frappant mille chemins suffirait a faire refuser
   la cible par Prometheus.
2. **La jauge des defauts n'est installee QUE par le dashboard.** `metrics_payload()`
   de l'API fait `generate_latest()` sur le registre par defaut : si l'API installait le
   collecteur, Prometheus verrait deux series pour le meme fait, `sum()` doublerait, et
   l'API executerait la requete SQL a chaque scrutation.

Mutation record — 2026-09-17, trois mutations EXECUTEES et vues rouges :
  1. `_route_of` rend `request.url.path` (l'URL brute) au lieu du patron -> rouge ;
  2. un appel a `install_open_defects_collector()` ajoute dans `src/api/main.py` -> rouge ;
  3. l'appel a `install_http_metrics(app)` retire de `src/api/main.py` -> rouge.
0 apres remise en etat.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

pytest.importorskip("prometheus_client")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_API = _ROOT / "src" / "api" / "main.py"
_SERVE = _ROOT / "src" / "dashboard" / "serve.py"


def _calls(path: pathlib.Path) -> set[str]:
    """Les noms de fonctions APPELEES dans ce fichier — structure, pas texte.

    On lit l'AST et non le texte : ce fichier-ci, et les commentaires de `main.py`,
    nomment legitimement `install_open_defects_collector` en prose. Un garde textuel
    rougirait sur l'explication du defaut qu'il garde.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name:
                out.add(name)
    return out


def test_the_route_label_is_the_pattern_not_the_url():
    """Le coeur du garde de cardinalite."""
    from src.utils import http_metrics

    class _Req:
        scope = {"route": type("R", (), {"path": "/artists/{artist_id}"})()}
        url = type("U", (), {"path": "/artists/4177"})()

    got = http_metrics._route_of(_Req())
    assert got == "/artists/{artist_id}", (
        f"`_route_of` rend {got!r}. S'il rend un identifiant concret, chaque ressource "
        f"visitee cree sa serie : la cardinalite suit le trafic, sans borne. Prometheus "
        f"finit par refuser la cible, et la mesure disparait quand la charge monte."
    )


def test_a_request_that_matched_no_route_is_folded():
    """Un 404 n'a pas de patron — il ne doit pas rouvrir la cardinalite par derriere."""
    from src.utils import http_metrics

    class _Req:
        scope: dict = {}

    assert http_metrics._route_of(_Req()) == http_metrics._UNMATCHED


def test_the_api_installs_its_own_http_measurement():
    """Sans cet appel, la cible `api` redevient `up` en mesurant zero."""
    assert "install_http_metrics" in _calls(_API), (
        "`src/api/main.py` n'installe plus la mesure HTTP. Sa cible Prometheus "
        "resterait `up` en ne mesurant rien — mesure du 2026-09-17 : 4 familles "
        "declarees, 0 alimentee, un service entier invisible."
    )


def test_the_api_publishes_the_pool_it_enables():
    """`enable_pool()` enregistre des bornes ; il ne publie rien tout seul."""
    calls = _calls(_API)
    assert "enable_pool" in calls, "l'API n'active plus le pool — verifier avant tout"
    assert "publish_pool_metrics" in calls, (
        "L'API active le pool sans jamais publier son etat. "
        "`streamlytics_postgres_pool_connections` ne decrirait alors que le dashboard, "
        "alors que les deux processus se partagent `max_connections`."
    )


def test_only_the_dashboard_installs_the_defect_gauge():
    """Deux installations = deux series pour le meme fait, et `sum()` double."""
    assert "install_open_defects_collector" in _calls(_SERVE), (
        "`src/dashboard/serve.py` n'installe plus la jauge des defauts : le panneau "
        "des erreurs redeviendrait muet apres chaque redeploiement."
    )
    assert "install_open_defects_collector" not in _calls(_API), (
        "`src/api/main.py` installe la jauge des defauts. Les deux processus "
        "l'exposeraient, Prometheus verrait deux series pour le meme fait, `sum()` "
        "doublerait — et l'API executerait la requete SQL a chaque scrutation."
    )

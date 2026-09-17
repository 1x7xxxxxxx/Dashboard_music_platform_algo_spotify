"""Mesure les requetes HTTP de l'API : combien, quel statut, combien de temps.

Type: Utility
Uses: prometheus_client, starlette
Triggers: src/api/main.py (install_http_metrics)
Depends on: —
Persists in: rien

Pourquoi ce module existe
-------------------------
Mesure du 2026-09-17 : l'API declare les quatre familles de `metrics.py` dans son
registre et n'en alimente **aucune**. Sa cible Prometheus est donc `up` en mesurant zero
— exactement le mode d'echec que `src/dashboard/serve.py` decrit comme « pire que
`down` », parce qu'une cible verte se lit comme une couverture.

Un service entier etait invisible : ni volume de requetes, ni taux d'erreur, ni latence.

La cardinalite, qui est le seul vrai risque ici
------------------------------------------------
⚠️ Le label `route` porte le PATRON (`/artists/{artist_id}`), jamais l'URL brute. Avec
l'URL, chaque identifiant creerait sa serie : le nombre de series suivrait le nombre de
ressources visitees, sans borne, et Prometheus finirait par refuser la cible. Starlette
expose le patron dans `request.scope["route"].path` une fois le routage fait.

Une requete qui n'a atteint AUCUNE route (404, ou refus du limiteur avant routage) n'a
pas de patron : elle est comptee sous `__unmatched__`. Compter l'URL brute « juste pour
ces cas-la » rouvrirait le probleme par la porte de derriere — un scanner qui frappe mille
chemins inexistants suffirait.
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_NS = "streamlytics"
_LOCK = threading.Lock()
_INSTALLED = False

_UNMATCHED = "__unmatched__"

# Bornes choisies pour une API REST derriere Caddy, pas par defaut. Elles doivent couvrir
# le cas normal (quelques ms, une lecture indexee) et rendre lisible la degradation. La
# derniere borne est a 10 s, au-dela du `statement_timeout` de 15 s il n'y a plus de
# nuance a capturer — la requete est perdue de toute facon.
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def _route_of(request) -> str:
    """Le PATRON de route, ou `__unmatched__`. Ne leve jamais."""
    try:
        route = request.scope.get("route")
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            return path
    except Exception:                                          # noqa: BLE001
        pass
    return _UNMATCHED


def install_http_metrics(app, registry=None) -> bool:
    """Pose le middleware de mesure. Idempotent, ne leve jamais.

    Rend True si la mesure est en place.
    """
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return True
        try:
            from prometheus_client import Counter, Histogram
        except ImportError:
            return False

        kwargs = {"registry": registry} if registry is not None else {}

        def _once(factory, name, *args, **kw):
            try:
                return factory(name, *args, **kw, **kwargs)
            except ValueError:
                from prometheus_client import REGISTRY
                existing = REGISTRY._names_to_collectors.get(name)
                if existing is None:
                    raise
                return existing

        try:
            requests = _once(
                Counter, f"{_NS}_http_requests_total",
                "Requetes HTTP servies par l'API, par route, methode et statut.",
                ["route", "method", "status"])
            latency = _once(
                Histogram, f"{_NS}_http_request_duration_seconds",
                "Duree d'une requete HTTP de l'API, vue du serveur.",
                ["route", "method"], buckets=_BUCKETS)
        except Exception:                                      # noqa: BLE001
            return False

        @app.middleware("http")
        async def _measure(request, call_next):                # noqa: WPS430
            t0 = time.perf_counter()
            status = "500"
            try:
                response = await call_next(request)
                status = str(response.status_code)
                return response
            except Exception:
                # ⚠️ On compte AVANT de re-lever. Une exception non geree est exactement
                # le cas qu'on veut voir dans Grafana ; ne la compter que sur le chemin
                # heureux rendrait le taux d'erreur aveugle aux vraies erreurs.
                raise
            finally:
                # `route` n'est pose dans le scope QU'APRES le routage, donc il se lit
                # ici et pas au debut de la fonction.
                route = _route_of(request)
                method = getattr(request, "method", "?")
                try:
                    requests.labels(route=route, method=method, status=status).inc()
                    latency.labels(route=route, method=method).observe(
                        time.perf_counter() - t0)
                except Exception:                              # noqa: BLE001
                    pass

        _INSTALLED = True
        logger.info("mesure HTTP de l'API installee")
        return True

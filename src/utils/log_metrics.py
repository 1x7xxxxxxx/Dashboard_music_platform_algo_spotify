"""Compte les lignes de journal par niveau, sans en stocker aucune.

Type: Utility
Uses: logging, prometheus_client
Triggers: src/dashboard/serve.py, src/api/main.py
Depends on: —
Persists in: rien

Pourquoi un compteur et pas un collecteur de logs
--------------------------------------------------
ADR-026 rejette Loki, avec un declencheur ecrit : « un incident que les metriques ne
suffisent pas a expliquer ». Ce module ne le contredit pas — il n'agrege aucun TEXTE et
ne stocke aucune ligne. Il repond a une question differente et strictement metrique :
**combien de lignes de quel niveau, et depuis quel module**. Une pointe d'ERROR devient
visible dans Grafana sans qu'on ait a lire un seul journal.

Le handler n'ecrit nulle part. Il s'ajoute a la racine a cote des handlers existants
(Streamlit, uvicorn), donc il ne remplace rien et ne change aucune sortie.

⚠️ La cardinalite est la seule chose a surveiller ici. `logger` est TRONQUE au module de
deuxieme niveau — `src.collectors`, jamais `src.collectors.spotify_api_collector`. Sans
cette troncature, chaque module du depot creerait sa serie par niveau, et le nombre de
series suivrait la taille du code plutot que l'activite.

⚠️ **Ce compteur ne voit QUE ce qui atteint les handlers**, et c'est le niveau du logger
RACINE qui en decide. Mesure du 2026-09-17 dans le conteneur de production : la racine
est a **WARNING**. Le compteur enregistre donc les WARNING, ERROR et CRITICAL, et ne
verra JAMAIS un INFO ni un DEBUG — verifie par exécution, un `error()` incremente, un
`info()` non.

C'est une limite acceptee, pas un oubli : baisser le niveau de la racine pour compter
davantage changerait aussi ce qui S'IMPRIME, et ce module n'a pas a decider du journal.
Mais une limite tue est un instrument qui ment sur sa portee — d'ou
`streamlytics_log_level_floor`, publiee a cote du compteur : elle rend le seuil effectif
lisible dans Grafana, de sorte qu'un « 0 INFO » se lise « hors de portee » et non
« aucun ».

⚠️ Il n'est PAS installe dans les DAG : Airflow a son propre journal par tache, aucun
exportateur Airflow n'existe (ADR-026 n'en prevoit pas), et un processus de tache meurt
trop vite pour etre scrute.
"""
from __future__ import annotations

import logging
import threading

_NS = "streamlytics"
_LOCK = threading.Lock()
_INSTALLED = False

# Deux segments : `src.collectors`, `src.dashboard`, `src.api`… Le troisieme segment est
# le nom du module, et c'est lui qui ferait exploser le nombre de series.
_LOGGER_DEPTH = 2

_UNKNOWN = "?"


def _short(name: str) -> str:
    """Tronque au module de deuxieme niveau. Borne la cardinalite a ~10 valeurs."""
    if not name:
        return _UNKNOWN
    return ".".join(name.split(".")[:_LOGGER_DEPTH])


class _CountingHandler(logging.Handler):
    """Incremente un compteur. N'ecrit rien, ne formate rien, ne leve jamais.

    `emit` est appele sur le chemin de TOUT log du processus. Une exception ici serait
    avalee par `logging` (elle irait sur stderr via `handleError`), mais elle
    s'imprimerait a chaque ligne : le bruit noierait le journal qu'on pretend mesurer.
    """

    def __init__(self, counter) -> None:
        super().__init__(level=logging.DEBUG)
        self._counter = counter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._counter.labels(
                level=record.levelname or _UNKNOWN,
                logger=_short(record.name),
            ).inc()
        except Exception:                                      # noqa: BLE001
            pass

    # Le formatage est le cout principal d'un handler ordinaire. On ne formate jamais.
    def format(self, record: logging.LogRecord) -> str:        # pragma: no cover
        return ""


def install_log_counter(registry=None) -> bool:
    """Ajoute le handler a la racine. Idempotent, ne leve jamais.

    Rend True si le compteur est en place (installe maintenant ou deja).
    """
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return True
        try:
            from prometheus_client import Counter

            kwargs = {"registry": registry} if registry is not None else {}
            try:
                counter = Counter(
                    f"{_NS}_log_records_total",
                    "Lignes de journal emises, par niveau et par module de second rang.",
                    ["level", "logger"], **kwargs)
            except ValueError:
                # Deja enregistre : meme raison que `_once` dans metrics.py — ce depot
                # peut importer un module sous deux noms.
                from prometheus_client import REGISTRY
                counter = REGISTRY._names_to_collectors.get(f"{_NS}_log_records_total")
                if counter is None:
                    raise

            # ⚠️ Le PLANCHER, publie comme une metrique a part entiere. Sans lui, un
            # panneau montrant « 0 ligne INFO » se lirait « aucune », alors que la
            # verite est « hors de portee du compteur ». C'est la meme discipline que
            # `_read_ok` pour la jauge des defauts : ce que l'instrument ne peut pas
            # voir doit etre visible a cote de ce qu'il voit.
            try:
                from prometheus_client import Gauge

                floor = Gauge(
                    f"{_NS}_log_level_floor",
                    "Niveau effectif du logger racine (10=DEBUG, 20=INFO, 30=WARNING). "
                    "Le compteur de lignes ne voit RIEN en dessous de ce seuil.",
                    **kwargs)
                floor.set_function(lambda: float(logging.getLogger().getEffectiveLevel()))
            except ValueError:
                pass                       # deja enregistree : meme raison que ci-dessus

            handler = _CountingHandler(counter)
            root = logging.getLogger()
            root.addHandler(handler)
            # ⚠️ Le niveau de la RACINE decide de ce qui atteint les handlers. On ne le
            # baisse PAS : changer le niveau global pour compter davantage changerait
            # aussi ce qui s'imprime, et ce module n'a pas a decider du journal.
            _INSTALLED = True
            return True
        except Exception:                                      # noqa: BLE001
            return False

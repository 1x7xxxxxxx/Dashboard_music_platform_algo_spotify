"""Le compteur de journaux compte, il ne stocke ni ne formate.

Type: Sub
Uses: logging, prometheus_client, src.utils.log_metrics
Triggers: pytest
Depends on: src/utils/log_metrics.py
Persists in: —

Error class `a-log-counter-whose-cardinality-follows-the-codebase`.

Ce que ce garde protege
-----------------------
Compter les lignes de journal par niveau est une METRIQUE, pas du stockage de logs —
c'est ce qui le rend compatible avec ADR-026, qui rejette Loki. Mais un compteur etiquete
par nom de logger complet suivrait la TAILLE DU CODE au lieu de l'activite : chaque
module de `src/` creerait ses series, une par niveau. Le depot compte plus de 150 modules
et 5 niveaux : ~750 series pour une information que 10 lignes rendent aussi bien.

La propriete tenue : le label `logger` est tronque au module de DEUXIEME rang, donc le
nombre de valeurs possibles suit le nombre de paquets (`src.utils`, `src.collectors`,
`src.dashboard`…), jamais le nombre de fichiers.

Mutation record — 2026-09-17, deux mutations EXECUTEES et vues rouges :
  1. `_LOGGER_DEPTH` porte a 4 (le nom complet du module) -> rouge ;
  2. le handler retire du logger racine apres installation -> rouge sur le comptage.
0 apres remise en etat.
"""
from __future__ import annotations

import importlib
import logging

import pytest

pytest.importorskip("prometheus_client")
from prometheus_client import CollectorRegistry                # noqa: E402


@pytest.fixture()
def log_metrics():
    import src.utils.log_metrics as mod
    return importlib.reload(mod)


def _value(registry, level: str, logger_name: str) -> float:
    got = registry.get_sample_value(
        "streamlytics_log_records_total",
        {"level": level, "logger": logger_name})
    return got or 0.0


def test_a_log_line_increments_its_level(log_metrics):
    reg = CollectorRegistry()
    assert log_metrics.install_log_counter(registry=reg) is True
    try:
        logging.getLogger("src.utils.demo_module").error("boom")
        assert _value(reg, "ERROR", "src.utils") == 1.0, (
            "Une ligne ERROR n'a pas incremente le compteur. Le handler est-il bien "
            "attache au logger RACINE ?"
        )
    finally:
        logging.getLogger().handlers = [
            h for h in logging.getLogger().handlers
            if not isinstance(h, log_metrics._CountingHandler)]


def test_the_logger_label_is_truncated_to_the_package(log_metrics):
    """Deux modules du meme paquet partagent UNE serie, pas deux."""
    assert log_metrics._short("src.collectors.spotify_api_collector") == "src.collectors"
    assert log_metrics._short("src.collectors.youtube_collector") == "src.collectors"
    assert log_metrics._short("src.utils.metrics") == "src.utils"
    assert log_metrics._short("") == log_metrics._UNKNOWN


def test_the_cardinality_follows_packages_not_files(log_metrics):
    """Le vrai enonce du garde, sur des noms reels du depot."""
    real_modules = [
        "src.collectors.spotify_api_collector",
        "src.collectors.youtube_collector",
        "src.collectors.soundcloud_api_collector",
        "src.dashboard.views.home",
        "src.dashboard.views.kpis",
        "src.dashboard.utils.error_alert",
        "src.utils.metrics",
        "src.utils.defect_gauge",
    ]
    labels = {log_metrics._short(m) for m in real_modules}
    assert labels == {"src.collectors", "src.dashboard", "src.utils"}, (
        f"Le label `logger` rend {sorted(labels)} pour 8 modules de 3 paquets. "
        f"S'il en rend plus de 3, la cardinalite suit les FICHIERS : le nombre de "
        f"series croitrait avec la taille du code, pas avec l'activite."
    )


def test_the_handler_never_formats(log_metrics):
    """Le formatage est le cout d'un handler ordinaire ; celui-ci n'en paie aucun."""
    reg = CollectorRegistry()
    log_metrics.install_log_counter(registry=reg)
    handler = next(h for h in logging.getLogger().handlers
                   if isinstance(h, log_metrics._CountingHandler))
    try:
        record = logging.LogRecord("src.utils.x", logging.INFO, __file__, 1,
                                   "message %s", ("arg",), None)
        assert handler.format(record) == "", (
            "Le handler formate le message. Sur le chemin de CHAQUE ligne de journal "
            "du processus, c'est un cout paye pour une chaine que personne ne lit."
        )
    finally:
        logging.getLogger().handlers = [
            h for h in logging.getLogger().handlers
            if not isinstance(h, log_metrics._CountingHandler)]


def test_a_broken_counter_never_breaks_logging(log_metrics):
    """`emit` avale tout : un compteur casse ne doit pas bruiter chaque ligne."""
    class _Exploding:
        def labels(self, **kwargs):
            raise RuntimeError("registry gone")

    handler = log_metrics._CountingHandler(_Exploding())
    record = logging.LogRecord("src.utils.x", logging.ERROR, __file__, 1, "m", (), None)
    handler.emit(record)          # ne doit pas lever

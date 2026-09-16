"""Le résumé QUOTIDIEN des métriques, écrit en base depuis Prometheus.

Type: Utility
Uses: requests (API Prometheus), src.database.postgres_handler
Triggers: la tâche `write_daily_ops_metrics` du DAG `alert_monitor` (23 h UTC)
Persists in: daily_ops_metrics (migration 125)

Pourquoi deux stockages, et pas un
-----------------------------------
Prometheus garde 30 jours à haute fréquence — c'est ce qu'il fait bien, et c'est ce que
Grafana lit. Mais **sa base meurt avec le conteneur**, et rien n'y est interrogeable en
SQL à côté des données métier. Une question comme « nos rendus se sont-ils dégradés
depuis qu'on a trois locataires de plus ? » se pose sur des MOIS et croise
`saas_artists` : Prometheus ne sait répondre ni à l'un ni à l'autre.

L'inverse — tout écrire en Postgres — coûterait une écriture par rendu sur le chemin
chaud, et ferait de Postgres une base de séries temporelles qu'il n'est pas.

Une seule source, et c'est le point
------------------------------------
Les chiffres viennent de **l'API de Prometheus**, jamais d'une seconde instrumentation.
Deux chemins de mesure pour la même grandeur divergent, et personne ne sait lequel
croire — ce dépôt a payé cette classe sur cinq surfaces qui affichaient deux totaux
différents au même instant (ADR-019).

Ce que ce module fait quand Prometheus ne répond pas
-----------------------------------------------------
Il écrit quand même la ligne, avec `complete = FALSE`. Une ligne incomplète vaut mieux
qu'une absence : **l'absence se lit comme « la surveillance n'a pas tourné »**, ce qui
est un autre problème et enverrait chercher au mauvais endroit.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://streamlytics_prometheus:9090")
_TIMEOUT_S = 15

# Une requête par colonne. Écrites ici plutôt que dans le DAG : c'est de la connaissance
# sur les métriques, pas sur l'ordonnancement, et le DAG fait déjà 2 700 lignes.
#
# ⚠️ `[24h]` et non `[1d]` : la fenêtre doit couvrir la journée qu'on résume, et la tâche
# tourne à 23 h UTC — elle décrit donc les 24 heures écoulées, pas une journée
# calendaire. Le nom de colonne `day` porte la date de CETTE fenêtre.
_QUERIES: dict[str, str] = {
    "p50_render_ms": 'histogram_quantile(0.50, sum by (le) '
                     '(rate(streamlytics_rerun_duration_seconds_bucket[24h]))) * 1000',
    "p95_render_ms": 'histogram_quantile(0.95, sum by (le) '
                     '(rate(streamlytics_rerun_duration_seconds_bucket[24h]))) * 1000',
    "p95_chrome_ms": 'histogram_quantile(0.95, sum by (le) '
                     '(rate(streamlytics_rerun_duration_seconds_bucket'
                     '{phase="chrome"}[24h]))) * 1000',
    "p95_view_ms": 'histogram_quantile(0.95, sum by (le) '
                   '(rate(streamlytics_rerun_duration_seconds_bucket'
                   '{phase="view"}[24h]))) * 1000',
    "reruns_total": 'sum(increase(streamlytics_rerun_duration_seconds_count[24h]))',
    "pool_high_water": 'max_over_time('
                       'streamlytics_postgres_pool_connections{state="borrowed"}[24h])',
    "pool_direct_fallbacks": 'max_over_time('
                             'streamlytics_postgres_pool_connections'
                             '{state="direct_fallback"}[24h])',
    "cpu_max_pct": 'max_over_time((100 - (avg(rate(node_cpu_seconds_total'
                   '{mode="idle"}[5m])) * 100))[24h:5m])',
    "ram_max_pct": 'max_over_time(((1 - node_memory_MemAvailable_bytes / '
                   'node_memory_MemTotal_bytes) * 100)[24h:5m])',
    "disk_pct": '(1 - node_filesystem_avail_bytes{mountpoint="/"} / '
                'node_filesystem_size_bytes{mountpoint="/"}) * 100',
}


def _query(expr: str):
    """Une valeur scalaire depuis Prometheus, ou None. Ne lève jamais."""
    try:
        import requests

        r = requests.get(f"{PROMETHEUS_URL}/api/v1/query",
                         params={"query": expr}, timeout=_TIMEOUT_S)
        r.raise_for_status()
        payload = r.json()
        if payload.get("status") != "success":
            return None
        result = (payload.get("data") or {}).get("result") or []
        if not result:
            return None
        value = float(result[0]["value"][1])
        # Prometheus rend `NaN` en texte pour un quantile sans échantillon.
        return None if value != value else value
    except Exception as exc:  # noqa: BLE001 — une métrique absente n'est pas une panne
        logger.warning("requête Prometheus en échec (%s) : %s",
                       type(exc).__name__, expr[:60])
        return None


def _errors_by_page() -> dict:
    """{page: nombre} sur 24 h. Dictionnaire vide si illisible."""
    try:
        import requests

        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": 'sum by (page) '
                             '(increase(streamlytics_app_errors_total[24h]))'},
            timeout=_TIMEOUT_S)
        r.raise_for_status()
        out: dict[str, int] = {}
        for row in (r.json().get("data") or {}).get("result") or []:
            page = (row.get("metric") or {}).get("page", "?")
            out[page] = int(float(row["value"][1]))
        return {k: v for k, v in out.items() if v > 0}
    except Exception:  # noqa: BLE001
        return {}


def _peak_sessions(db) -> int | None:
    """Pic de sessions HUMAINES en une minute sur 24 h.

    ⚠️ Exclut les canaris et le bac à sable, et ce n'est pas un détail : un comptage qui
    les incluait rapprochait artificiellement un seuil de charge de son déclencheur —
    320 des 1 043 événements d'une journée venaient du locataire `sandbox`, c'est-à-dire
    de nous. Un canari n'a jamais été un utilisateur.
    """
    try:
        rows = db.fetch_query("""
            SELECT max(n) FROM (
                SELECT count(DISTINCT u.session_id) AS n
                  FROM usage_events u
                  JOIN saas_artists a ON a.id = u.artist_id
                 WHERE u.ts >= now() - interval '24 hours'
                   AND COALESCE(a.is_canary, FALSE) = FALSE
                   AND COALESCE(a.is_sandbox, FALSE) = FALSE
                 GROUP BY date_trunc('minute', u.ts)
            ) per_minute
        """)
        return int(rows[0][0]) if rows and rows[0][0] is not None else 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("pic de sessions illisible (%s)", type(exc).__name__)
        return None


def collect(db, day: date | None = None) -> dict:
    """Rassemble le résumé du jour. Ne lève jamais ; marque `complete` honnêtement."""
    day = day or (date.today() - timedelta(days=0))
    values: dict = {"day": day}
    missing: list[str] = []

    for column, expr in _QUERIES.items():
        v = _query(expr)
        if v is None:
            missing.append(column)
        values[column] = None if v is None else (
            int(round(v)) if column.endswith(("_ms", "_total", "_water", "_fallbacks"))
            else round(v, 2))

    values["errors_by_page"] = _errors_by_page()
    peak = _peak_sessions(db)
    values["peak_sessions"] = peak
    if peak is None:
        missing.append("peak_sessions")

    values["complete"] = not missing
    if missing:
        logger.warning("résumé quotidien INCOMPLET — colonnes absentes : %s",
                       ", ".join(missing))
    return values


# Les colonnes que ce module a le droit d'écrire. Règle transverse #8 : tout nom de
# colonne interpolé dans une f-string se valide contre un `frozenset` AVANT exécution.
#
# Ici les noms viennent de `_QUERIES`, donc de ce fichier — mais c'est exactement le
# raisonnement qui rend la règle facile à contourner, et le dépôt a une classe pour
# ça : la constante d'aujourd'hui est le paramètre de demain. La liste est donc écrite
# une seconde fois, à la main, pour que l'ajout d'une clé dans `_QUERIES` ne suffise
# PAS à ouvrir une colonne — il faut le vouloir deux fois.
_WRITABLE_COLUMNS = frozenset({
    "p50_render_ms", "p95_render_ms", "p95_chrome_ms", "p95_view_ms",
    "peak_sessions", "reruns_total", "pool_high_water", "pool_direct_fallbacks",
    "cpu_max_pct", "ram_max_pct", "disk_pct", "errors_by_page", "complete",
})


def write(db, day: date | None = None) -> dict:
    """Écrit (ou remplace) la ligne du jour. Rend ce qui a été écrit.

    `ON CONFLICT ... DO UPDATE` : rejouer la tâche doit corriger la ligne, pas en
    empiler une seconde. Une journée a un seul résumé.
    """
    values = collect(db, day)
    cols = [c for c in values if c != "day"]
    unknown = sorted(set(cols) - _WRITABLE_COLUMNS)
    if unknown:
        raise ValueError(
            f"colonne(s) hors allowlist : {unknown}. Règle transverse #8 — un nom de "
            "colonne interpolé se valide contre un frozenset avant exécution. Ajouter "
            "la colonne à `_WRITABLE_COLUMNS` ET à la migration, dans cet ordre.")
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)
    placeholders = ", ".join(["%s"] * (len(cols) + 1))
    import json

    params = [values["day"]] + [
        json.dumps(values[c]) if c == "errors_by_page" else values[c] for c in cols]
    db.execute_query(
        f"INSERT INTO daily_ops_metrics (day, {', '.join(cols)}) "  # noqa: S608
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (day) DO UPDATE SET {sets}, written_at = now()",
        tuple(params))
    logger.info("résumé du %s écrit (complet=%s)", values["day"], values["complete"])
    return values

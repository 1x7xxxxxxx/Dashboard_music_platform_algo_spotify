"""Expose les defauts OUVERTS de `app_error_log` a Prometheus, sans jamais mentir.

Type: Utility
Uses: prometheus_client, PostgresHandler
Triggers: src/dashboard/serve.py (install_open_defects_collector)
Depends on: app_error_log (migration 083)
Persists in: rien — lecture seule

Pourquoi ce module existe
-------------------------
`streamlytics_app_errors_total` est un COMPTEUR d'exceptions, et il est correct. Mais un
Counter a labels de `prometheus_client` n'a **aucune serie** tant qu'aucun couple
`(page, error_class)` n'a ete incremente, et son registre vit en memoire de PROCESSUS :
il repart vide a chaque redeploiement. Le panneau Grafana affiche donc « No data », ce
qui n'est pas zero — c'est « aucune observation ».

`app_error_log`, elle, survit. Une ligne par DEFAUT (empreinte), avec sa `page`. Ce
module l'expose, a cote du compteur, parce que les deux repondent a deux questions :

    compteur : il vient de se passer quelque chose
    jauge    : il reste N defauts ouverts, meme apres un redeploiement

⚠️ Ce module n'est PAS importe par `metrics.py`, et ce n'est pas un detail. `metrics.py`
promet de n'ouvrir aucune connexion a l'import, et c'est lui que l'API importe pour
servir `/metrics`. Si le collecteur vivait la, l'API l'exposerait aussi : Prometheus
verrait deux series pour le meme fait, `sum()` doublerait, et l'API executerait la
requete a chaque scrutation. L'installation est donc OPT-IN, depuis `serve.py` seul.

Le choix d'un Collector plutot que d'une Gauge
----------------------------------------------
Une `Gauge` ordinaire garde ses jeux de labels POUR TOUJOURS. Un defaut ferme resterait
affiche a sa derniere valeur, et le remede (`.clear()` puis re-`set()`) ouvre une fenetre
ou une scrutation voit un vide qui n'existe pas. Un Collector reconstruit ses echantillons
a chaque appel : il n'a aucun etat de labels a perimer.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_NS = "streamlytics"

# Le TTL borne la charge : Prometheus scrute toutes les 15 s, donc au plus 2 requetes par
# minute au lieu de 4. Il est court devant la duree de vie d'un defaut (des heures), donc
# il ne fait perdre aucune information utile.
_TTL_SECONDS = 30.0

# ⚠️ 2 s, et le chiffre est DERIVE, pas choisi. `collect()` tourne dans le thread de
# l'exportateur : une requete pendue ferait expirer la scrutation (`scrape_timeout: 10s`)
# et emporterait TOUTES les autres metriques du dashboard avec elle. Le
# `statement_timeout` du pool vaut 15 s, donc il ne protege pas ici. 2 s laisse huit
# secondes de marge sous le delai de scrutation.
_STATEMENT_TIMEOUT_MS = 2000

# Borne de cardinalite. La population reelle est le backlog humain de defauts ouverts —
# 0 en production le 2026-09-17, moins de 30 de facon realiste. Le pire cas theorique
# (46 pages x ~40 types d'exception) vaut ~1800, d'ou un plafond plutot qu'une confiance.
_MAX_SERIES = 100
_OTHER = "__other__"

_LOCK = threading.Lock()
_INSTALLED = False
_WARNED_TRUNCATION = [False]


class _Snapshot:
    """Ce qu'une lecture a rendu — ou le fait qu'elle a echoue.

    `rows` est None quand la lecture a echoue. C'est la distinction que tout ce module
    existe pour preserver : une liste VIDE est un fait (aucun defaut ouvert), None est
    une ignorance. Les confondre produit un tableau de bord qui affiche « 0 defaut »
    pendant une panne de base.
    """

    __slots__ = ("rows", "sessions", "taken_at", "last_success")

    def __init__(self) -> None:
        self.rows: Optional[list[tuple[str, str, int]]] = None
        self.sessions: Optional[tuple[float, float]] = None
        self.taken_at: float = 0.0
        self.last_success: float = 0.0


_SNAP = _Snapshot()


def _fetch_sessions(db) -> tuple[float, float]:
    """Les deux facons de compter les gens, qui repondent a deux questions.

    `active_artists` vient de `active_sessions` : une ligne par artiste, ecrasee, avec un
    battement throttle a 1/60 s. Elle SAUTE les admins (`artist_id is None`), donc c'est
    « artistes vivants », pas « sessions ».

    `sessions_1m` vient de `usage_events` : le nombre de `session_id` distincts sur la
    derniere minute. C'est **exactement la grandeur du declencheur n°1 de
    `tools/scale_check.sh`**, qui vivait en SQL et n'etait visible nulle part en continu.
    On exclut canari et bac a sable, comme le script — sans quoi 31 % des evenements
    d'une journee mesuree venaient du bac a sable.

    ⚠️ Aucun label de locataire, ici ni ailleurs : `grafana-correspondence.md` refuse une
    cardinalite qui croitrait avec le nombre de clients.
    """
    artists = db.fetch_query(
        "SELECT COUNT(*) FROM active_sessions "
        "WHERE last_heartbeat > now() - interval '5 minutes'")
    sessions = db.fetch_query(
        """
        SELECT COUNT(DISTINCT u.session_id)
        FROM usage_events u
        LEFT JOIN saas_artists a ON a.id = u.artist_id
        WHERE u.ts > now() - interval '1 minute'
          AND COALESCE(a.is_canary, FALSE) = FALSE
          AND COALESCE(a.is_sandbox, FALSE) = FALSE
        """)
    return (float((artists or [[0]])[0][0]), float((sessions or [[0]])[0][0]))


def _fetch(db_factory):
    """Lit les defauts ouverts. LEVE si la base ne repond pas — l'appelant tranche.

    ⚠️ Le label est `exc_type`, PAS la colonne `error_class`. Les deux existent et ne
    veulent pas dire la meme chose : `count_error()` passe `type(exc).__name__`, tandis
    que `app_error_log.error_class` est la cle du catalogue `.claude/dev-docs/
    error-classes.md`, NULL sur presque toutes les lignes. Les melanger donnerait deux
    labels homonymes qui ne se rejoignent jamais dans une requete.
    """
    db = db_factory()
    try:
        db.execute_query(f"SET statement_timeout = {_STATEMENT_TIMEOUT_MS}")
        sessions = _fetch_sessions(db)
        rows = db.fetch_query(
            """
            SELECT COALESCE(NULLIF(page, ''), '?')     AS page,
                   COALESCE(NULLIF(exc_type, ''), '?') AS exc_type,
                   COUNT(*)                            AS n
            FROM app_error_log
            WHERE resolved_at IS NULL
            GROUP BY 1, 2
            -- `NULLS LAST` explicite. `COUNT(*)` ne rend jamais NULL, donc rien ne
            -- changerait ici — mais PostgreSQL place les NULL EN PREMIER sur un DESC,
            -- et `tests/test_a_parameterised_query_says_what_it_means.py` refuse un
            -- classement decroissant qui ne dit pas ce qu'il fait des vides. Le dire
            -- coute un mot ; le supposer a deja fait choisir un groupe vide ailleurs.
            ORDER BY 3 DESC NULLS LAST
            LIMIT %s
            """,
            (_MAX_SERIES + 1,),
        )
    finally:
        try:
            db.close()
        except Exception:                                      # noqa: BLE001
            pass
    return [(str(r[0])[:120], str(r[1])[:120], int(r[2])) for r in (rows or [])], sessions


def _fold(rows: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    """Replie la queue au-dela du plafond, en CONSERVANT la somme.

    Tronquer perdrait des defauts en silence ; replier garde `sum()` exact et rend la
    troncature visible par une serie nommee.
    """
    if len(rows) <= _MAX_SERIES:
        return rows
    head = rows[:_MAX_SERIES]
    tail_total = sum(n for _p, _e, n in rows[_MAX_SERIES:])
    if not _WARNED_TRUNCATION[0]:
        _WARNED_TRUNCATION[0] = True
        logger.warning(
            "defauts ouverts : %d series depassent le plafond de %d — la queue est "
            "repliee dans %s, la somme reste exacte",
            len(rows), _MAX_SERIES, _OTHER)
    return head + [(_OTHER, _OTHER, tail_total)]


def _refresh(db_factory) -> None:
    """Rafraichit le snapshot si le TTL est expire. Ne leve jamais.

    En cas d'echec, le snapshot est JETE (`rows = None`) et non servi perime. Servir une
    valeur ancienne serait le troisieme mensonge possible, apres le zero invente et la
    valeur figee : elle se lirait comme une mesure fraiche.
    """
    now = time.monotonic()
    if _SNAP.rows is not None and (now - _SNAP.taken_at) < _TTL_SECONDS:
        return
    try:
        rows, sessions = _fetch(db_factory)
        rows = _fold(rows)
    except Exception as exc:                                   # noqa: BLE001
        _SNAP.rows = None
        _SNAP.sessions = None
        _SNAP.taken_at = now
        logger.warning("defauts ouverts illisibles (%s) — la jauge se declare aveugle "
                       "plutot que de rendre zero", type(exc).__name__)
        return
    _SNAP.rows = rows
    _SNAP.sessions = sessions
    _SNAP.taken_at = now
    _SNAP.last_success = time.time()


class OpenDefectsCollector:
    """Trois series, parce qu'une jauge ne peut pas porter deux informations.

    `..._read_ok` est SANS label et TOUJOURS emise : c'est elle qui porte le
    « sait-on, ou pas », precisement parce qu'elle ne derive d'aucune ligne. La jauge
    principale, elle, n'est emise qu'apres une lecture reussie.

    Consequence assumee : `absent(streamlytics_open_defects)` est ambigu par construction
    — zero defaut reel, ou lecture morte. La desambiguisation est dans `read_ok`, qui ne
    peut pas mentir par absence de lignes.
    """

    def __init__(self, db_factory) -> None:
        self._db_factory = db_factory

    def collect(self):                                          # noqa: D102
        from prometheus_client.core import GaugeMetricFamily

        _refresh(self._db_factory)

        ok = GaugeMetricFamily(
            f"{_NS}_open_defects_read_ok",
            "1 si la derniere lecture de app_error_log a reussi, 0 sinon. "
            "TOUJOURS emise : c'est elle qui distingue « aucun defaut » de « aveugle ».")
        ok.add_metric([], 1.0 if _SNAP.rows is not None else 0.0)
        yield ok

        last = GaugeMetricFamily(
            f"{_NS}_open_defects_last_success_timestamp_seconds",
            "Horodatage unix de la derniere lecture reussie. 0 si jamais reussi — "
            "ce qui distingue un processus froid d'une panne longue.")
        last.add_metric([], _SNAP.last_success)
        yield last

        if _SNAP.rows is None:
            return                      # AUCUN echantillon : surtout pas un zero invente

        # ⚠️ Ce `if` est REDONDANT et il est gardé sciemment : le `return` ci-dessus
        # protège déjà ce bloc. Mesuré le 2026-09-17 — le remplacer par `if True:`
        # laisse le garde VERT, parce que l'exécution n'arrive jamais ici en cas
        # d'échec. Ce qui garde réellement, c'est le `return` ; le seul mutant rouge
        # est le déplacement de ce bloc AVANT lui. Écrit ici pour qu'on ne prenne pas
        # cette ligne pour la protection qu'elle n'est pas.
        if _SNAP.sessions is not None:
            artists, sessions_1m = _SNAP.sessions
            g = GaugeMetricFamily(
                f"{_NS}_active_artists",
                "Artistes dont le battement date de moins de 5 minutes. "
                "N'inclut PAS les admins : ils n'ont pas d'artist_id.")
            g.add_metric([], artists)
            yield g
            g2 = GaugeMetricFamily(
                f"{_NS}_sessions_1m",
                "Sessions distinctes sur la derniere minute, canari et bac a sable "
                "exclus. Meme grandeur que le declencheur n1 de tools/scale_check.sh.")
            g2.add_metric([], sessions_1m)
            yield g2

        defects = GaugeMetricFamily(
            f"{_NS}_open_defects",
            "Defauts non resolus de app_error_log, par page et type d'exception. "
            "Survit aux redeploiements, contrairement au compteur d'exceptions.",
            labels=["page", "error_class"])
        for page, exc_type, n in _SNAP.rows:
            defects.add_metric([page, exc_type], float(n))
        yield defects


def install_open_defects_collector(db_factory: Any = None) -> bool:
    """Enregistre le collecteur. Idempotent, ne leve jamais, rend True si installe.

    Appelee SEULEMENT depuis `src/dashboard/serve.py` — voir l'avertissement en tete de
    module sur le double comptage cote API.
    """
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return True
        try:
            from prometheus_client import REGISTRY

            if db_factory is None:
                def db_factory():                               # noqa: WPS440
                    from src.database.postgres_handler import PostgresHandler
                    return PostgresHandler.from_env_or_config()

            REGISTRY.register(OpenDefectsCollector(db_factory))
            _INSTALLED = True
            logger.info("jauge des defauts ouverts enregistree")
            return True
        except Exception as exc:                                # noqa: BLE001
            logger.warning("jauge des defauts ouverts non enregistree (%s) — le "
                           "dashboard demarre quand meme", type(exc).__name__)
            return False

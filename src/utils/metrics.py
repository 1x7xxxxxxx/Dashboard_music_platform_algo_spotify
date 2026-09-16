"""Les métriques du produit — UNE porte, deux surfaces.

Type: Utility
Uses: prometheus_client (pur Python) ; rien d'autre à l'import
Triggers: chaque rendu Streamlit, chaque requête FastAPI
Persists in: nothing (Prometheus les scrute ; le résumé quotidien va en base)

Pourquoi ce module existe, et pourquoi il est UNIQUE
----------------------------------------------------
ADR-026 adopte trois conteneurs et quatre familles de métriques. Les deux processus
applicatifs les exposent, et ils les déclarent **ici**. Le dépôt a déjà payé le prix
d'une seconde copie : le parseur `X-Forwarded-For` de l'API était faux, une copie faite
avant le correctif l'aurait été aussi, et rien ne l'aurait dit. Une métrique déclarée
deux fois diverge de la même façon — même nom, buckets différents, et deux courbes qui
ne se superposent pas sans qu'on sache laquelle croire.

Ce que ce module mesure, et pourquoi chaque ligne
--------------------------------------------------
**`streamlit_rerun_duration_seconds{page,phase}`** — l'histogramme qui manquait. Le seul
chronomètre existant (`app.py:975`) mesure `_render_page` et **exclut la barre
latérale**. Le label `phase` sépare `chrome` (auth, navigation, barre latérale) de
`view`. **C'est la correction d'un angle mort, pas un ajout.**

⚠️ On a longtemps écrit ici que la chrome pesait « un facteur 8 » de plus que la vue.
C'était FAUX, et la mesure qui le dit est celle que ce module a rendue possible : côté
SERVEUR le 2026-09-16, sur 8 pages, la chrome est PLATE à 11-13 ms et c'est la VUE qui
domine — de 4,6× (`saisie_s4a`) à 63× (`meta_mapping`, 777 ms).

Le chiffre venait d'une soustraction jamais faite : `468-538 ms` est mesuré sous
`AppTest`, dont le plancher pour `st.write('hello')` vaut **352 ms** dans le même
conteneur (`tools/loadtest_dashboard.py:30-33`). Le reste réel valait ~116-186 ms — et
`instagram`, mesuré ici, vaut 12 + 96 = 108 ms. Ce qu'on prenait pour la barre latérale
était le harnais.

L'angle mort reste réel : une seule des deux phases était mesurée. Ce qui a changé, c'est
laquelle pèse.

**`streamlit_reruns_in_flight`** — la file d'attente rendue visible. Streamlit sérialise
les reruns dans un processus ; cette jauge dit si les « reruns perdus » mesurés côté
client sont une file SERVEUR ou un client saturé. C'est le croisement qui tranchera
R119, et aucune mesure client ne peut le faire seule.

**`postgres_pool_connections{state}`** — le pool est à `maxconn=8` et **rien ne dit s'il
sature**. Pire : `_borrow_from_pool()` retombe sur une connexion DIRECTE en cas d'échec,
avec un simple `logger.warning` — une saturation se dégrade donc **en silence**, et rien
ne la distingue d'un fonctionnement normal. `state="direct_fallback"` est précisément ce
compteur manquant.

**`app_errors_total{page,error_class}`** — adossé au registre `app_error_log` qui existe.

Ce que ce module ne fait PAS
-----------------------------
Il ne démarre aucun serveur à l'import, n'ouvre aucune connexion, et **ne lève jamais**.
Une métrique ratée est une métrique ratée ; elle ne doit jamais devenir une page
d'erreur. C'est la même règle que `cache_epoch` et que les seaux de limitation.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Le préfixe. Un seul, pour que `{__name__=~"streamlytics_.*"}` cadre tout le produit.
_NS = "streamlytics"

# Port latéral du dashboard. L'API, elle, expose `/metrics` sur son port HTTP ordinaire :
# elle a déjà un serveur, lui en ajouter un second n'achèterait rien.
METRICS_PORT = int(os.getenv("STREAMLIT_METRICS_PORT", "9102"))

# ⚠️ LE DRAPEAU, et c'est le point délicat de toute l'étape.
#
# Streamlit RÉ-EXÉCUTE le script entier à chaque rerun. Sans ce drapeau, chaque rerun
# rappelle `start_http_server()` sur un port déjà lié.
#
# ⚠️ Correction d'une première rédaction, qui disait « la page tombe au premier clic ».
# C'est FAUX, et la mutation l'a montré : la capture d'`OSError` plus bas suffit à ne
# pas lever. Ce que le drapeau évite est plus modeste et bien réel — une tentative de
# liaison et une ligne d'avertissement à CHAQUE rerun, soit cent tentatives sur une page
# cliquée cent fois. Écrire la conséquence plus grave qu'elle n'est fait croire qu'un
# test qui ne lève pas prouve quelque chose.
#
# Un booléen de module suffit et c'est correct ici : il est par PROCESSUS, et c'est
# exactement la portée du serveur qu'il garde. Le verrou couvre le cas de deux sessions
# qui arrivent ensemble sur un processus froid.
_SERVER_STARTED = False
_SERVER_LOCK = threading.Lock()

_REGISTRY_READY = False


def _build():
    """Déclare les métriques une fois. Rend None si prometheus_client est absent."""
    global _REGISTRY_READY
    try:
        from prometheus_client import Counter, Gauge, Histogram
    except ImportError:          # l'observabilité est optionnelle, le produit non
        return None

    # Bornes choisies sur les mesures existantes, pas par défaut : 61 ms (vue seule),
    # 317-329 ms (p50 à un onglet), 468-538 ms (page complète), 1,5 s (le seuil
    # d'ADR-007 sur `trigger_algo`), 3 s (le seuil de `RenderLatencyDegraded`, qui a herite du rouge de
    # `perf_monitor` quand cette vue a ete retiree).
    buckets = (0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0)

    def _once(factory, name, *args, **kwargs):
        """Déclare la métrique, ou RÉCUPÈRE celle qui est déjà là.

        ⚠️ `prometheus_client` LÈVE si un nom est enregistré deux fois dans le registre
        par défaut. Ce n'est pas un cas de test : ce dépôt met `src/dashboard` sur
        `sys.path` et importe ses vues comme `views.x`, donc un même module peut être
        chargé sous deux noms — et le second import ferait tomber le DASHBOARD À
        L'IMPORT, avant qu'une seule ligne ne s'affiche.

        On relit alors le collecteur déjà enregistré plutôt que d'en créer un second :
        deux collecteurs du même nom donneraient deux séries qui ne se somment pas.
        """
        try:
            return factory(name, *args, **kwargs)
        except ValueError:
            from prometheus_client import REGISTRY

            existing = REGISTRY._names_to_collectors.get(name)
            if existing is None:
                raise
            logger.debug("métrique %s déjà enregistrée — réutilisée", name)
            return existing

    m = {
        "rerun": _once(
            Histogram, f"{_NS}_rerun_duration_seconds",
            "Durée d'un rendu Streamlit, vue du SERVEUR.",
            ["page", "phase"], buckets=buckets),
        "in_flight": _once(
            Gauge, f"{_NS}_reruns_in_flight",
            "Rendus en cours dans ce processus — la file d'attente."),
        "pool": _once(
            Gauge, f"{_NS}_postgres_pool_connections",
            "Connexions du pool par état.", ["state"]),
        "errors": _once(
            Counter, f"{_NS}_app_errors_total",
            "Erreurs applicatives, par page et par classe.", ["page", "error_class"]),
    }
    _REGISTRY_READY = True
    return m


_M = _build()


def start_metrics_server() -> bool:
    """Démarre le serveur de métriques du dashboard. Idempotent. Ne lève jamais.

    Rend True si le serveur tourne (démarré maintenant ou déjà), False sinon.
    """
    global _SERVER_STARTED
    if _M is None:
        return False
    with _SERVER_LOCK:
        if _SERVER_STARTED:
            return True
        try:
            from prometheus_client import start_http_server

            # `addr` explicite : sans lui, le serveur écoute sur 0.0.0.0 et la métrique
            # devient joignable de l'extérieur du conteneur. Prometheus scrute depuis
            # le réseau Docker, pas depuis Internet.
            start_http_server(METRICS_PORT, addr=os.getenv("METRICS_ADDR", "0.0.0.0"))
            _SERVER_STARTED = True
            logger.info("métriques exposées sur :%d", METRICS_PORT)
            return True
        except OSError as exc:
            # Port déjà pris : soit un autre worker du même conteneur l'a eu, soit le
            # drapeau a été contourné. Dans les deux cas le serveur TOURNE, donc on ne
            # se plaint qu'une fois et on considère l'objectif atteint.
            _SERVER_STARTED = True
            logger.warning("port de métriques %d déjà lié (%s) — on suppose qu'un "
                           "serveur y répond déjà", METRICS_PORT, type(exc).__name__)
            return True
        except Exception as exc:  # noqa: BLE001 — jamais au prix du produit
            logger.warning("serveur de métriques non démarré (%s)", type(exc).__name__)
            return False


@contextmanager
def timed_rerun(page: str, phase: str = "view"):
    """Chronomètre une phase de rendu. Ne lève jamais, même si la métrique échoue.

    `phase` vaut `chrome` (auth, navigation, barre latérale) ou `view`. La séparation
    est le fond du sujet : le chronomètre historique ne mesurait que `view`, et la
    chrome coûte ~8× plus.
    """
    if _M is None:
        yield
        return
    start = time.perf_counter()
    try:
        _M["in_flight"].inc()
    except Exception:  # noqa: BLE001
        pass
    try:
        yield
    finally:
        try:
            _M["rerun"].labels(page=page or "?", phase=phase).observe(
                time.perf_counter() - start)
            _M["in_flight"].dec()
        except Exception:  # noqa: BLE001 — une mesure ratée n'est pas une panne
            pass


def observe_chrome(page: str, seconds: float) -> None:
    """Publie la durée de la phase CHROME d'un rendu. Ne lève jamais.

    Séparée de `timed_rerun` parce que la chrome n'est pas un bloc qu'on enveloppe :
    elle commence à la première ligne du script et s'arrête quand la vue démarre, avec
    des `st.stop()` possibles au milieu. Un gestionnaire de contexte ne survivrait pas
    à `StopException` ; un chronomètre posé en haut et lu en bas, si.
    """
    if _M is None:
        return
    try:
        _M["rerun"].labels(page=page or "?", phase="chrome").observe(max(0.0, seconds))
    except Exception:  # noqa: BLE001
        pass


def observe_pool(borrowed: int, available: int, direct_fallback: int = 0) -> None:
    """Publie l'état du pool. `direct_fallback` est le compteur qui manquait.

    Une saturation du pool retombe aujourd'hui sur une connexion DIRECTE avec un simple
    `logger.warning` : elle se dégrade en silence et rien ne la distingue du
    fonctionnement normal. Cette jauge est ce qui la rend visible.
    """
    if _M is None:
        return
    try:
        _M["pool"].labels(state="borrowed").set(borrowed)
        _M["pool"].labels(state="available").set(available)
        _M["pool"].labels(state="direct_fallback").set(direct_fallback)
    except Exception:  # noqa: BLE001
        pass


def count_error(page: str, error_class: str) -> None:
    """Compte une erreur applicative. Ne lève jamais."""
    if _M is None:
        return
    try:
        _M["errors"].labels(page=page or "?", error_class=error_class or "?").inc()
    except Exception:  # noqa: BLE001
        pass


def metrics_payload() -> tuple[bytes, str]:
    """Le corps et le type de contenu de `/metrics`, pour la route FastAPI."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return generate_latest(), CONTENT_TYPE_LATEST

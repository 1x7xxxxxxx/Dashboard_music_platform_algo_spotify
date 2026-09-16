"""Client-IP resolution and sliding-window throttling, shared by the API and the dashboard.

Type: Utility
Uses: src.database.postgres_handler (IMPORTÉ TARDIVEMENT, dans PostgresHitStore._handler
      seulement — l'import de ce module doit rester stdlib pur, il est chargé par un
      middleware FastAPI comme par une vue Streamlit, et ne doit jamais dépendre d'une
      base joignable)
Triggers: every rate-limited request on either surface
Persists in: rate_limit_hits (seaux d'authentification) ; rien pour les seaux en mémoire

Why this module exists — 2026-08-22.

Both halves of this logic already existed, in `src/api/security.py`, and both were
reachable only from FastAPI: `client_ip()` took a `starlette.Request`, and the limiter
was instantiated at API import time. The dashboard therefore had no throttle at all
beyond a `st.session_state` counter, which a new browser tab resets (R26), and the
public registration page had none whatsoever (R23).

Copying the header logic into the dashboard would have created a second X-Forwarded-For
parser. That is the failure this file prevents: the API's parser was wrong until
2026-08-22 (it read hop 0, the one the *client* controls, making the limiter a no-op),
and a copy made before the fix would still be wrong today with nothing to point at it.
One parser, two callers, one test suite.

Où vivent les compteurs — révisé le 2026-09-16.

Ils ont été per-process jusqu'ici, et cette phrase n'était exacte que parce qu'il y
avait une instance par surface. Les seaux d'AUTHENTIFICATION (register, totp, login,
`/auth/token`) vivent désormais dans Postgres, table `rate_limit_hits` : leur budget
est une garantie de sécurité, et une garantie de sécurité ne peut pas dépendre du
nombre de conteneurs. Les autres restent en mémoire, avec leur plafond `× N` écrit
là où ils sont construits.

Le choix de Postgres plutôt que Redis est détaillé plus bas, au-dessus de `HitStore`.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import OrderedDict, deque
from typing import Callable, Optional

# Number of proxies in front of us whose X-Forwarded-For entries we trust.
# Production is Cloudflare → Caddy → app, so the last TWO hops are ours.
TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "2"))

_logger = logging.getLogger(__name__)

_MAX_TRACKED_CLIENTS = 10_000  # memory bound — full reset beyond this


def client_ip_from_headers(
    get_header: Callable[[str], Optional[str]],
    peer: Optional[str] = None,
) -> str:
    """Client IP, taken from the RIGHT of X-Forwarded-For — never the left.

    `get_header` is a case-insensitive single-header lookup returning None when absent
    (`request.headers.get` on starlette, `st.context.headers.get` on Streamlit — both
    already fold case). `peer` is the socket peer when the caller can see one.

    The first hop is whatever the CLIENT sent. Cloudflare and Caddy both APPEND the peer
    they saw, so an attacker-supplied entry survives to the app at position 0. Reading it
    made the API rate limiter a no-op: `X-Forwarded-For: 10.0.0.<n>` with an incrementing
    n created a fresh bucket per request. Measured 2026-08-22.

    Cloudflare's `CF-Connecting-IP` is preferred when present: Cloudflare sets it itself
    and overwrites any client-supplied value.
    """
    cf = get_header("cf-connecting-ip")
    if cf:
        return cf.strip()
    forwarded = get_header("x-forwarded-for")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        # FEWER hops than we expect means the header did not come through our proxies —
        # so it is not ours to read. Falling back to the socket peer is the only safe
        # answer; taking hops[0] there would restore the bypass in every environment
        # that has one proxy instead of two.
        if len(hops) >= TRUSTED_PROXY_HOPS > 0:
            return hops[len(hops) - TRUSTED_PROXY_HOPS]
    return peer or "unknown"



# ─────────────────────────────────────────────────────────────────────────────
# Le MAGASIN des coups — l'abstraction posée le 2026-09-16
# ─────────────────────────────────────────────────────────────────────────────
#
# Jusqu'ici la fenêtre glissante ÉTAIT un `dict` de `deque`, et la phrase du haut
# de ce module (« per process is per surface ») était exacte parce qu'il y avait
# une instance par surface. Une seconde réplique la rend fausse sans qu'une ligne
# de limiteur ne change : le budget devient `budget × N` sur un chemin
# d'authentification, en silence.
#
# La sortie choisie est **Postgres, pas Redis**. Le précédent existe déjà ici :
# `saas_users.failed_login_attempts` / `locked_until` partagent DÉJÀ le
# verrouillage par compte entre l'API et le dashboard, par la base. Ajouter Redis
# pour la même classe de donnée serait une seconde dépendance à exploiter,
# sauvegarder, sécuriser et un jour retirer — « code is a liability, not an
# asset » (SE@Google p.356). Le volume le permet : ce sont des tentatives
# d'AUTHENTIFICATION, pas des rendus.
#
# Le magasin est une interface à trois opérations parce que la seule qui doit
# être ATOMIQUE est `hit()` : compter puis insérer en deux allers-retours est un
# check-then-act, et en READ COMMITTED deux transactions concurrentes passent
# toutes les deux. Ce serait le même défaut « budget × N » déplacé du processus
# vers la transaction. `hit()` est donc UNE opération du magasin, et c'est
# l'implémentation qui choisit comment la rendre indivisible.
#
# Les trois méthodes rendent l'HORODATAGE le plus ancien de la fenêtre (ou None
# quand il reste du budget) plutôt qu'un « retry-after » : l'arithmétique du
# délai reste dans le limiteur, en un seul endroit, quel que soit le magasin.


class HitStore:
    """Interface d'un magasin de coups pour `SlidingWindowLimiter`.

    `is_shared` dit si deux processus qui l'utilisent voient le MÊME compteur.
    C'est ce booléen que `tests/test_in_memory_limits_forbid_replicas.py` lit :
    il interroge le magasin réellement branché, jamais le nom d'une variable.
    """

    is_shared: bool = False

    def hit(self, key: str, now: float, window_secs: int,
            max_requests: int) -> Optional[float]:
        """Consomme une unité si le budget le permet. ATOMIQUE.

        Rend None si le coup est accepté, sinon l'horodatage du plus ancien coup
        encore dans la fenêtre (ce qui donne au limiteur de quoi calculer le
        délai d'attente).
        """
        raise NotImplementedError

    def peek(self, key: str, now: float, window_secs: int,
             max_requests: int) -> Optional[float]:
        """Comme `hit()` mais SANS consommer. N'a pas besoin d'être atomique."""
        raise NotImplementedError

    def reset(self, key: str) -> None:
        """Oublie l'historique de `key`."""
        raise NotImplementedError


class InMemoryHitStore(HitStore):
    """Compteurs en mémoire de processus — le comportement d'origine.

    Reste le bon choix pour un seau dont le budget n'est pas une garantie de
    sécurité (voir `_GLOBAL_LIMITER` dans `src/api/security.py`), et sert de mode
    dégradé borné au magasin Postgres.
    """

    is_shared = False

    def __init__(self) -> None:
        # ORDONNÉ par dernière écriture : la borne mémoire évince les clés les plus
        # anciennes, elle ne remet pas tout le monde à zéro.
        #
        # Le `self._hits.clear()` d'avant le 2026-09-16 était un défaut de sécurité et
        # pas seulement une grossièreté : atteindre 10 000 clés distinctes est à la
        # portée de qui dispose d'un /64 IPv6, et cela EFFAÇAIT le budget de tous les
        # autres clients d'un coup — y compris celui de l'attaquant. Le seau ne
        # dégradait donc pas vers « budget × N », il dégradait vers « aucun budget ».
        self._hits: "OrderedDict[str, deque]" = OrderedDict()

    def _evict_if_needed(self) -> None:
        while len(self._hits) > _MAX_TRACKED_CLIENTS:
            self._hits.popitem(last=False)

    def _window(self, key: str, now: float, window_secs: int) -> deque:
        window = self._hits.setdefault(key, deque())
        cutoff = now - window_secs
        while window and window[0] <= cutoff:
            window.popleft()
        return window

    def hit(self, key, now, window_secs, max_requests):
        window = self._window(key, now, window_secs)
        if window and len(window) >= max_requests:
            return window[0]
        window.append(now)
        self._hits.move_to_end(key)
        self._evict_if_needed()
        return None

    def peek(self, key, now, window_secs, max_requests):
        if key not in self._hits:
            return None
        window = self._window(key, now, window_secs)
        if window and len(window) >= max_requests:
            return window[0]
        return None

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)

    def clear(self) -> None:
        """Oublie TOUS les clients — usage de test uniquement."""
        self._hits.clear()


# Espace de noms des verrous consultatifs. `pg_advisory_xact_lock(int4, int4)`
# prend deux entiers : le premier isole CE mécanisme de tout autre verrou
# consultatif que le produit prendrait un jour, le second est le hachage de la
# clé. Sans le premier, deux verrous sans rapport pourraient se sérialiser l'un
# l'autre par collision de hachage.
_ADVISORY_LOCK_CLASS = 0x7A7B  # arbitraire et stable — "throttle"

# Longueur maximale d'une clé écrite en base. Au-delà, on écrit un HACHAGE.
#
# La clé descend d'un en-tête HTTP (`CF-Connecting-IP`, `X-Forwarded-For`) que le
# client contrôle en partie. Une IP légitime tient en 45 caractères ; les préfixes de
# seau du produit ajoutent une vingtaine. 200 laisse une marge large et ferme deux
# choses : une ligne de base arbitrairement grosse, et surtout l'INSERT qui échouerait
# au-delà de la limite de taille d'une entrée d'index btree (~2704 octets) — une
# exception, donc un repli silencieux en mémoire, donc le budget × N retrouvé **en
# envoyant un en-tête long**. La borne rend ce levier inutilisable.
#
# Le hachage garde des clés DISTINCTES distinctes (un tronquage ne le ferait pas : deux
# en-têtes partageant leurs 200 premiers caractères partageraient un budget).
_MAX_KEY_LEN = 200


def _bounded(key: str) -> str:
    """La clé telle qu'elle est écrite en base — bornée en longueur."""
    if len(key) <= _MAX_KEY_LEN:
        return key
    return "sha256:" + hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()

# Le nom de table est ÉCRIT dans chaque requête, jamais interpolé — même depuis une
# constante de module. `tests/test_a_sql_identifier_comes_from_a_closed_set.py` tient un
# cliquet à ZÉRO sur ce dépôt, et il a raison de ne pas faire d'exception pour « c'est
# une constante » : la constante d'aujourd'hui est le paramètre de demain, et la revue
# qui laisse passer la première n'a plus d'argument contre la seconde.


class PostgresHitStore(HitStore):
    """Compteurs partagés par toutes les instances, tenus dans `rate_limit_hits`.

    L'atomicité vient d'un **verrou consultatif de transaction** pris sur la clé :
    `pg_advisory_xact_lock(classe, hashtext(clé))`. Deux tentatives sur la même
    clé se sérialisent ; deux clés différentes ne se voient pas. C'est une
    contention BORNÉE par client, ce qui est exactement ce qu'un limiteur doit
    supporter — là où `SERIALIZABLE` + reprise sur `40001` se dégrade sous la
    rafale même qu'il doit absorber.

    MODE DÉGRADÉ — explicite, et c'est un choix, pas un oubli. Une exception
    Postgres non traitée dans `hit()` rendrait 500 sur TOUTE authentification
    pendant le moindre hoquet de base : la panne de la base deviendrait une panne
    de connexion. On retombe donc sur un magasin en mémoire (`fail-open` **borné**,
    pas ouvert) : pendant l'incident le budget vaut `budget × N` au pire, ce qui
    est la situation d'avant ce changement, jamais « aucune limite ». Le repli est
    journalisé une fois par fenêtre pour ne pas noyer les logs.
    """

    is_shared = True

    # Fenêtre de silence entre deux journalisations du repli, en secondes.
    _OUTAGE_LOG_EVERY = 60.0

    def __init__(self) -> None:
        self._fallback = InMemoryHitStore()
        self._last_outage_log = 0.0

    # ── plomberie ────────────────────────────────────────────────────────────

    def _handler(self):
        """Un handler Postgres, emprunté au pool quand l'appelant en a un.

        `from_env_or_config()` est la porte unique du dépôt
        (`tests/test_one_door_onto_the_database.py`).

        Le coût dépend du POOL, et il ne se suppose pas : une version de ce
        commentaire a affirmé le 2026-09-16 que « le dashboard et l'API appellent
        tous deux `enable_pool()` ». C'était faux — `grep -rn "enable_pool(" src/`
        ne rendait que `src/dashboard/utils/__init__.py`. Sur l'API, chaque
        tentative d'authentification ouvrait donc une connexion DIRECTE, poignée
        de main SCRAM comprise, et consommait un créneau de `max_connections` par
        requête non authentifiée. `src/api/main.py` l'active désormais aussi.
        """
        from src.database.postgres_handler import PostgresHandler

        return PostgresHandler.from_env_or_config()

    def _note_outage(self, exc: BaseException) -> None:
        now = time.time()
        if now - self._last_outage_log >= self._OUTAGE_LOG_EVERY:
            self._last_outage_log = now
            _logger.error(
                "magasin de limitation indisponible (%s) — repli EN MÉMOIRE : "
                "le budget vaut budget × nombre d'instances jusqu'au rétablissement",
                type(exc).__name__,
            )

    # ── opérations ───────────────────────────────────────────────────────────

    def hit(self, key, now, window_secs, max_requests):
        try:
            return self._hit_in_db(key, now, window_secs, max_requests)
        except Exception as exc:  # noqa: BLE001 — le mode dégradé EST le contrat
            self._note_outage(exc)
            return self._fallback.hit(key, now, window_secs, max_requests)

    def _hit_in_db(self, key, now, window_secs, max_requests):
        """Les quatre instructions, sur UNE connexion, dans UNE transaction.

        On pilote la connexion directement au lieu de passer par
        `execute_query` / `fetch_query`, et ce n'est pas une préférence de style :
        ces deux méthodes appellent `_ensure_connection()`, qui REMPLACE
        `self.conn` sur une `OperationalError`. Au milieu de cette transaction,
        une reconnexion relâcherait le verrou consultatif (il est de portée
        TRANSACTION), puis exécuterait la suite en autocommit sur une connexion
        neuve — et committerait l'INSERT quand même. L'atomicité annoncée
        disparaîtrait sans une ligne de journal. Ici, une connexion coupée lève,
        et une levée est le mode dégradé, pas un faux succès.
        """
        key = _bounded(key)
        db = self._handler()
        try:
            conn = getattr(db, "conn", None)
            if conn is None:
                raise RuntimeError("handler sans connexion — pas de transaction possible")
            previous = conn.autocommit
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    # Le verrou se relâche au commit COMME au rollback : un plantage
                    # ici ne laisse pas une clé verrouillée derrière lui.
                    cur.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
                                (_ADVISORY_LOCK_CLASS, key))
                    cur.execute(
                        "DELETE FROM rate_limit_hits WHERE bucket = %s AND ts <= %s",
                        (key, now - window_secs))
                    cur.execute(
                        "SELECT count(*), min(ts) FROM rate_limit_hits WHERE bucket = %s",
                        (key,))
                    count, oldest = cur.fetchone()
                    if count >= max_requests and oldest is not None:
                        conn.commit()
                        return float(oldest)
                    cur.execute(
                        "INSERT INTO rate_limit_hits (bucket, ts) VALUES (%s, %s)",
                        (key, now))
                conn.commit()
                return None
            except Exception:
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001 — une connexion morte ne se rollback pas
                    pass
                raise
            finally:
                try:
                    conn.autocommit = previous
                except Exception:  # noqa: BLE001 — ne pas masquer l'erreur d'origine
                    pass
        finally:
            db.close()

    def peek(self, key, now, window_secs, max_requests):
        db_key = _bounded(key)
        try:
            db = self._handler()
            try:
                rows = db.fetch_query(
                    "SELECT count(*), min(ts) FROM rate_limit_hits "
                    "WHERE bucket = %s AND ts > %s",
                    (db_key, now - window_secs),
                )
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            self._note_outage(exc)
            return self._fallback.peek(key, now, window_secs, max_requests)
        count, oldest = (rows[0] if rows else (0, None))
        if count >= max_requests:
            return float(oldest)
        return None

    def reset(self, key: str) -> None:
        self._fallback.reset(key)
        try:
            db = self._handler()
            try:
                db.execute_query(
                    "DELETE FROM rate_limit_hits WHERE bucket = %s", (_bounded(key),))
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001 — un oubli raté n'est pas une panne
            self._note_outage(exc)


# Le magasin partagé est construit UNE fois par processus et n'ouvre aucune
# connexion à l'import : `_handler()` est appelé au premier coup, pas ici. Ce
# module doit rester importable depuis un middleware FastAPI comme depuis une vue
# Streamlit, et l'import ne doit jamais dépendre d'une base joignable.
_SHARED_STORE: Optional[HitStore] = None

# `memory` est la sortie de secours EXPLICITE (un développeur hors base, un
# incident). Elle se lit dans les journaux au démarrage, elle ne se devine pas.
_STORE_BACKEND = os.getenv("RATE_LIMIT_STORE", "postgres").strip().lower()


def shared_hit_store() -> HitStore:
    """Le magasin partagé du processus — Postgres par défaut."""
    global _SHARED_STORE
    if _SHARED_STORE is None:
        if _STORE_BACKEND == "memory":
            _logger.warning(
                "RATE_LIMIT_STORE=memory — les compteurs anti-force-brute ne sont "
                "PAS partagés entre instances"
            )
            _SHARED_STORE = InMemoryHitStore()
        else:
            _SHARED_STORE = PostgresHitStore()
    return _SHARED_STORE

class SlidingWindowLimiter:
    """Per-key sliding-window counter. Returns a Retry-After when over budget.

    Le comptage vit dans un `HitStore`, pas dans cet objet. `store=None` donne le
    comportement historique (un `dict` par processus) ; `store=shared_hit_store()`
    donne un compteur que toutes les instances partagent. Un seau dont le budget
    est une garantie de SÉCURITÉ doit prendre le second — voir le module.

    L'arithmétique du délai d'attente reste ici, en un seul endroit : le magasin
    rend l'horodatage du plus ancien coup de la fenêtre, jamais un nombre de
    secondes.
    """

    def __init__(self, max_requests: int, window_secs: int,
                 store: Optional[HitStore] = None):
        # Un budget nul ou négatif est une erreur de configuration
        # (`DASHBOARD_LOGIN_MAX=0`), pas une intention. Le laisser passer faisait
        # planter la page d'AUTHENTIFICATION au lieu de refuser : `count >= 0` est vrai
        # alors qu'aucun horodatage n'existe, donc `float(None)` puis `window[0]` sur
        # une file vide. On refuse au démarrage, là où le message se lit.
        if max_requests < 1:
            raise ValueError(
                f"budget de limitation invalide ({max_requests}) — il faut au moins 1. "
                "Un budget nul ne refuse pas tout le monde, il fait planter la page."
            )
        self.max_requests = max_requests
        self.window_secs = window_secs
        self.store: HitStore = InMemoryHitStore() if store is None else store

    @property
    def is_shared(self) -> bool:
        """True quand deux processus voient le MÊME compteur.

        Lu par `tests/test_in_memory_limits_forbid_replicas.py`, qui interroge le
        limiteur réellement branché et non le nom d'une variable : un garde qui
        lit un nom reste vert sur un correctif correct et rouge sur un renommage.
        """
        return bool(self.store.is_shared)

    def _retry_after(self, oldest: float, now: float) -> int:
        return max(1, int(oldest + self.window_secs - now) + 1)

    def hit(self, key: str, now: Optional[float] = None) -> Optional[int]:
        """Record a request for `key`. None = allowed; int = seconds to wait."""
        now = time.time() if now is None else now
        oldest = self.store.hit(key, now, self.window_secs, self.max_requests)
        return None if oldest is None else self._retry_after(oldest, now)

    def peek(self, key: str, now: Optional[float] = None) -> Optional[int]:
        """Seconds to wait if `key` is over budget, without recording a hit.

        For call sites that must decide *before* doing work whether to proceed, and
        record the attempt only on the path that actually consumed something.
        """
        now = time.time() if now is None else now
        oldest = self.store.peek(key, now, self.window_secs, self.max_requests)
        return None if oldest is None else self._retry_after(oldest, now)

    def reset(self, key: str) -> None:
        """Forget `key`'s history — call after a *successful* authentication only."""
        self.store.reset(key)

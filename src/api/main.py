"""FastAPI REST backend — Brick 14.

Exposes the core platform data over a JWT-authenticated REST API.

Run locally (development):
    uvicorn src.api.main:app --reload --port 8502

OpenAPI docs (Swagger UI): http://localhost:8502/docs
ReDoc:                      http://localhost:8502/redoc

Authentication flow:
    1. POST /auth/token  with form fields username + password (same creds as Streamlit dashboard)
    2. Use the returned ``access_token`` as a Bearer token on all other endpoints.

Environment variables:
    API_SECRET_KEY   — JWT signing secret (override in production, min 32 chars)
    DATABASE_URL     — optional postgres:// URL; falls back to config/config.yaml
"""
import os
import sys
import threading
import time
from pathlib import Path

# Ensure project root is on sys.path so src.* imports resolve
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from src.api.routers import auth, artists, streams, youtube, ml, kpis, stripe_webhook  # noqa: E402
from src.api.security import install as install_security  # noqa: E402

def _preflight() -> None:
    """Fail loud in prod on weak/absent security-critical config — instead of silently
    degrading (API_SECRET_KEY falls back to an EPHEMERAL key in auth.py, so JWTs die on
    every restart / differ per worker). Warns by default so dev/test keep working; raises
    only under API_STRICT_BOOT=1 (set in the prod compose). Mirrors the dashboard's
    boot-time FERNET/AIRFLOW checks."""
    import logging
    problems = []
    if len(os.getenv("API_SECRET_KEY", "")) < 32:
        problems.append("API_SECRET_KEY missing or <32 chars — JWTs won't survive a "
                        "restart / multi-worker (set `openssl rand -hex 32`)")
    if not os.getenv("DATABASE_URL"):
        problems.append("DATABASE_URL not set")
    if not problems:
        return
    msg = "API startup preflight: " + "; ".join(problems)
    if os.getenv("API_STRICT_BOOT"):
        raise RuntimeError(msg + " — refusing to start (API_STRICT_BOOT=1).")
    logging.getLogger("api.preflight").warning(
        "⚠️ %s — set API_STRICT_BOOT=1 in prod to make this fatal.", msg)


_preflight()

# OpenAPI docs (/docs, /redoc) hand attackers the full API surface map — disabled by
# default on a public deploy. Set API_ENABLE_DOCS=1 to re-enable (local dev).
_docs_enabled = os.getenv("API_ENABLE_DOCS") == "1"

app = FastAPI(
    title="Music Platform API",
    description=(
        "REST API for the music analytics SaaS platform.\n\n"
        "All endpoints (except `/auth/token` and `/health`) require a Bearer JWT obtained via `POST /auth/token`."
    ),
    version="1.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    # Gate the raw schema too: with docs/redoc off but openapi_url at its default,
    # /openapi.json still served the full API map (endpoints + schemas) to anyone —
    # pentest 2026-06-13 finding. None → /openapi.json returns 404 in prod.
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Un POOL de connexions, comme le dashboard en a un depuis le 2026-09-11 — posé ici le
# 2026-09-16, et pas par symétrie.
#
# Le seau de `/auth/token` compte désormais dans Postgres, donc CHAQUE tentative
# d'authentification, y compris celles qui seront refusées, ouvre une connexion. Sans
# pool, c'est une poignée de main SCRAM (~8,5 ms, mesurée en production) et un créneau
# de `max_connections` consommé par requête NON AUTHENTIFIÉE — soit un levier offert
# pour épuiser la base, donc pour provoquer le mode dégradé du limiteur et retrouver le
# budget × N. Un commentaire de `request_throttle.py` a affirmé une journée que l'API
# appelait déjà `enable_pool()` ; `grep -rn "enable_pool(" src/` ne rendait que le
# dashboard.
#
# `enable_pool()` ne se connecte à rien : il enregistre les bornes, le pool est
# construit à la première connexion. L'import de ce module reste donc sans effet de
# bord réseau.
from src.database.postgres_handler import enable_pool  # noqa: E402

enable_pool(minconn=1, maxconn=8)

# ⚠️ `enable_pool()` REGISTRE les bornes ; rien ne PUBLIE l'état du pool tant que
# personne n'appelle `publish_pool_metrics()`. Côté dashboard c'est `end_chrome()` qui
# s'en charge à chaque rerun ; côté API, personne ne le faisait — mesuré le 2026-09-17 :
# les quatre familles étaient déclarées dans le registre de l'API et AUCUNE n'était
# alimentée, donc `streamlytics_postgres_pool_connections` ne décrivait que le
# dashboard alors que les deux processus se partagent `max_connections`.
#
# On le publie à la scrutation plutôt qu'à chaque requête : l'état du pool est une
# grandeur instantanée, la lire 15 s trop tard ne coûte rien, et le faire sur le chemin
# de chaque requête paierait deux lectures d'attributs par appel pour rien.
from src.utils.http_metrics import install_http_metrics  # noqa: E402
from src.utils.log_metrics import install_log_counter  # noqa: E402

install_http_metrics(app)
install_log_counter()

# `/metrics` — ADR-026. Pas de serveur lateral ici, contrairement au dashboard :
# l'API a deja un serveur HTTP, lui en ajouter un second n'acheterait rien.
#
# La route est EXEMPTEE du limiteur global ci-dessous par `_EXEMPT_PATHS` : Prometheus
# scrute toutes les 15 s depuis le reseau Docker, et le faire compter dans un budget
# anti-abus ferait 429 le collecteur au bout de quelques minutes — la metrique
# disparaitrait exactement quand la charge monte, c'est-a-dire quand on la lit.
@app.get("/metrics", include_in_schema=False)
def metrics():
    from fastapi.responses import Response

    from src.database.postgres_handler import publish_pool_metrics
    from src.utils.metrics import metrics_payload

    # Publier JUSTE AVANT de rendre la charge utile : c'est le seul instant où l'état du
    # pool de CE processus a un sens pour le scrutateur.
    try:
        publish_pool_metrics()
    except Exception:  # noqa: BLE001 — une métrique ne casse jamais /metrics
        pass

    body, content_type = metrics_payload()
    return Response(content=body, media_type=content_type)


# C3 hardening: sliding-window rate limit + security response headers
install_security(app)

# CORS origins from env (comma-separated) so the real HTTPS origin is allowlisted in
# production; falls back to localhost for dev. Never use "*" with allow_credentials.
_cors_origins = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:8501,http://localhost:3000"
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(artists.router)
app.include_router(streams.router)
app.include_router(youtube.router)
app.include_router(ml.router)
app.include_router(kpis.router)
app.include_router(stripe_webhook.router)


# ── `/health` VÉRIFIE quelque chose — 2026-09-20 (R140 §16.14) ───────────────
#
# Il rendait `{"status": "ok"}` sans aucun contrôle, et DEUX surfaces en font un verdict
# FINAL : `railway.toml:24` (`healthcheckPath`, `healthcheckTimeout = 30`) et
# `Dockerfile.api:54` (`HEALTHCHECK`, `--retries=3 --interval=30s`). Un conteneur dont la
# base est injoignable était donc déclaré sain — et continuait de recevoir du trafic.
#
# ⚠️ **DEUX surfaces, pas trois.** Le premier jet de ce commentaire comptait aussi
# `docker-compose.yml:171` ; c'est le healthcheck d'**airflow-webserver**, visant le
# `/health` d'Airflow sur son propre port 8080. Aucun service FastAPI n'est défini dans
# ce fichier. Le décompte importe : c'est lui qui donne la cadence de sondage et donc le
# modèle de charge de cet endpoint.
#
# ⚠️ **ET LE PREMIER JET RENDAIT 503 SUR UNE BASE SAINE.** Il posait le délai par
# `db.fetch_query("SET LOCAL statement_timeout = 2000")` — or `fetch_query` appelle
# `fetchall()` après l'exécution, et un `SET` ne renvoie aucun jeu de résultats :
# `ProgrammingError`, attrapé par le `except`, donc `degraded` en permanence. Railway
# n'aurait jamais validé un déploiement et Docker aurait marqué le conteneur `unhealthy`
# en 90 s. **Cinq tests étaient verts pendant ce temps** : les trois premiers simulaient
# `_base_repond` lui-même, et le faux double de la base acceptait n'importe quel SQL.
# Un test qui simule la fonction qu'il vérifie ne vérifie rien.
# `SET LOCAL` était de toute façon inopérant — `PostgresHandler` est en `autocommit`,
# donc hors bloc transactionnel : PostgreSQL rend `WARNING: SET LOCAL can only be used
# in transaction blocks` et le délai effectif restait celui de la connexion, 15 s.
#
# La sonde ouvre donc sa PROPRE connexion, avec son propre `statement_timeout` dans les
# `options` — le seul endroit où il s'applique vraiment.
_SANTE_TTL_S = 5.0
_SANTE_TIMEOUT_MS = 2000
_sante_verrou = threading.Lock()
_sante_etat: dict[str, object] = {"quand": 0.0, "verdict": None}


def _sonder_la_base() -> tuple[bool, str]:
    """Une connexion neuve, un `SELECT 1`, des bornes explicites. Ne lève jamais."""
    conn = None
    try:
        import psycopg2

        # ⚠️ **`from_env_or_config()`, PAS `resolve_kwargs()`** — et l'écart n'existe
        # QUE là où ça compte. Mesuré en production le 2026-09-20, après déploiement :
        # `/health` rendait `503 {"reason":"database"}` sur une API qui servait
        # normalement (`/auth/token` → 401 correct, `/metrics` → 200).
        #
        # `resolve_kwargs()` ne lit PAS `DATABASE_URL` ; `from_env_or_config()` le lit
        # EN PREMIER puis retombe sur lui. Or les conteneurs `api` et `dashboard`
        # reçoivent `DATABASE_URL` et **aucun** `DATABASE_HOST`, et n'ont pas de
        # `config/config.yaml`. La sonde levait donc `RuntimeError: No database
        # configuration`, attrapée, et rendait « base injoignable » sur une base
        # parfaitement joignable.
        #
        # Le correctif de `security-specialist` disait `from_env_or_config()` ; j'ai
        # substitué `resolve_kwargs()` pour pouvoir passer mes propres bornes. On prend
        # donc la RÉSOLUTION du premier et les BORNES de la seconde : le handler porte
        # ses paramètres, on s'en sert pour ouvrir une connexion bornée.
        #
        # Ce défaut ne pouvait pas se voir ici : en local `config/config.yaml` existe,
        # donc `resolve_kwargs()` réussit. C'est la deuxième fois ce soir que ce
        # `/health` échoue faute d'avoir exercé le chemin RÉEL dans l'environnement réel.
        from src.database.postgres_handler import PostgresHandler
        h = PostgresHandler.from_env_or_config()
        conn = psycopg2.connect(
            connect_timeout=2,
            options=f"-c statement_timeout={_SANTE_TIMEOUT_MS}",
            host=h.host, port=h.port, database=h.database,
            user=h.user, password=h.password)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return (True, "ok")
    except Exception as exc:                  # noqa: BLE001 — une sonde ne lève jamais
        # La CLASSE part au journal, jamais dans la réponse : cet endpoint est public.
        import logging
        logging.getLogger("streamlytics.api").warning(
            "sonde /health en échec : %s", type(exc).__name__)
        return (False, "database")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:                 # noqa: BLE001 — fermeture best-effort
                pass


def _base_repond() -> tuple[bool, str]:
    """Le verdict de la sonde, mis en cache et SÉRIALISÉ.

    ⚠️ **Le verrou n'est pas une précaution, il est la borne de charge.** Sans lui, la
    lecture du cache et son écriture encadrent la sonde : N requêtes simultanées à cache
    froid passent toutes le test avant que la première n'écrive. Mesuré — 20 sondes
    simultanées ouvraient **20 connexions**. Et `_borrow_from_pool()` retombe sur un
    `psycopg2.connect()` direct quand le pool est épuisé, donc `maxconn` ne borne rien :
    une rafale anonyme sur un endpoint public et non limité consommait autant de créneaux
    de `max_connections` que le pool de threads d'uvicorn en autorise.

    ⚠️ **L'horodatage est posé APRÈS la sonde.** Le premier jet le lisait avant : si la
    sonde dure plus longtemps que le TTL, l'entrée est périmée à l'instant où elle est
    écrite, et le cache ne protège jamais dans le seul régime qui le justifie — une base
    lente. Mesuré : sonde de 10,4 s, TTL 5 s, trois connexions pour trois sondes.

    ⚠️ **Le verdict et son instant sont un SEUL tuple.** En deux affectations avec
    l'instant écrit en premier, un lecteur concurrent peut voir un instant FRAIS avec un
    verdict PÉRIMÉ — et servir `200 ok` pendant un TTL entier alors que la base vient de
    tomber. Les écritures de dict sont atomiques sous le GIL ; le défaut est l'ordre.
    """
    etat = _sante_etat.get("verdict")
    quand = float(_sante_etat.get("quand") or 0.0)
    if etat is not None and time.monotonic() - quand < _SANTE_TTL_S:
        return etat                                      # type: ignore[return-value]

    with _sante_verrou:
        # Relire APRÈS le verrou : les retardataires d'une rafale profitent de la sonde
        # que le premier vient de faire, au lieu d'en lancer une chacun.
        etat = _sante_etat.get("verdict")
        quand = float(_sante_etat.get("quand") or 0.0)
        if etat is not None and time.monotonic() - quand < _SANTE_TTL_S:
            return etat                                  # type: ignore[return-value]
        verdict = _sonder_la_base()
        _sante_etat["verdict"] = verdict                 # la valeur AVANT son instant
        _sante_etat["quand"] = time.monotonic()          # posé APRÈS la sonde
        return verdict


@app.get("/health", tags=["meta"], summary="Health check")
def health(response: Response):
    """Le service répond ET sa base répond. Sans authentification.

    Rend `200 {"status": "ok"}` quand Postgres accepte un `SELECT 1`, et
    `503 {"status": "degraded", "reason": "database"}` sinon — le code HTTP est ce que
    lisent le `HEALTHCHECK` Docker et Railway.

    ⚠️ `reason` est un VOCABULAIRE FERMÉ, pas la classe de l'exception. Distinguer
    `OperationalError` de `AdminShutdown` ou de `TooManyConnections` donnerait à un
    appelant anonyme un oracle sur l'état interne de la base. La classe part au journal.
    """
    ok, motif = _base_repond()
    if ok:
        return {"status": "ok"}
    response.status_code = 503
    return {"status": "degraded", "reason": motif}

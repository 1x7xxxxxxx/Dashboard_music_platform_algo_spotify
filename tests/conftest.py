"""Fixtures partagées pour tous les tests."""
import io
import sys
import os
import pytest
import pandas as pd

# Rendre src/ importable sans installation du package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers CSV en mémoire (pas de fichiers temporaires nécessaires)
# ---------------------------------------------------------------------------

def make_csv_bytes(content: str, encoding: str = "utf-8") -> bytes:
    return content.encode(encoding)


def make_tmp_csv(tmp_path, filename: str, content: str, encoding: str = "utf-8"):
    """Crée un fichier CSV temporaire et retourne son Path."""
    p = tmp_path / filename
    p.write_bytes(content.encode(encoding))
    return p


@pytest.fixture
def tmp_csv(tmp_path):
    """Factory fixture : make_tmp_csv(filename, content)."""
    def _factory(filename: str, content: str, encoding: str = "utf-8"):
        return make_tmp_csv(tmp_path, filename, content, encoding)
    return _factory


# ---------------------------------------------------------------------------
# The silence that let four waves of tenant-isolation work ship unverified
# ---------------------------------------------------------------------------
#
# ~160 tests carry `pytestmark = requires_live_db()`. Without Postgres on 5433
# they skip, pytest prints "N passed, 163 skipped", and the run reads as green.
#
# Measured 2026-08-22: four waves of credential and tenant-isolation fixes were
# written, guarded and COMMITTED against that green. Starting the database turned
# "1065 passed" into "1217 passed, 1 FAILED" — and the failure was in the Instagram
# uniqueness protection that had just been presented as closed.
#
# The suite is not required to have a database. It IS required to say, loudly, that
# the guards which need one did not run — because "163 skipped" scrolls past and
# "green" does not.

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Une dépendance absente ne doit pas se lire comme une couverture complète.

    Ajouté le 2026-08-26, en transformant 32 rouges d'environnement en skips. Le
    danger du geste est connu ici : c'est exactement la mécanique du bloc Postgres
    ci-dessous — « 163 skipped » défile et « vert » ne défile pas. Un skip qu'on ne
    crie pas est pire que le rouge qu'il remplace, parce qu'il se confond avec une
    suite qui a tout prouvé.
    """
    from tests.dep_gate import GATED, missing

    absent = missing()
    if absent:
        tw = terminalreporter
        tw.write_sep("=", "DÉPENDANCES ABSENTES — GARDES NON EXÉCUTÉS", red=True, bold=True)
        tw.write_line(
            f"{len(absent)} dépendance(s) manquent à CET interpréteur : "
            f"{', '.join(absent)}."
        )
        tw.write_line(
            "Les DAGs, les collecteurs et le parcours deux-locataires n'ont donc RIEN "
            "prouvé dans cette exécution."
        )
        for name in absent:
            tw.write_line(f"    {name} → {GATED[name][1]}")
        tw.write_line(f"    (interpréteur utilisé : {__import__('sys').executable})")


def _pytest_terminal_summary_db(terminalreporter, exitstatus, config):
    from tests.db_gate import DB_HOST, DB_PORT, db_ready

    if db_ready():
        return
    skipped = terminalreporter.stats.get("skipped", [])
    gated = sum(1 for r in skipped
                if "needs the live schema" in " ".join(str(x) for x in r.longrepr or ()))
    if not gated:
        return
    tw = terminalreporter
    tw.write_sep("=", "GARDES NON EXÉCUTÉS", red=True, bold=True)
    tw.write_line(
        f"{gated} test(s) exigeant une base ont été SAUTÉS — dont l'isolation "
        f"locataire, l'unicité d'identité et le parcours d'onboarding."
    )
    tw.write_line(
        "Cette exécution ne prouve RIEN sur ces sujets. Pour les lancer :"
    )
    tw.write_line(
        f"    docker start postgres_spotify_airflow   # puis relancer  "
        f"(attendu sur {DB_HOST}:{DB_PORT})"
    )


# ---------------------------------------------------------------------------
# The suite sent real email to real people
# ---------------------------------------------------------------------------
#
# Measured 2026-08-23. `test_admin_hypeddit_buttons.py::test_every_button_survives_a_click[admin]`
# presses every button on the admin view. One of them is `📧 Renvoyer vérification`
# (`admin.py:685`), which calls `send_verification_email(sel_user['email'], …)` — an
# address read from whatever database the run points at. Locally that is the migrated
# copy of production, so the recipient is a real beta tester, and `.env` holds real
# Gmail SMTP credentials. Three suite runs on 2026-08-23 delivered three verification
# emails, each carrying `http://localhost:8501?page=verify&token=…` because no local
# process sets APP_BASE_URL.
#
# Nothing prevented it: there was no network or SMTP boundary in this file at all.
#
# Why RECORD-then-fail rather than just raise: `send_verification_email` wraps its send
# in `except Exception`, so an exception alone is swallowed, the button reports a
# failure, and the test stays green — the send would be blocked but no one would ever
# learn the test attempts it. The attempt is recorded and asserted at teardown, where
# the application's error handling cannot reach it.
#
# A test that legitimately exercises the send path patches `smtplib.SMTP` itself; its
# patch lands after this one, so it is never recorded and never fails here.

# ── Frontière REGISTRE — un test ne salit pas le journal des défauts ──────────
#
# Mesuré le 2026-09-04, le jour où le registre a été construit : après une exécution de
# la suite, `app_error_log` portait `ValueError | unknown | ×8`, en environnement
# `local`, écrit par les tests de `error_alert` qui appellent `notify_app_error` pour
# de bon. Ces lignes ne décrivent aucun défaut — elles décrivent la suite — et elles
# arrivent dans la MÊME base que celle qu'on lit pour trier.
#
# Même famille que la frontière SMTP ci-dessous : la question n'est pas « le code
# est-il juste » mais « que fait la suite au monde extérieur ». Un test qui veut
# vraiment écrire dans le registre appelle `record_error` directement — c'est le cas
# de `test_an_error_leaves_a_row.py`, qui ne passe jamais par cette porte.

@pytest.fixture(autouse=True)
def _no_registry_writes(monkeypatch):
    """`notify_app_error` ne persiste rien pendant la suite."""
    try:
        from src.dashboard.utils import error_alert
    except Exception:      # noqa: BLE001 — dépendances absentes : rien à border
        yield
        return
    monkeypatch.setattr(error_alert, "_record", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(error_alert, "_mark_emailed", lambda *a, **k: None,
                        raising=False)
    yield


@pytest.fixture(autouse=True)
def _no_real_smtp(monkeypatch, request):
    """No test may open a real SMTP connection. Records attempts, fails at teardown."""
    import smtplib

    attempts: list[str] = []

    def _blocked(*args, **kwargs):
        host = kwargs.get("host", args[0] if args else "")
        port = kwargs.get("port", args[1] if len(args) > 1 else "")
        attempts.append(f"{host}:{port}")
        raise ConnectionRefusedError(
            "blocked by tests/conftest.py::_no_real_smtp — a test must not send email"
        )

    monkeypatch.setattr(smtplib, "SMTP", _blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _blocked)
    # Exposed so the meta-test that deliberately trips this boundary can consume its
    # own attempt. Nothing else should touch it.
    request.node._smtp_attempts = attempts

    yield

    assert not attempts, (
        f"{request.node.nodeid} opened a REAL SMTP connection to {', '.join(attempts)}.\n"
        f"The credentials come from .env and the recipient from the database the run "
        f"points at — locally, a copy of production, so this delivers mail to real "
        f"people with a link to http://localhost:8501.\n"
        f"Patch the send in the test — `monkeypatch.setattr(<module>, "
        f"'send_verification_email', lambda *a, **k: True)` — or mock `smtplib.SMTP` "
        f"yourself if the send path is what you mean to exercise."
    )


# ---------------------------------------------------------------------------
# The suite called the platforms' real APIs
# ---------------------------------------------------------------------------
#
# R41. Khorikov (*Unit Testing Principles*, p.213 et p.221) sépare les dépendances
# MANAGED — la base, qu'on ne mocke pas, et ce dépôt a raison de tourner sur un vrai
# Postgres — des dépendances UNMANAGED, hors process et observables de l'extérieur, qui
# « are part of your system's observable behavior. Such dependencies should be mocked
# out. » SMTP en fait partie, et a été borné plus haut le 2026-08-23. Les APIs des
# plateformes aussi, et rien ne les bornait.
#
# Mesuré le même jour avec un mouchard sur `socket.connect` pendant une exécution
# complète : `test_artist_preflight.py::test_a_scoped_run_still_requires_its_own_platform`
# ouvrait QUATRE connexions sortantes réelles — vers Meta (157.240.196.17), Google
# (35.186.224.24) et SoundCloud (3.164.85.105) — parce que `step_central_apps` sonde les
# quatre plateformes, y compris celles hors périmètre, avec les credentials de `.env`.
#
# Pourquoi ce défaut a vécu plus longtemps que son jumeau SMTP : un mail arrive dans une
# boîte et se voit. Un appel HTTP réel ne laisse aucune trace côté opérateur — il
# consomme du quota, peut écrire, et fait échouer la CI dès qu'il n'y a pas de réseau.
#
# La frontière est posée sur la SOCKET, pas sur `requests` : les collecteurs passent par
# `requests`, `googleapiclient` et `urllib` selon la plateforme, et patcher une seule des
# trois aurait laissé les autres sortir. Seuls les ports 80/443 sont refusés — Postgres
# (5433) doit continuer de passer, c'est une dépendance *managed*.

# L'ÉCHAPPATOIRE, et pourquoi elle doit exister.
#
# Une frontière `autouse` sans exception nommée ne borne pas le rayon de souffle : elle
# éteint aussi ce qui DOIT sortir. Mesuré le 2026-08-24 sur la CI de production —
# `tests/test_prod_health.py`, dont le rôle est de sonder l'application LIVE à travers
# Cloudflare, rendait **14 failed, 14 errors** chaque matin depuis que la frontière
# existe. La sonde synthétique externe, l'une des trois épaisseurs du filet de
# surveillance, était donc morte, et son rouge quotidien se lisait comme du bruit.
#
# La suite se gardait pourtant déjà elle-même (`RUN_PROD_HEALTH=1`, sinon elle skippe,
# « so a push never hammers prod ») : c'est la frontière qui l'écrasait au niveau
# SOCKET, sous son propre garde.
#
# La sortie est donc **nommée** (`@pytest.mark.real_http`), pas silencieuse, et
# `tests/test_the_http_escape_hatch_stays_narrow.py` échoue si un second fichier la
# prend. Une échappatoire qui se propage redevient l'absence de frontière.
_REAL_HTTP_MARK = "real_http"


@pytest.fixture(autouse=True)
def _no_real_http(monkeypatch, request):
    """No test may reach an external HTTP(S) endpoint. Records, fails at teardown."""
    import socket

    if request.node.get_closest_marker(_REAL_HTTP_MARK) is not None:
        # Sortie assumée : ce test EST un appel réseau réel. Rien n'est patché, donc
        # rien à restaurer — et l'assertion de fin ne s'exécute pas non plus.
        yield
        return

    attempts: list[str] = []
    original = socket.socket.connect

    def _blocked(self, address, *args, **kwargs):
        try:
            host, port = address[0], address[1]
        except (TypeError, IndexError):      # AF_UNIX & co : rien à voir avec HTTP
            return original(self, address, *args, **kwargs)
        if port in (80, 443):
            attempts.append(f"{host}:{port}")
            raise ConnectionRefusedError(
                "blocked by tests/conftest.py::_no_real_http — a test must not call an "
                "external API"
            )
        return original(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    # Exposé pour le méta-test qui déclenche volontairement la frontière.
    request.node._http_attempts = attempts

    yield

    assert not attempts, (
        f"{request.node.nodeid} opened {len(attempts)} REAL outbound HTTP(S) "
        f"connection(s) to {', '.join(sorted(set(attempts)))}.\n"
        f"The credentials come from .env, so this spends real API quota, can write to a "
        f"real account, and fails in CI the moment there is no network.\n"
        f"Stub the client in the test. If the HTTP call IS what you mean to exercise, "
        f"patch the transport yourself — your patch lands after this one and is never "
        f"seen here."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Le backoff du retry ne se paie pas en temps de suite
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _retry_backoff_costs_no_wall_clock(monkeypatch):
    """`src.utils.retry` n'attend pas pendant les tests. Il compte quand même.

    Mesuré le 2026-08-28 avec `--durations` : **onze** tests de
    `test_collectors_errors.py` duraient exactement 6,00 s chacun — 2,0 s + 4,0 s, le
    backoff exponentiel de `retry(max_attempts=3, base_delay=2.0)` sur trois tentatives
    vouées à échouer. **66 s des 275 s de la suite passées à dormir**, un quart du
    total, pour vérifier qu'un collecteur LÈVE.

    Ce qui rend le remplacement sûr, et il fallait le vérifier avant : aucun test
    n'asserte sur du temps écoulé. `test_retry.py` pose déjà son propre patch sur
    `src.utils.retry.time.sleep` et n'asserte que sur les VALEURS reçues
    (`sleep_calls == [2.0, 4.0]`) — donc sur la stratégie de backoff, pas sur son
    effet horaire. Son patch s'applique par-dessus celui-ci et le masque le temps de
    son bloc ; il continue de mesurer exactement ce qu'il mesurait.

    Portée délibérément étroite : **ce `sleep`-ci**, pas `time.sleep` en général. Et
    l'écrire n'a pas suffi — la première version de cette fixture faisait
    `setattr(_retry.time, "sleep", …)`, or `_retry.time` **EST** le module `time`
    global (`retry.py` fait `import time`). Elle neutralisait donc tous les `sleep`
    du processus. Constat immédiat : la suite est passée de 275 s à **608 s** et les
    deux tests les plus lents sont devenus ROUGES — les attentes de rendu Streamlit
    et WeasyPrint retournaient instantanément et lisaient une page pas encore prête.

    Remplacer la RÉFÉRENCE dans l'espace de noms du module, et non l'attribut d'un
    module partagé, est la seule forme qui tienne la promesse du paragraphe ci-dessus.
    Septième fois dans ce dépôt que la portée est le défaut, et la première dans du
    code que je venais d'écrire en la décrivant correctement.
    """
    try:
        import src.utils.retry as _retry
    except ImportError:      # environnement sans le paquet applicatif : rien à borner
        return

    class _NoWait:
        """Le module `time` vu par `retry.py` seul : tout, sauf l'attente."""

        def __getattr__(self, name):
            return getattr(_real_time, name)

        @staticmethod
        def sleep(_seconds):
            return None

    import time as _real_time
    monkeypatch.setattr(_retry, "time", _NoWait())

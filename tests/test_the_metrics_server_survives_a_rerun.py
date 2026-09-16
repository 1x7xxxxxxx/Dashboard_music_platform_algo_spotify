"""Le serveur de métriques survit aux reruns, et la chrome est mesurée.

Type: Test
Uses: pytest, socket
Depends on: src/utils/metrics.py, src/dashboard/app.py, src/api/main.py
Persists in: nothing

Le défaut que ce fichier tient
-------------------------------
Streamlit **ré-exécute le script entier à chaque rerun**. `start_http_server()` lie un
port ; appelé deux fois, le second lève `OSError: [Errno 98] Address already in use`.

Ce qui rend ce défaut méchant, c'est son CALENDRIER : le premier rendu réussit, donc la
mise en route est verte, le déploiement passe, la sonde de santé répond 200. La panne
arrive au **premier clic d'un utilisateur**. Un défaut qui attend l'utilisateur pour se
montrer est exactement celui qu'un test doit attraper.

Et l'angle mort qu'il corrige
------------------------------
Le chronomètre historique (`app.py`) mesure `_render_page` et **exclut la barre
latérale** : 61 ms par vue contre 468-538 ms pour la page complète, un facteur 8 que
rien n'affichait. La phase `chrome` est cette correction. Un test qui vérifierait
seulement « une métrique existe » laisserait repasser l'angle mort — il faut vérifier
que les DEUX phases sont émises.
"""
from __future__ import annotations

import ast
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"
_METRICS = _ROOT / "src" / "utils" / "metrics.py"


@pytest.fixture(autouse=True)
def _fresh_metrics_module():
    """Remet le drapeau à zéro entre les tests, SANS retirer le module de `sys.modules`.

    ⚠️ Une première version faisait `sys.modules.pop(...)`. Refusée par
    `tests/test_no_test_deletes_a_module.py`, et à raison : `AppTest` partage
    `sys.modules` avec le processus des tests, donc un module retiré ici disparaît pour
    tous les tests suivants du même worker. On remet l'état à zéro plutôt que de
    supprimer le module — c'est l'état qui gêne, pas le module.
    """
    import src.utils.metrics as m

    saved = m._SERVER_STARTED
    m._SERVER_STARTED = False
    yield
    m._SERVER_STARTED = saved


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_starting_twice_binds_only_once(monkeypatch) -> None:
    """C'EST le test du drapeau : trois appels, UNE seule tentative de liaison."""
    monkeypatch.setenv("STREAMLIT_METRICS_PORT", str(_free_port()))
    monkeypatch.setenv("METRICS_ADDR", "127.0.0.1")
    import importlib

    m = importlib.import_module("src.utils.metrics")
    importlib.reload(m)

    calls: list = []

    import prometheus_client

    original = prometheus_client.start_http_server

    def _counting(*a, **k):
        calls.append(1)
        return original(*a, **k)

    monkeypatch.setattr(prometheus_client, "start_http_server", _counting)

    assert m.start_metrics_server() is True
    assert m.start_metrics_server() is True
    assert m.start_metrics_server() is True

    # ⚠️ Ce qu'on vérifie est le NOMBRE DE TENTATIVES DE LIAISON, pas l'absence
    # d'exception. Une première version assertait « ça ne lève pas » — et restait verte
    # quand on retirait le drapeau, parce que la capture d'`OSError` suffit à ne pas
    # lever. Elle prouvait donc la capture, jamais le drapeau.
    #
    # Sans drapeau, chaque rerun retente une liaison et journalise un avertissement :
    # sur une page cliquée cent fois, cent tentatives et cent lignes de log pour un
    # serveur qui tourne déjà.
    assert len(calls) == 1, (
        f"{len(calls)} tentatives de liaison pour trois appels — le drapeau de module "
        "ne retient plus rien. Streamlit ré-exécute ce script à CHAQUE rerun."
    )


def test_a_port_already_taken_is_survived(monkeypatch) -> None:
    """Un port déjà lié par quelqu'un d'autre ne doit pas faire tomber la page.

    Cas réel : deux workers dans le même conteneur, ou un rechargement à chaud. Le
    serveur TOURNE déjà — l'objectif est atteint, ce n'est pas un échec.
    """
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        port = occupied.getsockname()[1]
        monkeypatch.setenv("STREAMLIT_METRICS_PORT", str(port))
        monkeypatch.setenv("METRICS_ADDR", "127.0.0.1")
        import src.utils.metrics as m

        assert m.start_metrics_server() is True, (
            "un port déjà pris a fait rendre False — la page tomberait alors qu'un "
            "serveur répond."
        )


def test_both_phases_are_emitted() -> None:
    """`chrome` ET `view`. Sans les deux, l'angle mort du facteur 8 revient."""
    import src.utils.metrics as m

    m.observe_chrome("home", 0.46)
    with m.timed_rerun("home", phase="view"):
        pass

    body, _ = m.metrics_payload()
    text = body.decode()
    for phase in ("chrome", "view"):
        assert f'phase="{phase}"' in text, (
            f"la phase {phase!r} n'est pas émise. La séparation chrome/vue EST la "
            "correction : le chronomètre historique ne mesurait que la vue, et la "
            "chrome coûte ~8× plus."
        )


def test_the_app_measures_the_chrome_before_the_view() -> None:
    """La chrome est chronométrée dans `app.py`, et son départ précède la vue.

    Présence ≠ atteignabilité : un module de métriques que le rendu n'appelle jamais
    laisserait tous les tests ci-dessus verts.
    """
    # ⚠️ Par AST, jamais par `in src`. Une première version comparait des chaînes au
    # texte du fichier ; refusée par `tests/test_a_guard_reads_structure_not_text.py`,
    # et à raison : une assertion textuelle est satisfaite par un commentaire, donc
    # verte le jour où l'appel disparaît mais où la ligne qui l'explique reste.
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    body = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_main_body")

    called = {n.func.id for n in ast.walk(body)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    for name in ("start_rerun", "end_chrome", "view_timer"):
        assert name in called, (
            f"`{name}()` n'est plus appelé dans `_main_body` — le module de métriques "
            f"existerait sans qu'aucun rendu ne l'atteigne. Appels vus : {sorted(called)}"
        )

    # L'ORDRE : démarrer le chronomètre APRÈS avoir mesuré ne mesurerait rien.
    stmts = [ast.unparse(n) for n in body.body]
    first_call = next(i for i, x in enumerate(stmts) if "start_rerun()" in x)
    first_chrome = next(i for i, x in enumerate(stmts) if "end_chrome(" in x)
    assert first_call < first_chrome, (
        "`start_rerun()` doit précéder `end_chrome()` — sinon la phase chrome est "
        "mesurée depuis un instant qui ne veut rien dire."
    )
    assert first_call <= 1, (
        f"`start_rerun()` est la {first_call + 1}ᵉ instruction de `_main_body` : le "
        "chronomètre doit partir AVANT tout le reste, sinon il mesure une fraction."
    )


def test_the_api_exposes_metrics_and_exempts_it_from_the_limiter() -> None:
    """`/metrics` existe, et Prometheus ne se fait pas 429 dessus.

    240 requêtes par heure contre un budget de 120/min : compté, le collecteur serait
    refusé au bout de quelques minutes — et la métrique disparaîtrait exactement quand
    la charge monte, c'est-à-dire quand on la regarde.
    """
    from src.api import security

    assert "/metrics" in security._EXEMPT_PATHS, (
        f"`/metrics` n'est pas exempté du limiteur : {sorted(security._EXEMPT_PATHS)}"
    )
    assert '@app.get("/metrics"' in (_ROOT / "src" / "api" / "main.py").read_text(
        encoding="utf-8"), "la route `/metrics` a disparu de l'API"


def test_metrics_never_raise_when_the_backend_is_absent(monkeypatch) -> None:
    """Sans `prometheus_client`, le produit fonctionne — sans métriques.

    L'observabilité est optionnelle, le produit ne l'est pas.
    """
    import src.utils.metrics as m

    monkeypatch.setattr(m, "_M", None)
    m.observe_chrome("home", 1.0)
    m.observe_pool(1, 2, 3)
    m.count_error("home", "ValueError")
    with m.timed_rerun("home"):
        pass
    assert m.start_metrics_server() is False


# ─────────────────────────────────────────────────────────────────────────────
# La pile d'observabilité — ce qu'elle expose, et à qui
# ─────────────────────────────────────────────────────────────────────────────

_OBS = _ROOT / "deploy" / "docker-compose.observability.yml"


def _obs() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(_OBS.read_text(encoding="utf-8")) or {}


def test_nothing_of_the_stack_is_published_beyond_loopback() -> None:
    """Prometheus et Grafana n'ont AUCUNE authentification devant Internet.

    L'arbitrage retenu est le tunnel SSH. Un `ports: ['3000:3000']` sans adresse
    publierait sur 0.0.0.0 — Grafana joignable depuis Internet avec son mot de passe
    par défaut, et Prometheus sans aucun mot de passe du tout.
    """
    offenders: list[str] = []
    for name, svc in (_obs().get("services") or {}).items():
        for spec in (svc.get("ports") or []):
            if not str(spec).startswith("127.0.0.1:"):
                offenders.append(f"{name} → {spec}")
    assert not offenders, (
        "port(s) publié(s) au-delà de la loopback :\n  " + "\n  ".join(offenders)
        + "\n\nPrometheus n'a aucune authentification et Grafana démarre sur un mot de "
        "passe par défaut. L'accès est un tunnel SSH, pas une surface publique."
    )


def test_prometheus_listens_on_the_container_network() -> None:
    """Pas de `--web.listen-address=127.0.0.1` : ce serait la loopback DU CONTENEUR.

    Défaut commis puis corrigé le 2026-09-16 : lié ainsi, ni le mappage de port ni
    Grafana — qui l'atteint par `streamlytics_prometheus:9090` sur le réseau Docker —
    ne pourraient l'atteindre. La restriction d'accès vient du MAPPAGE, jamais du
    binaire.
    """
    cmd = " ".join((_obs().get("services") or {}).get("prometheus", {}).get("command", []))
    assert "127.0.0.1:9090" not in cmd, (
        f"Prometheus se lie à la loopback du conteneur : {cmd!r}. Grafana ne pourrait "
        "plus l'interroger, et le tableau serait vide sans qu'aucune erreur ne le dise."
    )


def test_grafana_never_calls_home_at_boot() -> None:
    """`GF_INSTALL_PLUGINS` vide — REX importé de msdr, où il a coûté une panne.

    Grafana appelle grafana.com AU DÉMARRAGE quand cette variable est peuplée : le
    conteneur ne boote alors pas hors ligne (classe `b-grafana-offline-boot`).
    """
    env = (_obs().get("services") or {}).get("grafana", {}).get("environment", {})
    assert env.get("GF_INSTALL_PLUGINS", "") == "", (
        f"GF_INSTALL_PLUGINS vaut {env.get('GF_INSTALL_PLUGINS')!r} — Grafana appellera "
        "grafana.com au démarrage et ne bootera pas hors ligne."
    )


def test_every_scrape_target_is_named_not_discovered() -> None:
    """Aucune découverte automatique : cette machine porte AUSSI des conteneurs msdr.

    Le dépôt a déjà payé cette confusion — la sonde Docker du hook Stop est passée au
    VERT parce que des conteneurs `msdr_*` tournaient, pendant que
    `postgres_spotify_airflow` était à terre.
    """
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load(
        (_ROOT / "deploy" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8"))
    jobs = cfg.get("scrape_configs") or []
    assert jobs, "aucun job de scrape — la configuration est vide"
    for job in jobs:
        assert "static_configs" in job, (
            f"le job {job.get('job_name')!r} n'utilise pas `static_configs` : une "
            "découverte automatique ramasserait les conteneurs d'un autre projet."
        )
        for key in ("docker_sd_configs", "dns_sd_configs", "file_sd_configs"):
            assert key not in job, f"{job.get('job_name')!r} utilise {key}"


def test_the_scrape_targets_agree_with_the_caddy_upstreams() -> None:
    """Ce que Caddy sert et ce que Prometheus scrute doivent dire la MÊME chose.

    Réécrit le 2026-09-16. La version d'avant exigeait DEUX répliques scrutées ; la
    seconde est arrêtée depuis (mesure de R114 ambiguë, décision reportée à ADR-027), et
    sa cible a été retirée parce que Prometheus n'a pas de notion de « arrêté
    volontairement » : une réplique éteinte reste `down` pour toujours, et un rouge
    permanent apprend à lire le rouge comme du bruit.

    Le garde change donc de question, et la nouvelle est plus forte que l'ancienne : il
    ne demande plus « y a-t-il deux répliques », il demande **l'accord des deux
    surfaces**. Les deux dérives qu'il attrape sont réelles, dans les deux sens :

    * un amont servi que rien ne scrute — on refait l'expérience R114 en aveugle ;
    * une cible scrutée qu'aucun amont ne sert — un `down` permanent, pour rien.

    Le label `instance_role` reste exigé quoi qu'il arrive : sans lui, les requêtes de
    Grafana seraient à réécrire le jour où la réplique revient.
    """
    import re

    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load(
        (_ROOT / "deploy" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8"))
    job = next(j for j in cfg["scrape_configs"] if j["job_name"] == "dashboard")

    scraped = set()
    for sc in job["static_configs"]:
        assert sc.get("labels", {}).get("instance_role"), (
            f"cible sans `instance_role` : {sc}. Sans le label, on ne peut pas savoir "
            "laquelle sert ni à quel prix — c'est toute la question de R114.")
        scraped.update(t.split(":")[0] for t in sc["targets"])

    caddy = (_ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    # La ligne `reverse_proxy` du dashboard, hors commentaire : un bloc qui DÉCRIT la
    # remise en service n'est pas de la mise en service.
    upstream_ports = set()
    for line in caddy.splitlines():
        bare = line.strip()
        if bare.startswith("#") or not bare.startswith("reverse_proxy "):
            continue
        upstream_ports.update(re.findall(r"127\.0\.0\.1:(\d+)", bare))
    assert upstream_ports, (
        "aucune ligne `reverse_proxy` lue dans `deploy/Caddyfile` — la lecture est "
        "cassée, et le garde serait vert à vide")

    replica_served = "8511" in upstream_ports
    replica_scraped = "streamlytics_dashboard2" in scraped
    assert replica_served == replica_scraped, (
        f"désaccord : Caddy sert la réplique = {replica_served}, Prometheus la scrute = "
        f"{replica_scraped}.\n"
        "  • servie sans être scrutée => elle prend du trafic sans être mesurée, "
        "c'est-à-dire qu'on refait l'expérience R114 en aveugle ;\n"
        "  • scrutée sans être servie => une cible `down` pour toujours, et un rouge "
        "permanent apprend à lire le rouge comme du bruit.\n"
        "  Les trois gestes de remise en service sont écrits en UN endroit : le bloc "
        "au-dessus de `reverse_proxy` dans `deploy/Caddyfile`."
    )
    assert "streamlytics_dashboard" in scraped, (
        f"l'instance principale n'est plus scrutée du tout : {scraped}")

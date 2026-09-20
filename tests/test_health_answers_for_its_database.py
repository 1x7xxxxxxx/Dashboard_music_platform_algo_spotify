"""`/health` ne dit « ok » que si la base répond — et le CHEMIN RÉEL est exercé.

Type: Test
Uses: fastapi.testclient, la base joignable
Depends on: src/api/main
Persists in: nothing

Pourquoi ce garde existe
------------------------
`/health` rendait `{"status": "ok"}` **sans aucune vérification**, et deux surfaces en
font un verdict FINAL : `railway.toml:24` et `Dockerfile.api:54` (`HEALTHCHECK`). Un
conteneur dont la base est injoignable était déclaré sain — et **continuait de recevoir
du trafic**.

⚠️ **LA VERSION PRÉCÉDENTE DE CE FICHIER ÉTAIT VERTE SUR UN ENDPOINT CASSÉ.** Cinq tests
passaient pendant que `/health` rendait **503 sur une base saine** : trois simulaient
`_base_repond` — la fonction même qu'ils prétendaient vérifier — et le faux double de la
base acceptait n'importe quel SQL en rendant `[(1,)]`, donc il ne pouvait pas reproduire
le `ProgrammingError` que `fetch_query("SET …")` lève réellement.

**Un test qui simule la fonction qu'il vérifie ne vérifie rien.** Le premier test
ci-dessous exerce donc le chemin COMPLET contre une vraie base, et les simulations ne
servent plus qu'à fabriquer les états qu'on ne peut pas provoquer.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _vider_le_cache(main) -> None:
    main._sante_etat["verdict"] = None
    main._sante_etat["quand"] = 0.0


@pytest.fixture
def api():
    tc = pytest.importorskip("fastapi.testclient")
    from src.api import main
    _vider_le_cache(main)
    return tc.TestClient(main.app), main


def _base_joignable() -> bool:
    try:
        import psycopg2

        from src.utils.pg_connect import resolve_kwargs
        psycopg2.connect(connect_timeout=2, **resolve_kwargs()).close()
        return True
    except Exception:                          # noqa: BLE001
        return False


def test_the_real_probe_says_ok_against_a_real_database() -> None:
    """LE TEST QUI MANQUAIT. Aucune simulation : la sonde, la vraie base, le vrai verdict.

    ⚠️ C'est exactement celui-ci qui aurait attrapé le défaut livré le 2026-09-20 :
    `_base_repond()` rendait `(False, 'ProgrammingError')` sur une base parfaitement
    saine, parce que la sonde posait son délai par `fetch_query("SET LOCAL …")` et que
    `fetch_query` appelle `fetchall()` après l'exécution — un `SET` ne renvoie rien.
    Railway n'aurait jamais validé un déploiement.
    """
    if not _base_joignable():
        pytest.skip("base injoignable — la mesure n'est pas possible")
    from src.api import main
    _vider_le_cache(main)
    ok, motif = main._base_repond()
    assert ok is True, (
        f"la sonde rend {motif!r} sur une base JOIGNABLE. `/health` répondrait 503 en "
        "permanence : Railway ne validerait aucun déploiement et Docker marquerait le "
        "conteneur `unhealthy` en 90 s.")


def test_a_reachable_database_answers_200(api) -> None:
    if not _base_joignable():
        pytest.skip("base injoignable")
    c, main = api
    _vider_le_cache(main)
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_an_unreachable_database_answers_503(api) -> None:
    """Le CODE HTTP est le contrat — c'est lui que lisent `curl --fail` et Railway."""
    c, main = api
    _vider_le_cache(main)
    # ⚠️ LE `finally` N'EST PAS UNE PRÉCAUTION — il répare quatre tests rouges.
    # `_sante_etat` est un état de PROCESSUS, borné à 5 s par conception (c'est la borne
    # de charge de l'endpoint). Ce test y écrit un verdict FAUX via la simulation ; sans
    # nettoyage, ce verdict survivait à son propre test et quatre tests de TROIS autres
    # fichiers — `test_api.py::test_health`, `test_headers_present_on_health`,
    # `test_health_exempt`, `test_the_health_probe_is_never_blocked_by_the_edge_check` —
    # lisaient `degraded` sur une base parfaitement joignable.
    # Aucun de ces quatre n'a tort : ils vérifient que rien EN AMONT n'entrave `/health`,
    # et le 503 qu'ils voyaient venait d'ici. Un test qui FORCE un état de processus
    # porte la responsabilité de le rendre.
    try:
        with mock.patch.object(main, "_sonder_la_base", return_value=(False, "database")):
            r = c.get("/health")
    finally:
        _vider_le_cache(main)
    assert r.status_code == 503, (
        f"base injoignable et `/health` rend {r.status_code}. Un 200 ici laisse un "
        "conteneur sans base recevoir du trafic.")
    assert r.json()["status"] == "degraded"


def test_the_probe_never_raises() -> None:
    """Une sonde qui lève transforme une base lente en 500, donc en fausse panne."""
    from src.api import main
    with mock.patch("src.utils.pg_connect.resolve_kwargs",
                    side_effect=RuntimeError("boum")):
        ok, motif = main._sonder_la_base()
    assert ok is False and motif == "database"


def test_the_reason_is_a_closed_vocabulary_not_an_oracle() -> None:
    """`reason` ne distingue pas les états internes de la base.

    ⚠️ Rendre `type(exc).__name__` — ce que faisait le premier jet — donne à un appelant
    ANONYME un oracle : `OperationalError`, `AdminShutdown` et `TooManyConnections` sont
    trois états distincts de l'infrastructure. Et un message psycopg2 porterait l'hôte,
    le port et l'utilisateur. La classe part au journal.
    """
    from src.api import main
    secret = "host=10.0.0.4 user=postgres password=hunter2"   # pragma: allowlist secret
    with mock.patch("src.utils.pg_connect.resolve_kwargs",
                    side_effect=RuntimeError(secret)):
        _, motif = main._sonder_la_base()
    assert motif == "database", (
        f"`reason` vaut {motif!r} — il doit appartenir à un vocabulaire fermé, sans "
        "nommer la classe d'exception ni rien de la connexion.")


def test_a_burst_on_a_cold_cache_opens_ONE_connection() -> None:
    """LA BORNE DE CHARGE, et elle n'était pas tenue.

    ⚠️ Mesuré sur le premier jet : **20 sondes simultanées ouvraient 20 connexions**. La
    lecture du cache et son écriture encadraient la sonde, donc tout le monde passait le
    test avant que le premier n'écrive. Et `_borrow_from_pool()` retombe sur un
    `psycopg2.connect()` direct quand le pool est épuisé — `maxconn` ne borne rien. Sur
    un endpoint public et non limité, c'est un vecteur de déni de service.
    """
    from src.api import main
    _vider_le_cache(main)
    appels = {"n": 0}
    verrou = threading.Lock()

    def _sonde_lente():
        with verrou:
            appels["n"] += 1
        time.sleep(0.05)
        return (True, "ok")

    with mock.patch.object(main, "_sonder_la_base", side_effect=_sonde_lente):
        fils = [threading.Thread(target=main._base_repond) for _ in range(20)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
    assert appels["n"] == 1, (
        f"{appels['n']} sonde(s) pour 20 requêtes simultanées à cache froid — le verrou "
        "ne sérialise pas, et chaque sonde ouvre sa propre connexion.")


def test_a_probe_slower_than_the_ttl_is_still_cached() -> None:
    """L'horodatage est posé APRÈS la sonde, pas avant.

    ⚠️ Le premier jet le lisait AVANT : une sonde plus longue que le TTL produisait une
    entrée déjà périmée à l'écriture, donc le cache ne protégeait jamais dans le seul
    régime qui le justifie — une base lente. Mesuré : sonde de 10,4 s, TTL 5 s, trois
    connexions pour trois sondes.
    """
    from src.api import main
    _vider_le_cache(main)
    appels = {"n": 0}

    def _tres_lente():
        appels["n"] += 1
        time.sleep(main._SANTE_TTL_S + 0.2)
        return (True, "ok")

    with mock.patch.object(main, "_sonder_la_base", side_effect=_tres_lente):
        main._base_repond()
        main._base_repond()
    assert appels["n"] == 1, (
        f"{appels['n']} sondes : une sonde plus lente que le TTL ne met rien en cache.")


def test_the_verdict_is_written_before_its_timestamp() -> None:
    """Sinon un lecteur voit un instant FRAIS avec un verdict PÉRIMÉ.

    Les écritures de dict sont atomiques sous le GIL : le défaut n'est pas la corruption,
    c'est l'ORDRE. Servir `200 ok` pendant un TTL entier alors que la base vient de
    tomber est précisément ce que cet endpoint doit empêcher.
    """
    import ast
    src = (ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    fn = next(n for n in ast.walk(arbre)
              if isinstance(n, ast.FunctionDef) and n.name == "_base_repond")
    ordre = [ast.unparse(n.targets[0]) for n in ast.walk(fn)
             if isinstance(n, ast.Assign) and "_sante_etat[" in ast.unparse(n.targets[0])]
    assert ordre and "verdict" in ordre[0], (
        f"ordre d'écriture du cache : {ordre}. Le VERDICT doit être posé avant son "
        "instant, sinon un lecteur concurrent lit un instant frais sur un verdict vieux.")

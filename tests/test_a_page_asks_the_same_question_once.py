"""Une page ne pose pas deux fois la même question à la base.

Type: Test
Uses: pytest, streamlit.testing.v1.AppTest, live Postgres
Depends on: src/dashboard/views/home.py, src/dashboard/utils/platform_timeseries.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
Le rendu de l'accueil exécutait **14 requêtes pour 13 questions distinctes** : la
lecture des relevés Apple (`_apple_readings`) partait deux fois, avec exactement les
mêmes paramètres, parce que trois fonctions différentes en ont besoin au même rendu.

Ce garde compte les allers-retours SQL d'un rendu réel, en instrumentant
`PostgresHandler`. Il ne mesure pas un temps — une mesure de temps depuis WSL est
inexploitable en valeur absolue, leçon déjà payée ici — il compte des ÉVÉNEMENTS, ce
qui est reproductible partout.

Ce qu'un doublon n'est pas
--------------------------
Le même texte SQL avec des paramètres différents n'est pas un doublon : l'accueil
interroge la vue or `v_platform_totals` trois fois, une par plateforme, et c'est
exactement ce qu'on lui demande. La clé de comptage inclut donc les paramètres. Sans
cela ce garde aurait « trouvé » trois faux doublons et manqué le vrai.
"""
from __future__ import annotations

import json
import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — needs a live DB")

# Gelé le 2026-09-10, après retrait du doublon Apple. CE NOMBRE NE PEUT QUE DESCENDRE.
# Mesuré À FROID le 2026-09-11 — caches vidés dans le script, cf. `_SCRIPT`.
#
# Le plafond était 13/11, et ces deux nombres n'étaient pas comparables : ils
# avaient été gelés sur des caches RÉCHAUFFÉS par les tests précédents du même
# worker. Preuve : `main`, ce fichier lancé SEUL sur une base neuve, rend **13**
# pour un plafond de 11 — il ne passait qu'accompagné.
#
# À froid, `main` et la branche rendent le MÊME nombre : 13 et 13. Le plafond est
# donc regelé sur une mesure qui ne dépend plus de son voisinage, pas relevé pour
# laisser passer une régression. Il ne monte toujours pas.
_MAX_QUERIES = {"admin": 13, "artist": 13}

_SCRIPT = """
import sys, json, collections, re
sys.path.insert(0, {root!r})
from src.database.postgres_handler import PostgresHandler
_seen = collections.Counter()
def _norm(q):
    return re.sub(r'\\s+', ' ', str(q)).strip()[:200]
for _name in ('fetch_df', 'fetch_query', 'execute_query'):
    _orig = getattr(PostgresHandler, _name)
    def _make(orig=_orig):
        def wrapper(self, query, *a, **k):
            _seen[_norm(query) + ' @@ ' + repr(a[:1])] += 1
            return orig(self, query, *a, **k)
        return wrapper
    setattr(PostgresHandler, _name, _make())
import streamlit as st
# LES CACHES SONT VIDÉS AVANT DE COMPTER, et c'est ce qui rend ce nombre lisible.
# Sans ça le test mesurait son VOISINAGE : `kpi_helpers` garde ses lectures 600 s,
# donc le compte dépendait de ce que les tests précédents avaient réchauffé dans le
# même worker. Mesuré le 2026-09-11 : `main`, ce fichier lancé SEUL sur une base
# neuve, rend 13 pour un plafond de 11 — il ne passait qu'accompagné.
from src.dashboard.utils.kpi_helpers import clear_kpi_caches as _clear
_clear()
st.session_state["role"] = {role!r}
st.session_state["artist_id"] = 1
st.session_state["email"] = "probe@test"
st.session_state["authenticated"] = True
try:
    from src.dashboard.views.home import show
    show()
finally:
    open({out!r}, 'w').write(json.dumps(dict(_seen)))
"""


def _render(role: str, tmp_path) -> dict:
    from streamlit.testing.v1 import AppTest
    out = str(tmp_path / f"q_{role}.json")
    at = AppTest.from_string(
        _SCRIPT.format(root=os.getcwd(), role=role, out=out))
    at.run(timeout=180)
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("role", ["admin", "artist"])
def test_no_query_is_sent_twice_with_the_same_parameters(role, tmp_path) -> None:
    counts = _render(role, tmp_path)
    assert counts, "aucune requête interceptée — l'instrumentation est cassée"
    dups = {k: v for k, v in counts.items() if v > 1}
    assert not dups, (
        "l'accueil pose deux fois la même question, mêmes paramètres :\n" +
        "\n".join(f"  ×{v}  {k[:150]}" for k, v in sorted(dups.items(),
                                                          key=lambda x: -x[1])))


@pytest.mark.parametrize("role", ["admin", "artist"])
def test_the_number_of_round_trips_only_goes_down(role, tmp_path) -> None:
    """Un cliquet : une page qui se met à interroger plus n'entre pas en silence."""
    total = sum(_render(role, tmp_path).values())
    assert total <= _MAX_QUERIES[role], (
        f"{total} allers-retours SQL pour un rendu de l'accueil en `{role}`, contre "
        f"un plafond de {_MAX_QUERIES[role]} gelé le 2026-09-10. Ce plafond ne monte "
        "pas : si la page a besoin d'une donnée de plus, elle la lit dans une requête "
        "existante ou passe par la couche or.")

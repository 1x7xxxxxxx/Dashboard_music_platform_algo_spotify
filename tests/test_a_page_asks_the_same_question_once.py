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
import sys

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


pytestmark = [pytest.mark.xdist_group("a-page-asks-the-same-question-once"), pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — needs a live DB")]

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
#
# 2026-09-15 : `artist` passe de 13 à **14**, et ce n'est PAS un relèvement pour
# laisser passer une régression — c'est la correction d'un plafond qui n'avait
# jamais été froid. Le 13 était la mesure d'un second rendu, cache de plan déjà
# chaud. À froid, `main` et cette branche rendent 14 toutes les deux ; aucune
# requête n'a été ajoutée. Même geste, même raison qu'en 2026-09-11 ci-dessus.
# Preuve rejouable : trois rendus successifs rendent désormais 14, 14, 14.
_MAX_QUERIES = {"admin": 13, "artist": 14}

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
# ET TOUS LES AUTRES, SANS LES NOMMER. `clear_kpi_caches` purge une LISTE de dix
# fonctions ; cette liste se périme dès qu'un cache est ajouté au chemin chaud de
# l'accueil, et le cliquet se remet alors à mesurer son voisinage.
#
# C'est arrivé, et c'est la troisième fois pour ce fichier. `_cached_plan_row`
# (`auth.py`, `@st.cache_data(ttl=60)`, écrit le 2026-09-03 avec `plan_resolver`)
# n'était dans aucune liste. Mesuré le 2026-09-15, trois rendus successifs dans un
# processus neuf : `artist` rend **14, 13, 13** — le premier paie la requête de
# plan, les suivants la lisent au cache. Le plafond de 13 avait donc été gelé sur
# un cache CHAUD, et il ne tenait qu'en ordre de fichier ; `pytest-randomly`
# (graine 11111) le fait tomber en le plaçant avant son réchauffeur.
#
# `st.cache_data.clear()` ne s'énumère pas : elle ne peut pas se périmer. Avec
# elle : **14, 14, 14**. `admin` rend 13 dans les deux cas — `get_artist_plan()`
# répond `premium` sans toucher la base pour un admin, donc la requête de plan
# n'existe pas sur ce chemin. Cette asymétrie EST la preuve de la cause.
st.cache_data.clear()
# ET l'état du LOCATAIRE est fixé, pas subi.
#
# La page coûte deux prix selon que la mise en route est finie ou non : terminée
# elle lit ses sections de données, inachevée elle rend EN PLUS la matrice de
# mise en route (fraîcheur par source, sonde Meta, identifiants) — dix requêtes.
# Le plafond avait été gelé sur une base locale où l'artiste 1 est configuré ; en
# CI la base est neuve et il ne l'est pas, d'où 13 ici et 23 là-bas pour le MÊME
# code. Le test comparait donc deux états, pas deux versions.
#
# On mesure l'état « configuré », celui d'un artiste installé — c'est la page que
# la plupart des rendus servent. Le coût de la mise en route se mesure ailleurs.
import src.dashboard.utils.setup_completion as _sc
_sc_original = _sc.read_setup_state
_sc.read_setup_state = lambda *a, **k: _sc.SetupState(
    steps=[_sc.Step(k_, True, p_) for k_, p_ in _sc._STEP_PAGES],
    show_on_login=False, collected=True)
st.session_state["role"] = {role!r}
st.session_state["artist_id"] = 1
st.session_state["email"] = "probe@test"
st.session_state["authenticated"] = True
try:
    from src.dashboard.views.home import show
    show()
finally:
    # LA DOUBLURE EST RENDUE. Elle a été posée par une affectation nue, dans un
    # script qui s'exécute DANS le processus des tests : sans ce rétablissement,
    # tous les tests suivants du même worker voyaient une mise en route
    # TERMINÉE. Mesuré en CI le 2026-09-11 :
    # `test_the_tab_bar_skips_what_is_done` trouvait l'onglet « 📂 Mes fichiers »
    # vert pour un locataire qui venait d'être créé vide. Un test qui change
    # l'état du processus doit le rendre — classe « une suite de tests a un
    # rayon de souffle ».
    _sc.read_setup_state = _sc_original
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

    # NON-VACUITÉ. Ajoutée le 2026-09-12 : `total <= plafond` est vrai pour ZÉRO
    # requête, et un rendu qui échoue silencieusement en produit zéro. Le cliquet
    # était alors au vert sur une page qui ne s'affiche plus — la forme exacte que
    # ce dépôt appelle « un prédicat sans site ».
    assert total >= 5, (
        f"seulement {total} requête(s) pour un rendu complet de l'accueil en "
        f"`{role}` : il y en avait 13 le 2026-09-10. Le rendu n'a probablement pas "
        "abouti, et un plafond comparé à zéro ne garde rien.")

    # Mutation record — 2026-09-12 : plancher abaissé à 0 et le script neutralisé,
    # le test reste vert ; avec le plancher, il nomme le compte. Et un plafond
    # descendu à 12 le fait rougir sur la mesure réelle (13).

# Le seul moyen d'obtenir un compte VRAIMENT froid quand le processus courant a déjà
# tout réchauffé : en ouvrir un autre. Une comparaison faite entièrement en mémoire
# ne peut pas distinguer « la purge marche » de « personne n'avait rien réchauffé ».
_FRESH = """
import sys, tempfile, pathlib
sys.path.insert(0, {root!r})
import tests.test_a_page_asks_the_same_question_once as M
d = tempfile.mkdtemp()
print("TOTAL=%d" % sum(M._render({role!r}, pathlib.Path(d)).values()))
"""


def _render_in_a_fresh_process(role: str) -> int:
    """Le compte d'un rendu dans un processus qui n'a RIEN réchauffé."""
    import subprocess

    out = subprocess.run(
        [sys.executable, "-c", _FRESH.format(root=os.getcwd(), role=role)],
        capture_output=True, text=True, timeout=600, cwd=os.getcwd())
    for line in out.stdout.splitlines():
        if line.startswith("TOTAL="):
            return int(line.split("=", 1)[1])
    raise AssertionError(
        "le processus neuf n'a rendu aucun compte — l'instrumentation est cassée.\n"
        f"rc={out.returncode}\nstdout:\n{out.stdout[-2000:]}\nstderr:\n{out.stderr[-2000:]}")


def test_the_count_does_not_depend_on_its_neighbourhood(tmp_path) -> None:
    """Le même rendu, dans un processus chaud et dans un processus neuf, donne le même compte.

    C'est LA propriété ; les deux plafonds ci-dessus n'en sont que la valeur. Un
    cliquet dont le nombre bouge selon ce qui a tourné avant lui dans le même
    processus ne garde rien — il passe accompagné et tombe seul, et dans les deux
    cas il parle de son ordre d'exécution, pas du code. Sous `--dist loadgroup`,
    « ce qui a tourné avant » cesse même d'être prévisible.

    Trois fois ce fichier a été corrigé pour cette raison — caches KPI réchauffés
    (2026-09-11), état de mise en route subi (2026-09-11), cache de plan
    (2026-09-15). Les deux premières fois le correctif fut d'ajouter un nom à une
    liste ; cette assertion ne nomme aucun cache et échoue donc quel que soit
    celui qui manque à l'appel.

    Le rendu de réchauffage est DÉLIBÉRÉ, et il est la moitié du garde : sans lui,
    l'assertion serait verte quand ce test tombe en premier dans un ordre aléatoire
    — un garde qui ne rougit que placé au bon endroit est exactement le défaut
    qu'on corrige ici. Mesuré le 2026-09-15 : la première version, qui comparait
    deux rendus en mémoire, est restée VERTE sur la mutation.

    Mutation vérifiée : retirer `st.cache_data.clear()` de `_SCRIPT` → 13 contre 14.
    """
    _render("artist", tmp_path)            # on réchauffe DÉLIBÉRÉMENT, quel que soit l'ordre
    chaud = sum(_render("artist", tmp_path).values())
    froid = _render_in_a_fresh_process("artist")
    assert chaud == froid, (
        f"{chaud} allers-retours dans un processus déjà chaud, {froid} dans un processus "
        "neuf. Un cache du chemin chaud survit à la purge de `_SCRIPT` : le cliquet "
        "mesure ce que ses voisins ont réchauffé, pas la page.")

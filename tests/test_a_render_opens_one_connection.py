"""Rule #9, asked of the render instead of of the source text.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres
Depends on: src/dashboard/views/*.py, src/database/postgres_handler.py
Persists in: nothing

Why this exists next to `test_view_connection_budget.py`
--------------------------------------------------------
That file answers rule #9 with a regex:

    len(re.findall(r"get_db_connection\\(\\)", path.read_text()))

which counts how many times a FILE types a string. Three things it cannot see:

  * `project_db()` and `view_session()` — both open a connection, neither matches;
  * a connection opened by a **callee** (a helper, a shared widget, kpi_helpers);
  * its own comments, which is how four guards written on 2026-08-22 passed on
    their own explanatory text.

Its header states "every view now opens exactly one connection per render".
Measured at runtime on 2026-08-30 by patching `PostgresHandler._connect` and
rendering each of the 42 views: **41 open one, `hypeddit` opens two.** The second
comes from a helper, which a per-file count can never attribute.

The older test keeps its ratchet and its REX — it stops the *textual* count from
growing, which is still useful. This one asks the question rule #9 actually poses:
how many connections does rendering this page open?
"""
from __future__ import annotations

import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Runtime ceiling per view. A view absent from this map must open at most one.
# Lower a number when a view is fixed; never raise one.
_KNOWN_MULTI: dict[str, int] = {}
# Emptied 2026-08-30. `hypeddit` was the last at 2, and the second connection was not
# a second `get_db_connection()` — it was `_render_history()` calling `db.close()` on
# the connection `show()` owns, after which `_render_entry_form()` kept querying and
# `PostgresHandler._ensure_connection()` silently reconnected. The page worked; only
# a count taken AT THE RENDER could see it.


# La porte LÉGÈRE. Le corps recopié ici importait `get_db_connection`
# (**5,30 s**, dont 5,19 s de Streamlit) et ouvrait une connexion À L'IMPORT du
# module, donc à la collecte, une fois par fichier et par worker.
# `tests.db_gate.db_ready` répond en 0,19 s, derrière un `lru_cache` partagé, et
# sonde en plus `DATABASE_URL` et le schéma réel. Le nom est conservé : seuls le
# coût et le nombre de connexions changent.
from tests.db_gate import db_ready as _db_ready  # noqa: E402


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — "
           "counting connections needs the real render path",
)

# Source UNIQUE — `tests/render_harness.py`. Ces constantes vivaient en double
# dans les deux fichiers de rendu et ont divergé NEUF JOURS (voir le module).
from tests.render_harness import VIEWS  # noqa: E402
from tests.render_harness import render_once  # noqa: E402
from tests.render_harness import une_vue_ouvre_vraiment_une_connexion  # noqa: E402

# Le rendu est partagé avec `test_views_render_smoke.py` par un `lru_cache`, qui
# vit dans UN processus. `xdist_group` place les deux tests d'une vue dans le même
# worker ; sans lui, sous `-n`, le cache ne sert rien et le gain disparaît EN
# SILENCE — aucun test ne rougit.
_VUES = [pytest.param(v, marks=pytest.mark.xdist_group(v)) for v in VIEWS]
# `process_guide` et `upload_csv` ont quitté cette liste le 2026-09-15, NEUF JOURS
# après avoir quitté celle de `test_views_render_smoke.py:130-143` — qui explique
# déjà pourquoi : `src/dashboard/views/process_guide.py` a été SUPPRIMÉ, et
# `upload_csv.py` n'a plus de `show()` depuis la fusion du 2026-09-04.
#
# Le frère a été corrigé, celui-ci ne l'a pas été, et rien ne l'a vu : le script
# levait à l'import, ouvrait ZÉRO connexion, et `0 <= 1` passait. Deux `AppTest`
# complets payés à chaque exécution pour ne rien prouver. C'est la moitié « on a
# corrigé l'instance et laissé les frères vivants » ; l'autre moitié — la borne
# basse manquante — est traitée dans `connections_opened_by` ci-dessous.



def connections_opened_by(view: str) -> int:
    """Le compte de `PostgresHandler._connect` sur le rendu de `view`.

    Le rendu lui-même est délégué à `render_harness.render_once`, qui le paie UNE
    fois par worker et sert aussi `test_views_render_smoke.py`. Ce fichier gardait
    sa propre copie du rendu : les mêmes 39 vues étaient rendues deux fois par
    exécution, mesuré à 88,6 s (21,3 % de la suite) le 2026-09-18.
    """
    rendu = render_once(view)

    # ── La borne BASSE, ajoutée le 2026-09-15 ──
    # `opened <= plafond` est vrai pour ZÉRO connexion, et un rendu qui échoue à
    # l'import en ouvre zéro. Le plafond était donc au vert sur deux vues qui
    # n'existent plus — `process_guide` (module supprimé) et `upload_csv` (plus de
    # `show()`), pendant neuf jours.
    #
    # `test_a_page_asks_the_same_question_once.py:166-174` a appris exactement cette
    # leçon le 2026-09-12 et l'a nommée « un prédicat sans site ». Elle n'avait pas
    # été propagée ici. Un plafond comparé à zéro ne garde rien.
    if rendu.erreur is not None:
        raise AssertionError(
            f"le rendu de `{view}` a levé, donc il n'a ouvert aucune connexion et "
            f"le plafond passerait sur du vide :\n{rendu.erreur}"
        )
    return rendu.connexions


@pytest.mark.parametrize("view", _VUES)
def test_rendering_a_view_opens_at_most_its_ceiling(view):
    allowed = _KNOWN_MULTI.get(view, 1)
    opened = connections_opened_by(view)
    assert opened <= allowed, (
        f"{view}.show() opened {opened} connections (ceiling {allowed}). Rule #9: a "
        "view opens exactly one and never a second as a fallback. Note the count is "
        "of the RENDER, so a connection opened by a helper counts here even though "
        "the view's own source never spells `get_db_connection()`."
    )


def test_the_ceiling_map_has_not_gone_stale():
    """A ceiling above the real count hides a fix and invites a regression back to it."""
    stale = []
    for view, allowed in _KNOWN_MULTI.items():
        opened = connections_opened_by(view)
        if opened < allowed:
            stale.append(f"{view}: now opens {opened}, ceiling still says {allowed}")
    assert not stale, (
        "lower these ceilings — a stale one lets the count climb back for free:\n  "
        + "\n  ".join(stale)
    )


def test_the_counter_actually_counts():
    """Mutation: the instrument must move when a connection is opened.

    A counter wired to nothing reports 0 for every view and the whole file passes
    while measuring nothing — the failure mode this repo has hit four times.

    Depuis le 2026-09-18 la mutation porte sur `render_once`, la couture RÉELLEMENT
    lue par les 39 cas ci-dessus. Elle portait avant sur une copie locale de la
    technique de patch : une copie peut rester juste pendant que la couture servie
    rend zéro.
    """
    vue, compte = une_vue_ouvre_vraiment_une_connexion()
    assert compte >= 1, (
        "aucune des 39 vues n'a ouvert une seule connexion au rendu — le compteur de "
        "`render_once` n'est pas attaché au chemin de code qu'il prétend mesurer, et "
        "les 39 plafonds `<= 1` passent sur du vide."
    )
    assert vue, "aucune vue n'a rendu sans erreur"

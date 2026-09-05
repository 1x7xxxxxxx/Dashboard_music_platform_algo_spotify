"""Un verdict de sonde ne nomme que ce que la sonde a mesuré.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: views/credentials/_render.py, utils/status_matrix.py, utils/platform_probes.py
Persists in: tenant_platform_probe (lignes de test, écrasées)

Le 2026-09-05, un artiste a lu sur le même écran :

    ✅ Saisi   ✅ Format   ✅ Répond   🟢 Données
    ❌ ☁️ SoundCloud : enregistré, mais la plateforme ne répond pas encore.
       User ID 377065610 JOIGNABLE, mais aucun titre public…

Trois affirmations incompatibles, dont deux justes. Vérifié en base : ce locataire
portait **358 lignes** dans `soundcloud_tracks_daily`. Deux défauts distincts :

1. `ok is False` recouvre huit situations sur cinq sondes — HTTP 200 sans contenu,
   handle RÉSOLU, identité non saisie — et l'écran les traduisait toutes par « ne
   répond pas ». Le titre était un rendu de booléen ; le corps, qui SAIT pourquoi,
   était affiché en dessous sans participer au choix.
2. La règle « une mesure qui a eu lieu bat une prédiction » existait dans
   `_responds_cell` et sous le bouton « Tester », et manquait aux DEUX autres
   surfaces : le verdict d'enregistrement et la colonne « Prochaine étape ».

Le garde de la veille (`test_a_failing_probe_yields_to_data_that_actually_landed`)
était vert : il demandait « `_data_already_landed` est-il appelé quelque part ? », et
un seul appel le satisfaisait. La portée du garde était le défaut.
"""
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
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(), reason=f"needs the provisioned DB on {_DB_HOST}:{_DB_PORT}")

_REASON = "User ID 377065610 joignable, mais **aucun titre public** n'y est rattaché."

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
from src.dashboard.views.credentials._render import VERDICT_KEY
st.session_state["role"] = "artist"
st.session_state["artist_id"] = {aid}
st.session_state["email"] = "a@t"
st.session_state["name"] = "a@t"
st.session_state["authenticated"] = True
st.session_state[VERDICT_KEY] = ("soundcloud", False, {reason!r}, {cat!r})
from src.dashboard.views.credentials import show
show()
"""


def _flat(node, out=None):
    out = [] if out is None else out
    kids = getattr(node, "children", None)
    for child in (kids.values() if isinstance(kids, dict) else (kids or [])):
        out.append(child)
        _flat(child, out)
    return out


def _texts(artist_id: int, category):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(_SCRIPT.format(
        root=os.getcwd(), aid=artist_id, reason=_REASON, cat=category))
    at.run(timeout=180)
    assert not at.exception, at.exception
    return [str(getattr(e, "value", "") or getattr(e, "body", "") or "")
            for e in _flat(at.main)]


# Le locataire qui a réellement produit le rapport : des lignes SoundCloud existent.
_TENANT_WITH_DATA = 1
# Un locataire sans aucune ligne SoundCloud — le cas où l'échec est réel.
_TENANT_WITHOUT_DATA = 23702


@pytest.fixture(scope="module")
def _real_situation():
    """Les prémisses du rapport, POSÉES — pas lues sur ce qui traîne en base."""
    from src.dashboard.utils import get_db_connection
    from src.utils.artist_readiness import artist_readiness
    db = get_db_connection()
    try:
        rows = {r["key"]: r["status"] for r in artist_readiness(db, _TENANT_WITH_DATA)}
        if rows.get("soundcloud") not in ("ok", "stale", "quiet"):
            pytest.skip("ce locataire n'a plus de données SoundCloud : "
                        "la contradiction ne peut pas être reproduite")
        yield db
    finally:
        db.close()


def test_data_that_landed_beats_a_probe_that_predicts_otherwise(_real_situation):
    """Le cas exact du rapport : la sonde dit non, la collecte a déjà dit oui."""
    texts = _texts(_TENANT_WITH_DATA, "nothing_to_collect")
    joined = "\n".join(texts)

    assert any("est connecté" in x for x in texts), (
        "l'artiste reste sur un ❌ alors que sa plateforme livre")
    assert "ne répond pas" not in joined
    assert "n'est pas prouvée" not in joined
    # Le message de sonde n'est PAS effacé : il peut nommer un vrai problème.
    assert any("se trompe sur la conséquence" in x for x in texts)
    assert any("aucun titre public" in x for x in texts)
    # Il n'y a rien à corriger dans ce formulaire.
    assert "Corrige ci-dessous" not in joined
    # …et le parcours continue, décidé le 2026-09-05.
    assert any("Suivante" in x for x in texts), (
        "l'artiste est bloqué par une prédiction que la collecte a démentie")


def test_without_data_the_heading_names_the_situation_and_never_invents_one():
    """Chaque situation a son titre ; aucun ne dit « ne répond pas » à tort."""
    cases = {
        "nothing_to_collect": ("rien à collecter", False),
        "unreachable": ("n'a pas répondu", False),
        "not_found": ("introuvable", True),
        "refused": ("refusé", True),
        "identity_missing": ("manque ton identifiant", True),
        "resolved": ("une valeur à recopier", False),
    }
    for category, (needle, expects_gesture) in cases.items():
        texts = _texts(_TENANT_WITHOUT_DATA, category)
        joined = "\n".join(texts)
        assert needle in joined, f"{category} : titre attendu absent — {needle!r}"
        # Une seule situation autorise « ne répond pas », et c'est la sienne.
        if category != "unreachable":
            assert "n'a pas répondu" not in joined, (
                f"{category} affirme une cause que la sonde n'a pas mesurée")
        # « Corrige ci-dessous » ne se dit que d'un échec imputable à la saisie.
        assert ("Corrige ci-dessous" in joined) is expects_gesture, (
            f"{category} : le geste proposé ne correspond pas à la situation")


def test_an_unnamed_situation_falls_back_to_a_heading_asserting_no_cause():
    """`None` = verdict écrit avant la migration 086, ou sonde qui ne se prononce pas."""
    joined = "\n".join(_texts(_TENANT_WITHOUT_DATA, None))
    assert "n'est pas prouvée" in joined
    assert "ne répond pas" not in joined
    assert "n'a pas répondu" not in joined


def test_the_category_survives_the_round_trip_through_the_database():
    """Migration 086. Sans elle, le titre retombe sur le libellé neutre."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.status_matrix import read_probes, save_probe
    db = get_db_connection()
    try:
        save_probe(db, _TENANT_WITHOUT_DATA, "soundcloud", False, "x", "nothing_to_collect")
        remembered = read_probes(db, _TENANT_WITHOUT_DATA)["soundcloud"]
        assert len(remembered) == 4, "le tuple ne porte pas la situation"
        assert remembered[3] == "nothing_to_collect"
        save_probe(db, _TENANT_WITHOUT_DATA, "soundcloud", False, "x", None)
        assert read_probes(db, _TENANT_WITHOUT_DATA)["soundcloud"][3] is None
    finally:
        db.close()


def test_every_named_category_is_declared_and_every_declared_one_is_rendered():
    """Les deux listes ne peuvent pas diverger en silence.

    Une sonde qui rend une catégorie absente de la table de titres retomberait sur le
    libellé neutre — sans erreur, et sans que personne le voie.
    """
    from src.dashboard.views.credentials._render import _VERDICT_HEADINGS
    from src.utils.platform_probes import PROBE_CATEGORIES

    assert set(_VERDICT_HEADINGS) == set(PROBE_CATEGORIES), (
        "une situation nommée par une sonde n'a pas de titre, ou l'inverse : "
        f"{set(_VERDICT_HEADINGS) ^ set(PROBE_CATEGORIES)}")


# ── La situation est PRODUITE, et elle survit au transport ───────────────────
# Ces deux tests n'ont pas besoin de la base. Ils comblent le trou que deux
# mutations ont révélé : tout ce qui précède POSE la catégorie (dans `VERDICT_KEY`
# ou via `save_probe`) et n'exerçait donc jamais le chemin qui la fabrique. Retirer
# l'étiquette de la sonde SoundCloud, ou la laisser tomber dans `clamp()`, laissait
# la suite verte — deux façons silencieuses de retomber sur le libellé neutre.

_NO_DB = True  # sans base : ces deux-là tournent partout, y compris en CI


@pytest.mark.parametrize("category,payload", [
    ("nothing_to_collect", {"collection": []}),
])
def test_the_soundcloud_probe_names_the_situation_it_measured(category, payload):
    """HTTP 200 + zéro titre : « joignable », donc jamais « ne répond pas »."""
    from unittest.mock import MagicMock, patch

    from src.utils.platform_probes import category_of

    def _resp(status=200, body=None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = body if body is not None else {}
        r.text = str(body)
        return r

    with patch("src.dashboard.views.credentials._platform_soundcloud.requests") as req:
        req.post.return_value = _resp(200, {"access_token": "tok"})  # pragma: allowlist secret
        req.get.return_value = _resp(200, payload)
        from src.dashboard.views.credentials._platform_soundcloud import _test_soundcloud
        ok, msg = _test_soundcloud({"user_id": "377065610", "client_id": "cid",
                                    "client_secret": "sec"})  # pragma: allowlist secret

    assert ok is False
    assert category_of(msg) == category, (
        "la sonde ne nomme plus sa situation : l'écran retombera sur un titre neutre")
    # Le contrat public reste à DEUX éléments : le `ok, msg = …` ci-dessus lèverait
    # `ValueError` sinon — c'est ce qui est arrivé à 30 tests au premier essai, quand
    # la situation était un troisième élément du tuple.


def test_the_situation_survives_the_seam_that_reformats_the_message():
    """`clamp(str(...))` rend un `str` nu et PERD l'attribut. On ré-étiquette après."""
    from unittest.mock import patch

    from src.utils.platform_probes import NOTHING_TO_COLLECT, probe, tagged

    long_reason = tagged("joignable, mais aucun titre public. " + "x" * 4000,
                         NOTHING_TO_COLLECT)

    with patch("src.dashboard.views.credentials._registry.CONNECTION_TESTS",
               {"soundcloud": lambda fields: (False, long_reason)}), \
         patch("src.utils.platform_probes._identity_fields", return_value={"user_id": "1"}):
        verdict = probe(object(), 1, "soundcloud")

    assert verdict is not None
    ok, reason = verdict
    assert ok is False
    from src.utils.platform_probes import category_of
    assert category_of(reason) == NOTHING_TO_COLLECT, (
        "la situation est perdue entre la sonde et la mémoire des verdicts")
    assert len(reason) < 4000, "le message n'est plus tronqué"

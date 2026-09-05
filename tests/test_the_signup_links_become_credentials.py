"""Les liens saisis à l'inscription deviennent des credentials — au bon moment.

Type: Test
Uses: live Postgres (spotify_etl), l'API SoundCloud pour la résolution
Depends on: migration 087, views/credentials/_from_signup.py, views/register.py
Persists in: un locataire jetable, supprimé en fin de test

Demandé le 2026-09-05 : « ajouter des champs pour saisir le profil Spotify + SoundCloud
+ YouTube dans la page de création, et les rentrer dans credentials à un moment
pertinent ».

## Pourquoi on ne devine PAS depuis le nom d'artiste

Mesuré le même jour contre la vérité terrain — trois locataires de production dont
l'identifiant de plateforme est déjà vérifié — avec un filtre de nom EXACT :

    « Benken » → 4 profils SoundCloud du même nom, le bon est le QUATRIÈME
    « GRiNCH » → Spotify rend « Gringe », un autre artiste
    « Benken » → sur YouTube, la bonne chaîne n'est PAS dans les 5 premiers résultats

C'est aussi la réponse à « et si on cochait : même nom sur la plateforme ? ». Sur le cas
YouTube, le nom EST le même et le compte est faux : une case cochée de bonne foi
produirait une identité confiante et erronée. Un lien collé par son propriétaire ne se
trompe pas — d'où des CHAMPS, et pas une recherche.
"""
import json
import os
import socket
import uuid

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
        return db
    except Exception:  # noqa: BLE001
        return None


pytestmark = pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")


@pytest.fixture()
def tenant():
    db = _db()
    slug = f"e2e-links-{uuid.uuid4().hex[:8]}"
    aid = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"E2E {slug}", slug))[0][0]
    yield db, aid
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (aid,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))
    # PAS de `db.close()` : `get_db_connection()` rend une connexion MISE EN CACHE et
    # partagée. La fermer ici casse le test suivant, qui la reçoit déjà fermée — vu à
    # la première exécution, en erreur de démontage et pas en échec.


def _pending(db, aid, links):
    db.execute_query("UPDATE saas_artists SET pending_profile_links = %s WHERE id = %s",
                     (json.dumps(links), aid))


def test_a_spotify_link_becomes_a_credential_without_a_network_call(tenant):
    """L'URL Spotify se convertit HORS LIGNE — aucune dépendance réseau."""
    from src.dashboard.views.credentials._from_signup import materialise

    db, aid = tenant
    _pending(db, aid, {"spotify": "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV"})
    assert materialise(db, aid) == ["spotify"]

    rows = db.fetch_query(
        "SELECT extra_config FROM artist_credentials "
        "WHERE artist_id = %s AND platform = 'spotify'", (aid,))
    extra = rows[0][0]
    extra = json.loads(extra) if isinstance(extra, str) else extra
    assert extra["spotify_artist_id"] == "4qG1qjeHfkASTdyRGbLWbV"


def test_the_pending_field_is_cleared_and_a_second_pass_writes_nothing(tenant):
    """Idempotence : la vérification peut être rejouée sans dupliquer ni écraser."""
    from src.dashboard.views.credentials._from_signup import materialise

    db, aid = tenant
    _pending(db, aid, {"spotify": "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV"})
    materialise(db, aid)

    assert db.fetch_query(
        "SELECT pending_profile_links FROM saas_artists WHERE id = %s", (aid,)
    )[0][0] is None, "le champ d'attente survit : un rejeu réécrirait"
    assert materialise(db, aid) == []


def test_an_unusable_link_never_loses_the_usable_one(tenant):
    """Chaque plateforme est isolée — un lien illisible n'en fait pas perdre trois.

    Le `@handle` YouTube en est le cas réel : il demande un appel de résolution qui
    peut échouer, et il est donc laissé à l'artiste plutôt que deviné.
    """
    from src.dashboard.views.credentials._from_signup import materialise

    db, aid = tenant
    # La résolution SoundCloud est SIMULÉE : ce test porte sur l'isolement entre
    # plateformes, pas sur le réseau. La frontière HTTP de `conftest` refuse
    # d'ailleurs les appels sortants réels — elle a attrapé la première version de
    # ce test, et elle avait raison : il dépensait du quota d'API pour une question
    # qui ne s'y joue pas.
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "src.utils.platform_identity_resolver.soundcloud_user_id_from_url",
        lambda url: (_ for _ in ()).throw(ValueError("lien illisible")))
    _pending(db, aid, {
        "spotify": "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV",
        "youtube": "https://youtube.com/@une-chaine-quelconque",
        "soundcloud": "pas une url du tout",
    })
    try:
        connected = materialise(db, aid)
    finally:
        monkeypatch.undo()
    assert "spotify" in connected
    assert "youtube" not in connected
    assert "soundcloud" not in connected


def test_an_identity_already_taken_by_another_tenant_is_refused(tenant):
    """Le MÊME contrôle que la saisie manuelle.

    Sans lui, deux comptes déclareraient le même profil et liraient les chiffres
    l'un de l'autre — la classe la plus coûteuse de ce dépôt.
    """
    from src.dashboard.views.credentials._from_signup import materialise

    db, aid = tenant
    other = db.fetch_query(
        "SELECT artist_id FROM artist_credentials "
        "WHERE platform = 'spotify' AND extra_config->>'spotify_artist_id' <> '' "
        "  AND artist_id <> %s LIMIT 1", (aid,))
    if not other:
        pytest.skip("aucun locataire ne déclare d'identité Spotify ici")
    taken = db.fetch_query(
        "SELECT extra_config->>'spotify_artist_id' FROM artist_credentials "
        "WHERE artist_id = %s AND platform = 'spotify'", (other[0][0],))[0][0]

    _pending(db, aid, {"spotify": f"https://open.spotify.com/artist/{taken}"})
    assert materialise(db, aid) == [], (
        "une identité déjà prise a été écrite pour un second locataire")


def test_the_signup_form_offers_the_three_links():
    """Les champs existent, et restent FACULTATIFS."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/views/register.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    keys = {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for key in ("register.link_spotify", "register.link_soundcloud",
                "register.link_youtube"):
        assert key in keys, f"le champ {key} a disparu du formulaire d'inscription"

    # Facultatifs : le libellé par défaut ne porte pas le `*` des champs requis.
    # Lu dans l'ARBRE — le second argument de chaque `t(...)` — et non par une
    # recherche de chaîne dans le source : le cliquet du dépôt refuse une assertion
    # qui compare une chaîne au texte d'un fichier, et il a raison ici comme ailleurs.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "t"
                and len(node.args) == 2
                and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value).startswith("register.link_")
                and isinstance(node.args[1], ast.Constant)):
            assert not str(node.args[1].value).rstrip().endswith("*"), (
                f"{node.args[0].value} est devenu obligatoire : ces liens sont un "
                "raccourci, pas une condition pour s'inscrire")


def test_a_connected_platform_is_marked_differently_in_the_tab_bar():
    """« Ceux qui sont validés, on les propose différemment. »

    Vérifié SUR LE RENDU. La première version lisait l'AST et cherchait « une
    expression conditionnelle contenant une f-string » — vrai de plusieurs autres
    endroits du routeur, donc verte quand on retirait la marque. La portée du garde
    était le défaut.
    """
    import os

    from streamlit.testing.v1 import AppTest

    db = _db()
    marked = db.fetch_query(
        "SELECT artist_id FROM artist_credentials "
        "WHERE artist_id IN (SELECT id FROM saas_artists WHERE active) LIMIT 1")
    if not marked:
        pytest.skip("aucun locataire ne porte de credentials ici")
    artist_id = marked[0][0]

    at = AppTest.from_string(f"""
import sys
sys.path.insert(0, {os.getcwd()!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = {artist_id}
st.session_state["email"] = "a@t"
st.session_state["name"] = "a@t"
st.session_state["authenticated"] = True
from src.dashboard.views.credentials import show
show()
""")
    at.run(timeout=200)
    assert not at.exception, at.exception

    def flat(node, out=None):
        out = [] if out is None else out
        kids = getattr(node, "children", None)
        for child in (kids.values() if isinstance(kids, dict) else (kids or [])):
            out.append(child)
            flat(child, out)
        return out

    bars = [e for e in flat(at.main) if type(e).__name__ == "ButtonGroup"]
    assert bars, "la barre d'onglets a disparu"
    labels = str(bars[0])
    assert "✓" in labels, (
        "aucun onglet n'est marqué alors que ce locataire a des credentials : "
        "l'artiste ne distingue plus ce qui reste à configurer de ce qui est fait")
    # Et la marque ne doit pas être partout, sinon elle ne distingue rien.
    assert labels.count("✓") < labels.count("content:"), (
        "tous les onglets portent la marque — elle ne sépare plus rien")

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

    Le `@handle` YouTube en est le cas réel : il demande un appel de résolution, qui
    peut ne rien trouver. Depuis le 2026-09-05 la matérialisation le RÉSOUT au lieu
    de le jeter — un artiste qui colle l'adresse de sa chaîne à l'inscription voyait
    son lien disparaître en silence, alors que c'est exactement la forme que le champ
    lui propose.
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
    # Et la résolution YouTube pour la même raison : elle appelle l'API de Google.
    # La frontière HTTP l'a attrapée le 2026-09-05, sur ce test précis — 16
    # connexions sortantes réelles vers googleapis. Ici, la chaîne est introuvable.
    monkeypatch.setattr(
        "src.dashboard.views.credentials._platform_youtube.resolve_channel_id",
        lambda given, api_key: (None, None, "chaîne introuvable"))
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
    assert "🟢" in labels, (
        "aucun onglet n'est en VERT alors que ce locataire a des credentials : "
        "l'artiste ne distingue plus ce qui reste à configurer de ce qui est fait")
    # Et la marque ne doit pas être partout, sinon elle ne distingue rien.
    assert labels.count("🟢") < labels.count("content:"), (
        "tous les onglets portent la marque — elle ne sépare plus rien")


# ── La chaîne ENTIÈRE, pas seulement son maillon central ─────────────────────
# Les tests ci-dessus appellent `materialise` directement. Ils ne disent rien de deux
# maillons : le formulaire d'inscription range-t-il vraiment les liens, et la
# vérification de l'e-mail appelle-t-elle vraiment la matérialisation ? Une fonction
# correcte que personne n'atteint reste une fonction correcte que personne n'atteint.

def test_the_signup_form_stores_what_it_collected(tenant):
    """Maillon 1 : le formulaire → la colonne d'attente."""
    from src.dashboard.views.register import _store_pending_links

    db, aid = tenant
    _store_pending_links(db, aid, {
        "spotify": "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV",
        "soundcloud": "  ",          # vide après strip : ne doit pas être rangé
    })
    stored = db.fetch_query(
        "SELECT pending_profile_links FROM saas_artists WHERE id = %s", (aid,))[0][0]
    stored = json.loads(stored) if isinstance(stored, str) else stored
    assert stored == {"spotify": "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV"}


def test_the_signup_flow_is_wired_to_the_storage():
    """Le formulaire APPELLE-t-il ce rangement ?

    `test_the_signup_form_stores_what_it_collected` appelle `_store_pending_links`
    directement : il reste vert si plus personne ne l'appelle. Vu sur une mutation —
    remplacer l'appel dans `show()` par une expression morte n'a rien fait rougir.
    Une fonction correcte que personne n'atteint reste une fonction correcte que
    personne n'atteint.
    """
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/views/register.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "show"), None)
    assert fn is not None, "`show()` a disparu de la page d'inscription"

    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "_store_pending_links" in called, (
        "l'inscription ne range plus les liens saisis : les champs existent, "
        "l'artiste les remplit, et rien n'en sort")
    assert "_create_artist_and_user" in called, (
        "la liste des appels de `show()` a changé de forme — ce test ne mesure "
        "peut-être plus ce qu'il croit")


def test_email_verification_is_wired_to_the_materialisation():
    """Maillon 2, lu dans l'ARBRE de `_verify_email`.

    Pas au rendu : rejouer une vérification demande de fabriquer un utilisateur, un
    jeton, et d'empêcher l'envoi d'un VRAI e-mail de bienvenue — trois vrais e-mails
    sont déjà partis d'une suite de tests le 2026-08-23. La preuve de bout en bout a
    été faite une fois, à la main, SMTP bloqué ; ce qui doit être gardé en continu est
    que le fil ne soit pas coupé.
    """
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/app.py").read_text(encoding="utf-8")
    fn = next((n for n in ast.walk(ast.parse(src))
               if isinstance(n, ast.FunctionDef) and n.name == "_verify_email"), None)
    assert fn is not None, "`_verify_email` a disparu"

    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "materialise" in called, (
        "la vérification de l'e-mail n'appelle plus la matérialisation : les liens "
        "resteraient dans leur colonne d'attente pour toujours")
    assert "_artist_id_of" in called, (
        "le locataire n'est plus résolu depuis l'utilisateur — écrire sous un repli "
        "serait la fuite de locataire du 2026-08-20, par la porte d'entrée")


def test_the_links_are_plain_fields_with_no_wrapper_and_no_explanation():
    """Un bloc, à plat. Demandé le 2026-09-05 : « le plus simple possible ».

    Le dépliant et ses deux phrases d'explication ont vécu une heure. Ce qui les
    remplace n'est pas un texte plus court : c'est aucun texte — le libellé de chaque
    champ dit ce qu'on attend, et l'absence d'astérisque dit qu'il est facultatif.
    """
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/views/register.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Aucun `st.expander` dans le formulaire d'inscription.
    expanders = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", "") == "expander"]
    assert not expanders, (
        "un dépliant est revenu sur la page d'inscription : il cache ce qu'il "
        "contient, et un bloc facultatif caché n'est pas rempli")

    # Et plus aucune clé de titre ou d'explication pour ce bloc.
    keys = {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for gone in ("register.links_expander", "register.links_help"):
        assert gone not in keys, f"{gone} est revenue — c'est du texte en plus"


@pytest.mark.skipif(not _db(), reason="rendu : needs the DB for the shared imports")
def test_the_form_renders_flat_with_the_marketing_box_ticked():
    """Ce que l'artiste voit, pas ce que le source dit.

    Deux affirmations en une : les trois liens sont des champs ORDINAIRES (aucun
    conteneur ne les cache), et la case marketing arrive cochée — décision produit
    du 2026-09-05, contraire à l'exigence RGPD d'un acte positif (CJUE *Planet49*,
    C-673/17). Épinglée ici pour qu'un changement d'arbitrage soit un changement
    VISIBLE, et pas une dérive.
    """
    import os

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(f"""
import sys
sys.path.insert(0, {os.getcwd()!r})
from src.dashboard.views.register import show
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

    els = flat(at.main)
    labels = [str(getattr(e, "label", "") or "") for e in els]

    assert not [e for e in els if type(e).__name__ == "Expander"], (
        "un dépliant est rendu sur la page d'inscription")
    for needle in ("Spotify Artist", "SoundCloud", "YouTube"):
        assert any(needle in x for x in labels), f"le champ {needle} n'est plus rendu"
    # Facultatifs : pas d'astérisque, contrairement aux quatre champs requis.
    for x in labels:
        if "Lien de t" in x:
            assert not x.rstrip().endswith("*"), f"{x!r} est devenu obligatoire"

    boxes = [e for e in els if type(e).__name__ == "Checkbox"]
    assert len(boxes) >= 2, "les deux cases de consentement ne sont plus rendues"
    marketing = next((b for b in boxes if "marketing" in str(b.label).lower()), None)
    assert marketing is not None, "la case marketing a disparu"
    assert marketing.value is True, (
        "la case marketing n'est plus pré-cochée — décision produit du 2026-09-05")
    terms = next((b for b in boxes if "confidentialité" in str(b.label).lower()), None)
    assert terms is not None and terms.value is False, (
        "la case des CONDITIONS est pré-cochée : celle-là doit rester un acte "
        "positif, c'est elle qui autorise la création du compte")


@pytest.mark.skipif(not _db(), reason="rendu : needs the DB for the shared imports")
def test_nothing_stands_between_the_title_and_the_first_field():
    """Retiré le 2026-09-05 : « ça ne sert à rien ».

    Trois éléments vivaient entre le titre et le formulaire — un sous-titre
    (« Rejoignez streaMLytics. Plan gratuit… »), un compteur « Live Activity » et une
    règle horizontale. Aucun n'aide quelqu'un qui vient de cliquer « Créer un
    compte » : il sait où il est, et un compteur qui annonce cinq inscrits dit
    surtout que personne n'est là.

    Le compteur reste calculé et affiché AILLEURS (barre latérale). Ce test garde sa
    place sur ce chemin, pas son existence.
    """
    import os

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(f"""
import sys
sys.path.insert(0, {os.getcwd()!r})
from src.dashboard.views.register import show
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

    els = flat(at.main)
    kinds = [type(e).__name__ for e in els]
    texts = [str(getattr(e, "label", "") or getattr(e, "value", "")
                 or getattr(e, "body", "") or "") for e in els]
    joined = "\n".join(texts)

    assert "Live Activity" not in joined
    assert "Rejoignez" not in joined
    assert "utilisent streaMLytics" not in joined

    first_field = next(i for i, k in enumerate(kinds) if k == "TextInput")
    between = [k for k in kinds[:first_field]
               if k not in ("SpecialBlock", "Block", "Column", "Title", "Radio")]
    assert not between, (
        f"des éléments séparent encore le titre du premier champ : {between}")
    # Et surtout aucune règle horizontale sur ce chemin.
    assert not [e for e in els[:first_field]
                if type(e).__name__ == "Markdown"
                and str(getattr(e, "value", "")).strip() == "---"], (
        "la règle horizontale est revenue entre le titre et la saisie")

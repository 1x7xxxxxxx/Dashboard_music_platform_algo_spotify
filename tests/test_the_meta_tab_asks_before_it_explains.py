"""L'onglet Meta demande avant d'expliquer, et demande la même chose que les autres.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres, ast
Depends on: views/credentials/_registry.py, _render.py, content/credential_guides*.py
Persists in: —

Quatre demandes du 2026-09-05, sur le seul onglet qui ne suivait pas la forme des
autres :

1. **« Saisir tes identifiants » en premier.** Un assistant « 🔎 Trouver mon numéro de
   compte publicitaire » occupait le haut de l'onglet, avec ses deux consignes ① ② —
   du texte avant la seule chose à faire. Supprimé, avec sa fonction et ses sept clés
   de traduction : `render_ad_account_picker` n'avait plus d'appelant, et une couche
   débranchée pourrit.
2. **Un lien, comme Spotify et SoundCloud.** Le champ demandait « Ad Account ID (act_…
   ou numérique) » là où les deux autres onglets demandent un lien. Le geste est
   « copier la barre d'adresse », pas « sélectionner la bonne sous-chaîne ».
3. **Pas de légende « ex. … »** sous ces champs : elle répétait mot pour mot le texte
   fantôme affiché DANS le champ.
4. **Trois actions, pas sept étapes.** Ce qui reste est ce que personne ne peut
   deviner ni faire à la place de l'artiste — dont le PARTAGE du compte, l'étape qui a
   bloqué la session du 2026-06-19.

Le rendu est vérifié À L'ÉCRAN : une page peut renvoyer les bons objets et n'en
afficher aucun (`verdict-exists-but-not-when-it-is-needed`, 2026-09-04).
"""
import ast
import os
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
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


# ── Ce qui ne demande pas la base ────────────────────────────────────────────

def test_the_meta_field_asks_for_a_link_like_the_other_tabs():
    from src.dashboard.views.credentials._registry import PLATFORMS

    def _first(key):
        return PLATFORMS[key]["fields"][0]

    meta = _first("meta")
    assert "act_" not in meta["label"], (
        "le champ Meta redemande un identifiant à découper au lieu d'un lien")
    # La forme est la même que celle des deux onglets qui la portaient déjà.
    for other in ("spotify", "soundcloud"):
        label = _first(other)["label"].lower()
        assert ("lien" in label) or ("url" in label), (
            f"{other} n'est plus la référence de forme — ce test compare à lui")
    assert ("lien" in meta["label"].lower()) or ("url" in meta["label"].lower())
    # …et son texte fantôme est bien une URL, pas un numéro nu.
    assert meta["example"].startswith("http")


def test_no_example_caption_repeats_the_placeholder_on_the_meta_fields():
    from src.dashboard.views.credentials._registry import PLATFORMS

    for field in PLATFORMS["meta"]["fields"]:
        if field.get("example"):
            assert field.get("show_example") is False, (
                f"{field['key']} réaffiche « ex. … » sous un champ qui montre déjà "
                "la même valeur en texte fantôme")


def test_the_render_honours_show_example():
    """Le drapeau doit être LU — sinon il documente une intention sans effet."""
    render = (_ROOT / "src/dashboard/views/credentials/_render.py").read_text(
        encoding="utf-8")
    tree = ast.parse(render)
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "get"
             and n.args and isinstance(n.args[0], ast.Constant)
             and n.args[0].value == "show_example"]
    assert reads, "`show_example` n'est plus lu : la légende reviendra sans prévenir"


def test_the_ad_account_picker_is_gone_with_everything_that_named_it():
    """Supprimée, pas seulement débranchée — et ses traductions avec elle."""
    from src.dashboard.utils.i18n_catalog import credentials as en

    meta_src = (_ROOT / "src/dashboard/views/credentials/_platform_meta.py").read_text(
        encoding="utf-8")
    names = {n.name for n in ast.walk(ast.parse(meta_src))
             if isinstance(n, ast.FunctionDef)}
    assert "render_ad_account_picker" not in names

    orphans = [k for k in en.EN if ".picker_" in k]
    assert not orphans, f"traductions sans écran : {orphans}"


@pytest.mark.parametrize("module,attr", [
    ("src.dashboard.content.credential_guides", "CREDENTIAL_GUIDES"),
    ("src.dashboard.content.credential_guides_en", "CREDENTIAL_GUIDES_EN"),
])
def test_the_meta_guide_is_two_actions_without_an_intro(module, attr):
    import importlib

    guides = getattr(importlib.import_module(module), attr)
    meta = next(g for g in guides if g.key == "meta")

    assert meta.intro is None, "l'intro décrit l'architecture, pas un geste"
    # DEUX depuis le 2026-09-05 (soir) : la troisième était Instagram, parti avec son
    # propre onglet. Le nombre n'est pas un objectif — c'est le compte de ce qu'on ne
    # peut pas deviner : où copier, et le partage que nous ne pouvons pas faire.
    assert len(meta.steps) == 2, (
        f"{len(meta.steps)} étapes : le guide a regrossi — chaque étape doit être "
        "une action que l'artiste est seul à pouvoir faire")
    joined = " ".join(s.text for s in meta.steps)
    # L'étape du PARTAGE reste : c'est elle qui a bloqué la session du 2026-06-19,
    # et personne ne peut la faire à la place de l'artiste.
    assert "ETL_DASHBOARD_SPOTIFY" in joined or "{" in joined or "Analy" in joined, (
        "l'étape de partage du compte publicitaire a disparu du guide")


# ── Ce que la page montre vraiment ───────────────────────────────────────────

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = 18
st.session_state["email"] = "a@t"
st.session_state["name"] = "a@t"
st.session_state["authenticated"] = True
st.session_state["_creds_tab"] = "meta"
from src.dashboard.views.credentials import show
show()
"""


@pytest.mark.skipif(not _db_ready(), reason=f"needs the DB on {_DB_HOST}:{_DB_PORT}")
def test_the_entry_section_is_the_first_thing_on_the_meta_tab():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd()))
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
    def _text(el) -> str:
        """Le texte d'un élément, sans jamais lever.

        `.value` est une PROPRIÉTÉ sur certains éléments : sur un `link_button`, qui
        n'a pas d'état, elle lève `KeyError`. Un `getattr(e, "value", "")` ne protège
        pas de ça — le défaut par défaut ne couvre que l'absence d'attribut, pas une
        propriété qui explose.
        """
        for attr in ("value", "label", "body"):
            try:
                got = getattr(el, attr, "")
            except Exception:  # noqa: BLE001
                continue
            if got:
                return str(got)
        return ""

    texts = [_text(e) for e in els]
    joined = "\n".join(texts)

    assert "Trouver mon numéro" not in joined, "l'assistant est de retour"
    assert "ex. act_" not in joined
    assert "ex. 17841400000000000" not in joined

    idx_entry = next(i for i, x in enumerate(texts) if "Saisir tes identifiants" in x)

    # Les glyphes ① ② étaient ceux de l'assistant supprimé, et ce test les
    # interdisait PARTOUT. Depuis le 2026-09-05 (soir), l'étape de partage du guide
    # les utilise légitimement pour numéroter quatre clics — la question n'a jamais
    # été « ce glyphe existe-t-il ? » mais « quelque chose est-il revenu AU-DESSUS du
    # formulaire ? ». Le prédicat suit donc la question, et pas le symptôme.
    assert not [x for x in texts[:idx_entry] if "①" in x or "②" in x], (
        "des consignes numérotées précèdent la saisie : c'est la forme de "
        "l'assistant qui a été retiré")
    idx_guide = next((i for i, x in enumerate(texts)
                      if "obtenir les identifiants" in x), len(texts))
    assert idx_entry < idx_guide, "le guide passe devant le formulaire"

    # Rien d'autre que la barre d'onglets entre le titre et la saisie.
    kinds_before = [type(e).__name__ for e in els[:idx_entry]]
    assert "ButtonGroup" in kinds_before
    for noisy in ("TextInput", "Expander"):
        assert noisy not in kinds_before, (
            f"un {noisy} précède « Saisir tes identifiants »")


# ── Ce que le 2026-09-05 (soir) a ajouté ─────────────────────────────────────

def test_the_agency_field_left_the_tab_and_instagram_is_not_optional():
    """Le champ d'agence n'est plus ici du tout — il est sur 📣 Meta Ads.

    Il a été replié dans cet onglet quelques heures, puis DÉPLACÉ : « ça ne doit pas
    être dans l'onglet credential ». Credentials répond à « comment te connecter » ;
    un compte d'agence est une déclaration de périmètre. Ce test garde le
    déplacement, pas le repli.
    """
    from src.dashboard.views.credentials._registry import PLATFORMS

    by_key = {f["key"]: f for f in PLATFORMS["meta"]["fields"]}
    assert "extra_account_ids" not in by_key, (
        "le champ d'agence est revenu dans l'onglet Credentials")
    # Instagram a QUITTÉ cet onglet le 2026-09-05 (soir) : il a le sien. On vérifie
    # donc son absence ici, et son libellé se garde dans le fichier de la séparation.
    assert "ig_user_id" not in by_key, (
        "Instagram est revenu dans l'onglet Meta")


def test_no_collapsed_field_remains_on_the_meta_tab():
    """Le mécanisme `collapsed` reste, son unique usage est parti.

    `_render.py` sait toujours replier un champ ; plus rien ne l'utilise ici. Ce test
    dit l'état voulu de l'ONGLET, pas la disparition du mécanisme : le jour où un
    champ mérite d'être replié, ce sera une décision, pas un héritage.
    """
    from src.dashboard.views.credentials._registry import PLATFORMS

    collapsed = [f["key"] for f in PLATFORMS["meta"]["fields"] if f.get("collapsed")]
    assert not collapsed, (
        f"des champs sont repliés dans l'onglet Meta : {collapsed}. Un champ replié "
        "sur le chemin obligatoire demande une décision à chaque visite")


def test_the_sharing_step_names_a_number_the_artist_can_paste():
    """Un artiste ne peut PAS voir notre app dans son Business Manager.

    Chez Meta, une application n'apparaît que dans le Business Manager qui la
    possède ; la nôtre appartient au nôtre. Le guide disait « cherche
    ETL_DASHBOARD_SPOTIFY dans ta liste d'applications » — une instruction que
    personne ne pouvait suivre, et qu'aucun test ne remettait en cause parce que le
    garde d'alors exigeait justement ce nom.

    Le geste qui marche est l'inverse : l'artiste attribue SON compte à NOTRE
    Business, en collant un numéro que nous lui donnons.
    """
    import importlib

    for module, attr in (
        ("src.dashboard.content.credential_guides", "CREDENTIAL_GUIDES"),
        ("src.dashboard.content.credential_guides_en", "CREDENTIAL_GUIDES_EN"),
    ):
        guides = getattr(importlib.import_module(module), attr)
        meta = next(g for g in guides if g.key == "meta")
        joined = " ".join(s.text for s in meta.steps)
        assert "Attribuer un partenaire" in joined or "Assign partner" in joined, (
            f"{module}: l'étape de partage ne nomme plus le geste faisable")
        assert "ETL_DASHBOARD_SPOTIFY" not in joined, (
            f"{module}: le guide renvoie chercher notre app dans le Business Manager "
            "de l'artiste, où elle ne peut pas apparaître")


def test_every_step_of_the_meta_guide_carries_a_clickable_portal():
    """Chaque étape commence par le lien qu'elle fait ouvrir — demandé le 2026-09-05."""
    import importlib

    guides = importlib.import_module(
        "src.dashboard.content.credential_guides").CREDENTIAL_GUIDES
    meta = next(g for g in guides if g.key == "meta")
    for i, step in enumerate(meta.steps, 1):
        assert "](http" in step.text, (
            f"étape {i} sans lien cliquable : l'artiste doit chercher la page "
            "lui-même")

"""📸 Instagram est un onglet à part, et il partage la ligne de 📱 Meta Ads.

Type: Test
Uses: live Postgres
Depends on: views/credentials/_registry.py, _render.py, _core.py, tenant_identity
Persists in: un locataire jetable

Instagram était un CHAMP de l'onglet Meta parce que son identifiant ne se trouvait que
dans Business Manager : les deux plateformes partageaient donc le même parcours pénible.
`business_discovery` ayant supprimé ce détour (2026-09-05), Instagram est devenu une
saisie de dix secondes — la garder derrière Meta forçait à lire une étape de partage de
compte publicitaire pour brancher un profil public.

**L'onglet est séparé, le stockage ne l'est pas.** `ig_user_id` reste dans la ligne
`meta`, et c'est là qu'est le risque : `_save_credentials` REMPLACE `extra_config`.
Enregistrer un onglet effacerait donc l'autre. Ce fichier garde la fusion.
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


def test_instagram_is_its_own_tab_and_meta_no_longer_carries_it():
    from src.dashboard.views.credentials._registry import PLATFORMS

    assert "instagram" in PLATFORMS, "l'onglet Instagram a disparu"
    assert [f["key"] for f in PLATFORMS["instagram"]["fields"]] == ["ig_user_id"]
    meta_keys = {f["key"] for f in PLATFORMS["meta"]["fields"]}
    assert "ig_user_id" not in meta_keys, (
        "Instagram est revenu dans l'onglet Meta : brancher un profil public "
        "redemanderait de lire l'étape de partage d'un compte publicitaire")


def test_each_tab_triggers_only_its_own_collection():
    """Le DAG suit l'ONGLET, pas la ligne.

    `dags_for_save` matchait sur `spec.storage == tab_key`. Avec deux onglets sur la
    ligne `meta`, enregistrer Instagram n'aurait déclenché aucun DAG — ou celui de
    Meta Ads, ce qui est pire : une collecte publicitaire lancée par une saisie qui
    ne la concerne pas.
    """
    from src.dashboard.views.credentials._core import dags_for_save

    assert dags_for_save("instagram", {"ig_user_id": "178"}) == ["instagram_daily"]
    assert dags_for_save("meta", {"account_id": "act_1"}) == ["meta_ads_api_daily"]
    # Un champ vide ne déclenche rien : une collecte sans identité ne collecte rien.
    assert dags_for_save("instagram", {}) == []
    assert dags_for_save("meta", {}) == []


@pytest.fixture()
def tenant():
    db = _db()
    slug = f"e2e-split-{uuid.uuid4().hex[:8]}"
    aid = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier, active) "
        "VALUES (%s, %s, 'free', TRUE) RETURNING id", (f"E2E {slug}", slug))[0][0]
    yield db, aid
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (aid,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (aid,))


def _save_tab(db, artist_id: int, tab: str, extra: dict) -> None:
    """La fusion de `_handle_save`, rejouée sans Streamlit."""
    from src.dashboard.views.credentials._core import (
        DERIVED_KEYS,
        _save_credentials,
        merge_into_row,
    )
    from src.dashboard.views.credentials._registry import PLATFORMS
    from src.dashboard.views.credentials._render import _saved_row_extra
    from src.utils.tenant_identity import storage_platform

    # `merge_into_row` est LA fonction de production, pas une copie. La première
    # version de ce fichier réimplémentait la fusion, et deux mutations sont restées
    # vertes : le test validait son propre calcul. Une seule implémentation.
    row = storage_platform(tab)
    owned = {f["key"] for f in PLATFORMS[tab]["fields"]} | DERIVED_KEYS.get(tab, set())
    merged = merge_into_row(_saved_row_extra(db, artist_id, row), extra, owned)
    _save_credentials(db, artist_id, row, "", merged)


def test_saving_one_tab_never_erases_the_other(tenant):
    """Le défaut que la séparation crée, et que la fusion ferme."""
    from src.dashboard.views.credentials._render import _saved_row_extra

    db, aid = tenant
    _save_tab(db, aid, "meta", {"account_id": "act_777",
                                "account_ids": ["act_777"]})
    _save_tab(db, aid, "instagram", {"ig_user_id": "17841400196310703"})

    row = _saved_row_extra(db, aid, "meta")
    assert row.get("account_id") == "act_777", (
        "enregistrer Instagram a effacé le compte publicitaire")
    assert row.get("ig_user_id") == "17841400196310703"

    # Et dans l'autre sens.
    _save_tab(db, aid, "meta", {"account_id": "act_555",
                                "account_ids": ["act_555"]})
    row = _saved_row_extra(db, aid, "meta")
    assert row.get("ig_user_id") == "17841400196310703", (
        "réenregistrer Meta a effacé Instagram")
    assert row.get("account_id") == "act_555", "la mise à jour de Meta n'a pas pris"
    assert row.get("account_ids") == ["act_555"], (
        "les comptes dérivés ne suivent pas : un compte retiré resterait pour "
        "toujours")


def test_a_cleared_field_is_really_cleared(tenant):
    """La fusion ne doit pas rendre la suppression impossible.

    C'est le risque symétrique : à trop préserver, on garde une valeur que l'artiste
    vient d'effacer. Les clés que l'onglet POSSÈDE sont retirées avant la fusion,
    donc vider un champ le vide vraiment.
    """
    from src.dashboard.views.credentials._render import _saved_row_extra

    db, aid = tenant
    _save_tab(db, aid, "instagram", {"ig_user_id": "17841400196310703"})
    _save_tab(db, aid, "instagram", {})          # l'artiste efface son profil

    row = _saved_row_extra(db, aid, "meta")
    assert "ig_user_id" not in row, (
        "un champ vidé par l'artiste survit à l'enregistrement")


def test_the_tab_reads_the_row_and_not_its_own_name(tenant):
    """Sinon Instagram afficherait un formulaire vide sur une valeur existante."""
    from src.dashboard.views.credentials._core import _load_credentials
    from src.dashboard.views.credentials.router import _storage_for_tab

    db, aid = tenant
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'meta', %s)", (aid, json.dumps({"ig_user_id": "178414"})))

    existing = _load_credentials(db, aid)
    assert _storage_for_tab("instagram") == "meta"
    assert existing.get(_storage_for_tab("instagram")), (
        "l'onglet Instagram ne retrouve pas la ligne qui porte sa valeur")


def test_a_derived_key_is_owned_by_its_tab_and_does_not_go_stale(tenant):
    """`account_ids` appartient à l'onglet Meta, même s'il n'est pas un champ.

    Sans cela, la fusion le croirait à l'AUTRE onglet et le garderait : un compte
    publicitaire retiré resterait collecté pour toujours, et le seul symptôme serait
    des chiffres qui ne correspondent à aucune campagne visible.

    Le cas qui le révèle est celui où l'onglet Meta écrit SANS `account_ids` — c'est
    la seule façon de distinguer « possédé donc effacé » de « réécrit par-dessus ».
    """
    from src.dashboard.views.credentials._render import _saved_row_extra

    db, aid = tenant
    _save_tab(db, aid, "meta", {"account_id": "act_777",
                                "account_ids": ["act_777", "act_666"]})
    _save_tab(db, aid, "meta", {"account_id": "act_777"})   # plus d'agence

    row = _saved_row_extra(db, aid, "meta")
    assert "account_ids" not in row, (
        "`account_ids` a survécu à un enregistrement qui ne le portait plus : la "
        "clé dérivée n'est pas possédée par son onglet, un compte retiré resterait")


def test_handle_save_actually_calls_the_merge():
    """Le BRANCHEMENT, pas la fonction.

    Les tests ci-dessus appellent `merge_into_row` directement : ils restent verts
    si `_handle_save` cesse de l'appeler — c'est-à-dire au moment précis où un onglet
    se remettrait à écraser l'autre. C'est la quatrième fois de la journée que ce
    trou apparaît ; il est fermé d'emblée ici.
    """
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/dashboard/views/credentials/_render.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_handle_save")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "merge_into_row" in called, (
        "`_handle_save` ne fusionne plus : enregistrer un onglet effacerait l'autre")
    assert "_saved_row_extra" in called, (
        "la fusion ne relit plus la ligne en base — elle n'aurait rien à fusionner")

    # Et le résultat doit être ÉCRIT : une fusion calculée puis jetée ne garde rien.
    assigned = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                and any(getattr(tgt, "id", "") == "extra" for tgt in n.targets)
                and isinstance(n.value, ast.Call)
                and getattr(n.value.func, "id", "") == "merge_into_row"]
    assert assigned, "le résultat de la fusion n'est pas réaffecté à `extra`"

    # Et la branche doit être ATTEIGNABLE. `if False:` laisse l'appel dans l'arbre :
    # les assertions ci-dessus restaient vertes sur cette mutation. La condition doit
    # nommer `SHARED_ROWS` — c'est elle qui décide qu'une ligne se fusionne.
    guarded = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.If)
        and any(getattr(x, "id", "") == "SHARED_ROWS" for x in ast.walk(n.test))
    ]
    assert guarded, (
        "la fusion n'est plus conditionnée par `SHARED_ROWS` : soit elle ne tourne "
        "jamais, soit elle tourne partout — et dans les deux cas elle ne dit plus "
        "ce qu'elle prétend dire")

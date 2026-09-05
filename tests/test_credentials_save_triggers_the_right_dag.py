"""Guard — saving an identity must start ITS collection, not a neighbour's.

Error class `map-key-unreachable-by-construction`.

`_PLATFORM_DAG_MAP` was keyed on the form TAB and carried an `'instagram'` entry.
`_handle_save` is only ever called with a key from `_registry.PLATFORMS`, which has
four tabs — `ig_user_id` is a FIELD of the meta tab. So the `'instagram'` entry could
never be selected: saving an Instagram Business Account ID triggered
`meta_ads_api_daily` and never `instagram_daily`. The artist connected Instagram,
waited for the "~2 min" the toast promises, and no first pull ever ran.

The file read as though the feature existed. That is the whole class: a config entry
no caller can reach declares a behaviour that never happens.
"""
from __future__ import annotations

from src.dashboard.views.credentials._core import (
    _IDENTITY_DAG_MAP,
    PLATFORM_TO_DAGS,
    dags_for_save,
)
from src.dashboard.views.credentials._registry import PLATFORMS
from src.utils.tenant_identity import PLATFORM_IDENTITIES


# RÉANCRÉ le 2026-09-05 (soir) : Instagram a son propre onglet depuis que
# `business_discovery` a supprimé le détour par Business Manager. Le stockage, lui,
# n'a pas bougé — `ig_user_id` reste dans la ligne `meta`. La question du fichier est
# inchangée : une saisie démarre-t-elle SA collecte, et une seule ?

def test_an_instagram_only_save_starts_instagram_not_meta() -> None:
    """Le champ décide, pas l'onglet.

    Les deux identités partagent l'onglet « 📱 Meta Ads / Insta » — elles ont eu deux
    onglets pendant une heure le 2026-09-05, refusionnés parce que leur configuration
    est la même. Ce qui compte n'a pas bougé : une identité laissée vide ne déclenche
    aucune collecte.
    """
    assert dags_for_save("instagram", {"ig_user_id": "17841400000000000"}) == [
        "instagram_daily"]
    # Et le symétrique, qui est la moitié « not_meta » du nom : l'identité Instagram
    # vit dans la ligne `meta`, donc elle se retrouve dans le blob enregistré depuis
    # l'onglet Meta Ads. Elle ne doit RIEN y déclencher — sinon chaque sauvegarde de
    # compte publicitaire relancerait la collecte Instagram.
    assert dags_for_save("meta", {"ig_user_id": "17841400000000000"}) == []


def test_each_tab_starts_only_its_own_collection() -> None:
    """Les deux onglets partagent une ligne ; ils ne partagent pas leurs DAGs.

    Ce test exigeait qu'un enregistrement Meta lance AUSSI `instagram_daily` —
    juste tant que l'onglet portait les deux champs. Depuis la séparation du
    2026-09-05, chacun ne lance que la collecte dont il porte l'identité.
    """
    both = {"account_id": "123456789", "ig_user_id": "17841400000000000"}
    assert set(dags_for_save("meta", both)) == {"meta_ads_api_daily"}
    assert set(dags_for_save("instagram", both)) == {"instagram_daily"}


def test_an_untouched_tab_starts_nothing() -> None:
    """`_handle_save` pops empty values, so a blank save has no identity to collect for."""
    assert dags_for_save("meta", {}) == []
    assert dags_for_save("meta", {"account_id": "   ", "ig_user_id": ""}) == []


def test_single_identity_tabs_are_unchanged() -> None:
    assert dags_for_save("spotify", {"spotify_artist_id": "x"}) == ["spotify_api_daily"]
    assert dags_for_save("youtube", {"channel_id": "UC..."}) == ["youtube_daily"]
    assert dags_for_save("soundcloud", {"user_id": "377065610"}) == ["soundcloud_daily"]


def test_no_dag_map_key_is_unreachable() -> None:
    """The assertion that would have failed on the original `'instagram'` tab key.

    Every entry of the map must be producible by `dags_for_save` from some declared
    tab; an entry nothing can select is a promise the code never keeps.
    """
    # Parcouru par les CHAMPS de l'onglet, comme `dags_for_save` lui-même. C'était
    # `spec.storage == tab`, ce qui liait le DAG à la LIGNE : depuis que deux onglets
    # partagent la ligne `meta`, ce calcul déclarait `instagram_daily` inatteignable
    # alors qu'il est atteint par l'onglet Instagram. Le test mesurait le modèle
    # d'hier, pas la question qu'il pose.
    reachable = set()
    for tab, info in PLATFORMS.items():
        for field in (f["key"] for f in info.get("fields", [])):
            reachable.update(dags_for_save(tab, {field: "probe"}))
    unreachable = set(_IDENTITY_DAG_MAP.values()) - reachable
    assert not unreachable, (
        f"DAG(s) declared but unreachable from any tab: {sorted(unreachable)}"
    )


def test_every_identity_storage_is_a_real_tab() -> None:
    """Une ligne de stockage est toujours ATTEIGNABLE par un onglet.

    Elle n'a plus à porter le même nom que lui : `instagram` est un onglet dont la
    ligne s'appelle `meta`. Ce qui compte est qu'aucune identité ne soit stockée
    quelque part que l'artiste ne puisse jamais atteindre.
    """
    tabs = set(PLATFORMS)
    for logical, spec in PLATFORM_IDENTITIES.items():
        assert spec.storage in tabs, (
            f"{logical} is stored under '{spec.storage}', which is not a credentials tab — "
            f"no artist could ever enter it"
        )


def test_platform_to_dags_is_derived_not_restated() -> None:
    """The KPI badge map must agree with the trigger map — it was a third copy."""
    expected: dict = {}
    for logical, spec in PLATFORM_IDENTITIES.items():
        dag = _IDENTITY_DAG_MAP.get(logical)
        if dag:
            expected.setdefault(spec.storage, []).append(dag)
    assert PLATFORM_TO_DAGS == expected

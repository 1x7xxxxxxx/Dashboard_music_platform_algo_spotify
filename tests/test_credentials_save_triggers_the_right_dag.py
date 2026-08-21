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


def test_an_instagram_only_save_starts_instagram_not_meta() -> None:
    assert dags_for_save("meta", {"ig_user_id": "17841400000000000"}) == ["instagram_daily"]


def test_a_full_meta_save_starts_both_collections() -> None:
    dags = dags_for_save("meta", {"account_id": "123456789", "ig_user_id": "17841400000000000"})
    assert set(dags) == {"meta_ads_api_daily", "instagram_daily"}


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
    reachable = set()
    for tab in PLATFORMS:
        for logical, spec in PLATFORM_IDENTITIES.items():
            if spec.storage == tab:
                reachable.update(dags_for_save(tab, {spec.field: "probe"}))
    unreachable = set(_IDENTITY_DAG_MAP.values()) - reachable
    assert not unreachable, (
        f"DAG(s) declared but unreachable from any tab: {sorted(unreachable)}"
    )


def test_every_identity_storage_is_a_real_tab() -> None:
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

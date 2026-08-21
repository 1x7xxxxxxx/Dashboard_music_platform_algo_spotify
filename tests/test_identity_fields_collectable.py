"""Guard — every identity the pipeline reads must have a form field to enter it.

Error class `identity-read-but-never-collectable`: `instagram_daily` selected
tenants on `creds['meta']['ig_user_id']`, `artist_readiness` read the same key as
the Instagram identity, and `instagram_api_collector` even told the artist to
"verify ig_user_id" in Dashboard → Credentials → Meta — while the Meta form
exposed only `account_id`. No artist could ever connect Instagram; the platform
stayed ⚪ "À connecter" forever with no way out.

The shape of the bug is generic: a consumer reads an identity key that the
credential form never writes. This test pins consumers and form together.
"""
import re
from pathlib import Path

import pytest

from src.dashboard.views.credentials._registry import PLATFORMS
from src.utils import artist_readiness as ar
from src.utils.tenant_identity import PLATFORM_IDENTITIES

_ROOT = Path(__file__).resolve().parents[1]

# readiness platform key → (credential form tab, field key the artist must type).
# DERIVED — this was the SIXTH hand-maintained copy of the same mapping, and the
# copies disagreed: this one had five entries while `_core.UNIQUE_IDENTITY_FIELDS`
# and `tools/create_canary.py` had four. A guard that keeps its own copy of the
# registry can be right while the code is wrong, which is the least useful place
# for a correct map to live.
_IDENTITY_FIELD = {
    logical: (spec.storage, spec.field)
    for logical, spec in PLATFORM_IDENTITIES.items()
}


def _form_field_keys(platform_key: str) -> set[str]:
    return {f["key"] for f in PLATFORMS[platform_key]["fields"]}


@pytest.mark.parametrize("readiness_key", [p["key"] for p in ar._PLATFORMS])
def test_identity_has_a_form_field(readiness_key):
    tab, field = _IDENTITY_FIELD[readiness_key]
    assert field in _form_field_keys(tab), (
        f"artist_readiness treats '{field}' as the {readiness_key} identity, but the "
        f"'{tab}' credential form has no such field — the artist cannot connect it."
    )


def test_map_covers_every_readiness_platform():
    """A new platform in artist_readiness must be added here, not silently skipped."""
    assert {p["key"] for p in ar._PLATFORMS} == set(_IDENTITY_FIELD)


def test_instagram_dag_selects_on_a_collectable_field():
    """The DAG's tenant filter must read a key the form actually writes."""
    dag = (_ROOT / "airflow/dags/instagram_daily.py").read_text(encoding="utf-8")
    keys = set(re.findall(r"\.get\('([a-z_]+)'\)", dag))
    assert "ig_user_id" in keys
    assert "ig_user_id" in _form_field_keys("meta")

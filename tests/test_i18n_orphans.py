"""Guard: no orphan EN translation keys (an EN entry never referenced by a t() call).

Complements test_i18n.test_every_static_t_key_has_en_entry (used→has-EN); this checks
the reverse (has-EN→used) so deleted/renamed features don't leave dead translations.
"""
import pathlib
import re

from src.dashboard.utils import i18n

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

# Keys built dynamically as t(f"<prefix>.{var}") — they can't be matched to a string
# literal, so their EN entries are legitimate even without a literal reference. Keep in
# sync with: grep -rhoE 't\(\s*f"[a-z0-9_.]+\.\{' src/dashboard
# `email.*` keys are consumed in src/utils/verification_email.py via the `_tr()` wrapper
# (and `email.welcome.step{i}` is built in a loop) — neither shape the literal matcher sees.
_DYNAMIC_PREFIXES = (
    "email.",
    "algo.calib.", "algo.divnote.", "algo.label.", "algo.lever.", "algo.model.",
    "algo.regressor.", "algo.suppressed.", "common.month.", "credentials.field.",
    "credentials.guide.",
    # Built as t(f"credentials.resolve.{code}") from ResolutionError.code — the codes
    # themselves are enumerated in `platform_identity_resolver.RESOLUTION_CODES`, and
    # `test_a_link_is_enough_to_identify_a_tenant` checks every one has an entry.
    "credentials.resolve.",
    "export_csv.source.", "export_pdf.period.", "export_pdf.section.",
    "home.dag.", "meta_ads_overview.dim.", "meta_ads_overview.gender.", "meta_breakdowns.dim.",
    "meta_breakdowns.family.", "meta_breakdowns.grain.", "meta_cpr_optimizer.rec.",
    "meta_creatives.metric.", "nav.item.", "nav.section.",
    "onboarding.caveat.", "onboarding.value.",
    # `t(f"onboarding.download_guide_{code}")` — une clé par langue, construite
    # à l'appel : les deux boutons de téléchargement du guide (2026-09-04).
    # `for key, default, image in (…)` : les trois promesses du bloc 1 passent
    # leur clé en VARIABLE, une par figure d'exemple (2026-09-04).
    "onboarding.brief_", "onboarding.download_guide_", "upgrade.page.",
    "upload_csv.platform.",
)

_KEY_RE = re.compile(r'\b_?t(?:ranslate)?\(\s*["\']([a-zA-Z0-9_.]+)["\']')


def _used_keys() -> set[str]:
    used: set[str] = set()
    for p in _SRC.rglob("*.py"):
        if "i18n_catalog" in str(p):
            continue
        used |= set(_KEY_RE.findall(p.read_text(encoding="utf-8")))
    return used


def test_no_orphan_en_keys():
    used = _used_keys()
    en = set(i18n._TR.get("en", {}))
    orphans = sorted(
        k for k in en
        if k not in used and not any(k.startswith(p) for p in _DYNAMIC_PREFIXES)
    )
    assert not orphans, (
        f"{len(orphans)} orphan EN key(s) — no t() reference, remove them or add the "
        f"dynamic prefix to _DYNAMIC_PREFIXES:\n" + "\n".join(orphans)
    )

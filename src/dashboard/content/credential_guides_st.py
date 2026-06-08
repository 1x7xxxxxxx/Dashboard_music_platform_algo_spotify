"""Streamlit renderer for the API-credential guides (see credential_guides).

Type: Sub
Uses: streamlit, src.dashboard.content.credential_guides
Depends on: assets/credential_guide/*.png (optional — missing images degrade)
Persists in: nothing
"""
import pandas as pd
import streamlit as st

from src.dashboard.content.credential_guides import (
    CREDENTIAL_GUIDES,
    CredStep,
    PlatformCred,
    screenshot_path,
)
from src.dashboard.content.csv_guides_st import _display_width


_BY_KEY = {g.key: g for g in CREDENTIAL_GUIDES}


def render_credential_guides() -> None:
    """One expander per platform: steps + screenshots + the values to paste."""
    st.markdown("**Comment obtenir les identifiants de chaque plateforme ?**")
    for guide in CREDENTIAL_GUIDES:
        _render_guide_expander(guide)


def render_credential_guide_for(platform_key: str) -> None:
    """Render the single-platform guide (used inside that platform's tab)."""
    guide = _BY_KEY.get(platform_key)
    if guide is not None:
        _render_guide_expander(guide)


def _render_guide_expander(guide: PlatformCred) -> None:
    with st.expander(f"{guide.icon} {guide.title} — obtenir les identifiants", expanded=False):
        st.markdown(guide.intro)
        st.markdown(f"🔗 Portail : [{guide.portal_url}]({guide.portal_url})")
        for i, step in enumerate(guide.steps, 1):
            _render_step(i, step)
        _render_fields_table(guide)
        if guide.note:
            st.info(guide.note)


def _render_step(num: int, step: CredStep) -> None:
    st.markdown(f"**{num}.** {step.text}")
    if step.screenshot:
        path = screenshot_path(step.screenshot)
        if path.exists():
            st.image(str(path), caption=step.caption, width=_display_width(path))


def _render_fields_table(guide: PlatformCred) -> None:
    rows = [{
        "Champ": f.label,
        "Exemple (factice)": f.example,
        "🔒": "secret" if f.secret else "",
        "Note": f.note or "",
    } for f in guide.fields]
    st.caption("Valeurs à coller dans 🔑 Credentials API :")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

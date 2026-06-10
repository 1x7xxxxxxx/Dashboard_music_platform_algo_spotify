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
from src.dashboard.utils.i18n import t


_BY_KEY = {g.key: g for g in CREDENTIAL_GUIDES}


def render_credential_guides() -> None:
    """One expander per platform: steps + screenshots + the values to paste."""
    st.markdown(t("credentials.guide.list_header",
                  "**Comment obtenir les identifiants de chaque plateforme ?**"))
    for guide in CREDENTIAL_GUIDES:
        _render_guide_expander(guide)


def render_credential_guide_for(platform_key: str) -> None:
    """Render the single-platform guide (used inside that platform's tab)."""
    guide = _BY_KEY.get(platform_key)
    if guide is not None:
        _render_guide_expander(guide)


def _render_guide_expander(guide: PlatformCred) -> None:
    # Translate at the render site: the PlatformCred constants are evaluated at
    # import (language not yet chosen), so the FR source strings are passed as
    # the `t()` default and the EN keys live in the credentials catalog.
    title = t(f"credentials.guide.{guide.key}.expander",
              "{icon} {title} — obtenir les identifiants").format(
                  icon=guide.icon, title=guide.title)
    with st.expander(title, expanded=False):
        st.markdown(t(f"credentials.guide.{guide.key}.intro", guide.intro))
        st.markdown(t("credentials.guide.portal", "🔗 Portail : [{url}]({url})").format(
            url=guide.portal_url))
        for i, step in enumerate(guide.steps, 1):
            _render_step(guide.key, i, step)
        _render_fields_table(guide)
        if guide.note:
            st.info(t(f"credentials.guide.{guide.key}.note", guide.note))


def _render_step(platform_key: str, num: int, step: CredStep) -> None:
    text = t(f"credentials.guide.{platform_key}.step_{num}", step.text)
    st.markdown(f"**{num}.** {text}")
    if step.screenshot:
        path = screenshot_path(step.screenshot)
        if path.exists():
            caption = (t(f"credentials.guide.{platform_key}.step_{num}_caption",
                         step.caption) if step.caption else None)
            st.image(str(path), caption=caption, width=_display_width(path))


def _render_fields_table(guide: PlatformCred) -> None:
    col_field = t("credentials.guide.col_field", "Champ")
    col_example = t("credentials.guide.col_example", "Exemple (factice)")
    col_note = t("credentials.guide.col_note", "Note")
    rows = [{
        col_field: f.label,
        col_example: f.example,
        "🔒": "secret" if f.secret else "",
        col_note: t(f"credentials.guide.{guide.key}.note_{i}", f.note) if f.note else "",
    } for i, f in enumerate(guide.fields, 1)]
    st.caption(t("credentials.guide.paste_caption",
                 "Valeurs à coller dans 🔑 Credentials API :"))
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

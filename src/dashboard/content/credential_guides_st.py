"""Streamlit renderer for the API-credential guides (see credential_guides).

Type: Sub
Uses: streamlit, src.dashboard.content.credential_guides
Depends on: assets/credential_guide/*.png (optional — missing images degrade)
Persists in: nothing
"""
import pandas as pd
from urllib.parse import quote

import streamlit as st

from src.dashboard.content.credential_guides import (
    CREDENTIAL_GUIDES,
    CredStep,
    PlatformCred,
    screenshot_path,
)
from src.dashboard.content.csv_guides_st import _display_width
from src.dashboard.utils.i18n import t
from src.dashboard.utils.os_hints import md as _os_md, os_selector
from src.dashboard.auth import is_admin


_BY_KEY = {g.key: g for g in CREDENTIAL_GUIDES}


def render_credential_guides() -> None:
    """One expander per platform: steps + screenshots + the values to paste."""
    st.markdown(t("credentials.guide.list_header",
                  "**Comment obtenir les identifiants de chaque plateforme ?**"))
    # Keyboard steps differ on macOS; pick once here for every guide below.
    os_selector(key="cred_guides_os")
    for guide in CREDENTIAL_GUIDES:
        _render_guide_expander(guide)


def render_credential_guide_for(platform_key: str,
                                artist_name: str | None = None) -> None:
    """Render the single-platform guide (used inside that platform's tab).

    Le sélecteur d'OS est rendu ICI depuis le 2026-08-23. Il existait déjà
    (`utils.os_hints.os_selector`) mais n'était appelé que par
    `render_credential_guides()`, **qui n'a aucun appelant** — donc il ne s'affichait sur
    aucune page. Le chemin vivant, celui-ci, se contentait de résoudre les jetons
    (`{{VIEW_SOURCE}}`, `{{FIND}}`, `{{COPY}}`…) par **reniflage du User-Agent, avec
    WINDOWS par défaut**, sans laisser à un artiste Mac le moindre moyen de corriger une
    détection fausse. Remonté par GRiNCH, qui est sur Mac.

    Une clé par plateforme : les onglets coexistent dans la même session, et une clé
    partagée ferait basculer les quatre en même temps depuis un seul onglet.
    """
    guide = _BY_KEY.get(platform_key)
    if guide is not None:
        os_selector(key=f"cred_guide_os_{platform_key}")
        _render_guide_expander(guide, artist_name=artist_name)


def _render_guide_expander(guide: PlatformCred,
                           artist_name: str | None = None) -> None:
    # Translate at the render site: the PlatformCred constants are evaluated at
    # import (language not yet chosen), so the FR source strings are passed as
    # the `t()` default and the EN keys live in the credentials catalog.
    title = t(f"credentials.guide.{guide.key}.expander",
              "{icon} {title} — obtenir les identifiants").format(
                  icon=guide.icon, title=guide.title)
    with st.expander(title, expanded=False):
        st.markdown(_os_md(t(f"credentials.guide.{guide.key}.intro", guide.intro)))
        _render_portal_link(guide, artist_name)
        for i, step in enumerate(guide.steps, 1):
            _render_step(guide.key, i, step)
        _render_fields_table(guide)
        if guide.note:
            st.info(_os_md(t(f"credentials.guide.{guide.key}.note", guide.note)))
        # `admin_note` porte ce qui relève de l'exploitant — créer une app chez le
        # fournisseur, poser une variable d'environnement. L'artiste n'a pas ces
        # accès, et le lui montrer sur la page où il colle un lien lui fait croire
        # qu'il manque une étape. Rendu au seul admin.
        if guide.admin_note and is_admin():
            st.caption("🛠️ " + _os_md(
                t(f"credentials.guide.{guide.key}.admin_note", guide.admin_note)))


def _render_portal_link(guide: PlatformCred, artist_name: str | None) -> None:
    """The portal link, aimed at this artist when the platform allows it.

    `quote` and not `quote_plus`: Spotify's search path takes the query as a PATH
    segment, where a `+` stays a literal plus sign and would search for it.
    """
    if guide.portal_search_url and artist_name and artist_name.strip():
        url = guide.portal_search_url.format(q=quote(artist_name.strip(), safe=""))
        st.markdown(t("credentials.guide.portal_search",
                      "🔗 Ouvrir **{name}** sur {title} : [{url}]({url})").format(
                          name=artist_name.strip(), title=guide.title, url=url))
        return
    st.markdown(t("credentials.guide.portal", "🔗 Portail : [{url}]({url})").format(
        url=guide.portal_url))


def _render_step(platform_key: str, num: int, step: CredStep) -> None:
    text = _os_md(t(f"credentials.guide.{platform_key}.step_{num}", step.text))
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

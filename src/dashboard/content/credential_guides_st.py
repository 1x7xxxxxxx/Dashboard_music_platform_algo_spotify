"""Streamlit renderer for the API-credential guides (see credential_guides).

Type: Sub
Uses: streamlit, src.dashboard.content.credential_guides
Depends on: assets/credential_guide/*.png (optional — missing images degrade)
Persists in: nothing
"""
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
from src.dashboard.utils.os_hints import has_os_tokens, md as _os_md, os_selector
from src.dashboard.auth import is_admin


_BY_KEY = {g.key: g for g in CREDENTIAL_GUIDES}


def render_credential_guides() -> None:
    """One expander per platform: steps + screenshots + the values to paste."""
    st.markdown(t("credentials.guide.list_header",
                  "**Comment obtenir les identifiants de chaque plateforme ?**"))
    # Le sélecteur d'OS n'apparaît que si AU MOINS un guide en dépend — voir
    # `_needs_os_selector`.
    if any(_needs_os_selector(g) for g in CREDENTIAL_GUIDES):
        os_selector(key="cred_guides_os")
    for guide in CREDENTIAL_GUIDES:
        _render_guide_expander(guide)


def render_credential_guide_for(platform_key: str,
                                artist_name: str | None = None,
                                expanded: bool = False) -> None:
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
        # …et seulement quand ce guide-ci dépend vraiment du clavier. Au 2026-09-04
        # aucun des quatre n'en dépend plus : le dernier jeton ({{COPY}}, guide Meta)
        # est parti avec le passage au collage de l'URL entière. Le sélecteur
        # disparaît donc de fait — mais par la règle, pas par une suppression : le
        # jour où un guide redemande un raccourci, il revient tout seul.
        if _needs_os_selector(guide):
            os_selector(key=f"cred_guide_os_{platform_key}")
        _render_guide_expander(guide, artist_name=artist_name, expanded=expanded)


def _needs_os_selector(guide: PlatformCred) -> bool:
    """Ce guide contient-il une instruction qui diffère entre Windows et macOS ?

    Lit la MÊME prose que le rendu — intro, étapes, notes de champ, note, note
    admin. Une portée plus étroite (les seules étapes, par exemple) laisserait un
    raccourci dans l'intro sans son sélecteur, ce qui est le défaut d'origine à
    l'envers.
    """
    return has_os_tokens(
        guide.intro or "", guide.note or "", guide.admin_note or "",
        *[s.text or "" for s in (guide.steps or ())],
        *[f.note or "" for f in (guide.fields or ())],
    )


def _render_guide_expander(guide: PlatformCred,
                           artist_name: str | None = None,
                           expanded: bool = False) -> None:
    # Translate at the render site: the PlatformCred constants are evaluated at
    # import (language not yet chosen), so the FR source strings are passed as
    # the `t()` default and the EN keys live in the credentials catalog.
    title = t(f"credentials.guide.{guide.key}.expander",
              "{icon} {title} — obtenir les identifiants").format(
                  icon=guide.icon, title=guide.title)
    # `expanded` est décidé par l'APPELANT, pas ici. Dans l'onglet de saisie il vaut
    # True : le guide est la colonne de droite, il n'y a rien à ouvrir pour lire ce
    # qu'on doit faire à gauche. Sur la page « Process — Credentials », qui liste les
    # quatre guides à la suite, il reste replié — quatre pavés dépliés y seraient un
    # mur, pas une aide.
    with st.expander(title, expanded=expanded):
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
    """Ce qu'il y a à coller, et OÙ — plus un tableau d'exemples factices.

    Signalé le 2026-09-04 : « intégrer la section *saisir tes identifiants* à la
    place de l'exemple factice, car confusion et surcharge ; mettre l'exemple en
    italique ». Le tableau présentait l'exemple dans une colonne aussi large et
    aussi nette que le nom du champ, sur une page dont le seul geste est de coller
    une valeur — un artiste qui copie la ligne d'exemple fait exactement ce que la
    mise en page lui montre.

    Trois changements, tous dans ce sens : la phrase d'entête nomme l'encadré du
    formulaire au lieu de dire « ci-dessous » (le guide est SOUS le formulaire) ;
    l'exemple passe en italique, en légende, précédé de `ex.` et suivi de « ne le
    copie pas » ; le tableau disparaît au profit d'une liste, qui tient sur un
    téléphone là où un `st.dataframe` à quatre colonnes défile latéralement.
    """
    # Ne nomme plus l'encadré ni sa position : le guide est la colonne d'à côté DE
    # cet encadré depuis le 2026-09-04, donc la phrase décrivait à quelqu'un
    # l'endroit où il se trouve déjà. Elle dit ce qu'elle a à dire — quoi coller —
    # et reste vraie dans le PDF, qui n'a ni « en haut » ni « à côté ».
    st.markdown(t("credentials.guide.paste_header", "**Les valeurs à coller :**"))
    for i, f in enumerate(guide.fields, 1):
        lock = " 🔒" if f.secret else ""
        label = t(f"credentials.guide.{guide.key}.field_{i}", f.label)
        st.markdown(f"- **{label}**{lock}")
        note = t(f"credentials.guide.{guide.key}.note_{i}", f.note) if f.note else ""
        if note:
            st.caption(f"　{note}")
        st.caption("　" + t("credentials.guide.example_inline",
                           "*ex. {example}* — exemple de forme, ne le copie pas")
                   .format(example=f.example))

"""📖 Glossaire — how the app works, and every technical word it uses (R592).

Type: Feature
Uses: src.dashboard.utils.glossary, src.dashboard.utils.i18n
Depends on: nothing (no database read — the page renders for any session)
Persists in: nothing

Owner, 2026-10-15 : « une vue Glossaire dans Compte, juste après Mon compte : le schéma du
fonctionnement de l'app et toutes les définitions techniques ». The diagram comes first —
the pages are read by their charts, and this one too.
"""
import streamlit as st

from src.dashboard.utils import glossary
from src.dashboard.utils.i18n import t


def flow_dot() -> str:
    """The app's data flow, as Graphviz DOT. Pure — the test reads its nodes."""
    nodes = [
        ("apis", t("glossary.flow.apis", "Spotify · YouTube · SoundCloud · Meta · Instagram")),
        ("csv", t("glossary.flow.csv", "Tes exports CSV\n(Spotify for Artists, Apple, distributeurs)")),
        ("collect", t("glossary.flow.collect", "Collecte de chaque nuit")),
        ("db", t("glossary.flow.db", "Ta base de données\n(une ligne par jour et par titre)")),
        ("gold", t("glossary.flow.gold", "Calculs partagés\n(une seule définition par chiffre)")),
        ("model", t("glossary.flow.model", "Modèles de prédiction\n(algos Spotify)")),
        ("pages", t("glossary.flow.pages", "Tes pages\n(graphiques, PDF, alertes)")),
    ]
    edges = [("apis", "collect"), ("csv", "db"), ("collect", "db"), ("db", "gold"),
             ("gold", "pages"), ("gold", "model"), ("model", "pages")]
    lines = ["digraph app {", "  rankdir=LR;",
             '  node [shape=box, style="rounded,filled", fillcolor="#eef3f8", '
             'fontname="Helvetica", fontsize=11];']
    lines += [f'  {k} [label="{label}"];'.replace("\n", "\\n") for k, label in nodes]
    lines += [f"  {a} -> {b};" for a, b in edges]
    return "\n".join(lines + ["}"])


def show() -> None:
    st.title(t("glossary.title", "📖 Glossaire"))
    st.subheader(t("glossary.flow_title", "Comment marche l'app"))
    st.graphviz_chart(flow_dot(), use_container_width=True)
    st.subheader(t("glossary.terms_title", "Les mots de l'app"))
    for label, keys in glossary.by_group():
        with st.expander(label, expanded=False):
            st.markdown("\n".join(f"- **{glossary.term(k)}** — {glossary.definition(k)}"
                                  for k in keys))

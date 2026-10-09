"""trigger_algo sections — the page's parts, named ONCE for the layout and the guide.

Type: Utility
Uses: src.dashboard.utils.i18n
Depends on: nothing
Persists in: nothing

R380 (2026-10-05): « Comment lire cette page » listed seven tabs for a page that had
four — it had been rewritten twice by hand and drifted twice. The layout and the guide
now read this tuple, so a part cannot be added, renamed or removed in one of them only.
"""
import streamlit as st

from src.dashboard.utils.i18n import t

# (key, label i18n key, FR label, description i18n key, FR description)
PAGE_SECTIONS = (
    ("catalogue", "trigger_algo.tab_catalogue", "🎯 Où en sont mes titres",
     "trigger_algo.guide_section_catalogue",
     "ton catalogue classé par l'avancement vers la porte la plus proche."),
    ("titre", "trigger_algo.tab_titre", "🎧 Ce titre : ce qu'il reste à faire",
     "trigger_algo.guide_section_titre",
     "le verdict du titre choisi, ses leviers et sa trajectoire J+28."),
    ("realise", "trigger_algo.tab_realise", "📈 Ce qui s'est vraiment passé",
     "trigger_algo.guide_section_realise",
     "ce que chaque playlist t'a réellement rapporté, et le pari du modèle face au résultat."),
    ("budget", "trigger_algo.tab_budget", "💰 Budget & ROI",
     "trigger_algo.guide_section_budget",
     "tes réglages de campagne, ton budget Meta restant et ton rythme de dépense."),
    ("argent", "trigger_algo.tab_argent", "💶 Mon argent : où j'en suis",
     "trigger_algo.guide_section_argent",
     "ce qui est rentré face à la somme de tes dépenses, et la date du point mort."),
)

# R405 (V73, V74) : two former pages are sections of this one. Their keys stay routed —
# mails and PDFs link to them — and open the page on THEIR section.
ALIAS_SECTION = {
    "meta_campaign_settings": "budget",
    "revenue_forecast": "argent",
    "meta_cpr_optimizer": "budget",  # R477 (W14)
}


def arrival_section(alias: str | None) -> str | None:
    """The section an old page key names — app.py sets the alias on the arriving run only."""
    return ALIAS_SECTION.get(alias) if alias else None


def section_label(key: str) -> str:
    return next(t(k, fr) for sk, k, fr, _dk, _dfr in PAGE_SECTIONS if sk == key)


def detail(label: str | None = None):
    """The one place a table may sit on this page: folded, under « Détail chiffré ».

    R403 (V59): the page is read top to bottom, figures first; a raw table is the
    detail behind a figure, never the figure. `tests/test_the_algo_page_reads_top_to_bottom.py`
    refuses a `st.dataframe` rendered outside an expander.
    """
    return st.expander(label or t("trigger_algo.detail", "📋 Détail chiffré"))


def section_keys() -> list[str]:
    return [k for k, *_ in PAGE_SECTIONS]


def section_labels() -> list[str]:
    return [t(key, fr) for _k, key, fr, _dk, _dfr in PAGE_SECTIONS]


def guide_sections_md() -> str:
    head = t("trigger_algo.guide_sections_head", "**🗂️ Les parties de la page**")
    lines = [f"- **{t(key, fr)}** — {t(dkey, dfr)}" for _k, key, fr, dkey, dfr in PAGE_SECTIONS]
    return head + "\n" + "\n".join(lines)

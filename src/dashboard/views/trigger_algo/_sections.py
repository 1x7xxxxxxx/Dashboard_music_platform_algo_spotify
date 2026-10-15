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
# R570 (owner, 2026-10-15) : two parts only — where my tracks stand, then once triggered.
PAGE_SECTIONS = (
    ("catalogue", "trigger_algo.tab_catalogue", "🎯 Où en sont mes titres",
     "trigger_algo.guide_section_catalogue",
     "tes deux dernières sorties : leur avancement vers chaque playlist, ce qui la déclenche, "
     "ce qu'un déclenchement rapporte et la prévision de leurs écoutes."),
    ("declenche", "trigger_algo.tab_declenche", "🎯 Une fois déclenché",
     "trigger_algo.guide_section_declenche",
     "tes saisies des streams algorithmiques réalisés et des ajouts en playlist depuis la sortie."),
)

# R553 (ADR-033) : `revenue_forecast` is no longer one — it is an alias of the Trésorerie.
# R405 (V73, V74) : two former pages were sections of this one. R570 removed the budget
# section (the Trésorerie covers it); their keys stay routed — mails and PDFs link to
# them — and open the page with NO section (None): the key's presence is the arrival.
ALIAS_SECTION: dict[str, str | None] = {
    "meta_campaign_settings": None,
    "meta_cpr_optimizer": None,  # R477 (W14)
}


def is_alias_arrival(alias: str | None) -> bool:
    """True when the run arrives from a former page key — app.py sets it on that run only."""
    return bool(alias) and alias in ALIAS_SECTION


def arrival_section(alias: str | None) -> str | None:
    """The section an old page key names, or None (no section, or not an alias)."""
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

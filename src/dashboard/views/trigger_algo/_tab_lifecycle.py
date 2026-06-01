"""trigger_algo — _show_tab_lifecycle (move-only split)."""
from src.dashboard.utils.ui import show_empty_state
import streamlit as st
from ._common import (
    _LIFECYCLE_LABELS,
    _LIFECYCLE_PALETTE,
    _age_week_order,
    _compute_age_weeks,
    _lifecycle_band_fig,
    _lifecycle_legend,
    _standardization_block,
)


def _show_tab_lifecycle(db, track, artist_id, release_date, benchmark_df):
    st.subheader("📉 Cycle de vie algorithmique & standardisation")
    if show_empty_state(
        benchmark_df,
        "Benchmark indisponible — artefact non généré "
        "(voir migration 035 / export_lifecycle_benchmark.py).",
        level="warning",
    ):
        return

    age_weeks = _compute_age_weeks(release_date)
    live_order, live_bin = _age_week_order(age_weeks)
    c1, c2 = st.columns([1, 2])
    c1.metric("Âge du titre", f"{age_weeks} sem." if age_weeks is not None else "—")
    c2.caption(f"Sortie : {release_date or '—'} · tranche {live_bin or '—'} · "
               "courbes = cohorte globale statique")
    _lifecycle_legend()

    for algo in ("DW", "RR", "RADIO"):
        curve = benchmark_df[benchmark_df["algorithm"] == algo].sort_values("age_week_bin_order")
        if curve.empty:
            continue
        st.plotly_chart(
            _lifecycle_band_fig(curve, _LIFECYCLE_LABELS[algo], live_order, _LIFECYCLE_PALETTE[algo]),
            width="stretch",
        )

    st.markdown("---")
    _standardization_block(db, track, artist_id, age_weeks, benchmark_df)
    st.divider()
    with st.expander("🗒️ Notes & analyses à venir"):
        st.caption("Espace réservé pour intégrer les prochaines analyses "
                   "(distribution complète en boxplots, segmentation par décile, etc.).")

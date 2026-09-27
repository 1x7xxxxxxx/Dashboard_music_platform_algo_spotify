"""trigger_algo pi_gates — move-only split of _common."""
from src.dashboard.utils.i18n import t
import streamlit as st
from ._loaders import _load_threshold_tables


_PI_BINS = [(0, 10, "0-10"), (11, 20, "11-20"), (21, 30, "21-30"),
            (31, 40, "31-40"), (41, 50, "41-50"), (51, 10_000, "50+")]


def _pi_bracket(pi) -> str | None:
    if pi is None:
        return None
    for lo, hi, label in _PI_BINS:
        if lo <= pi <= hi:
            return label
    return None


def _show_pi_breakeven(ml_pred: dict | None) -> None:
    """PI-driven breakeven: the Popularity Index gates algorithmic revenue, so the
    real break-even question is whether the PI crosses each algo's trigger gate.
    """
    if not ml_pred:
        return
    pi = ml_pred.get("pi_forecast_7d")
    tables = _load_threshold_tables()
    if pi is None or not tables:
        return
    brackets = tables.get("pi_brackets", [])
    here = _pi_bracket(pi)
    st.markdown(t("trigger_algo.common.pi_breakeven_header",
                  "**🎯 Rentabilité pilotée par le Popularity Index**"))
    st.caption(t("trigger_algo.common.pi_breakeven_caption",
                 "PI prédit actuel : **{pi} / 100** (tranche {bracket}). Tu ne rentabilises "
                 "via un algo que si ton PI franchit sa porte de déclenchement.")
               .format(pi=int(pi), bracket=here))
    for key, label in (("discover_weekly", "Discover Weekly"),
                       ("radio", "Radio"), ("release_radar", "Release Radar")):
        data = tables.get(key, {})
        gate = next((b for b in brackets if (data.get(b, {}).get("prob") or 0) >= 50), None)
        if not gate:
            continue
        reached = here and brackets.index(here) >= brackets.index(gate)
        status = (t("trigger_algo.common.gate_reached", "✅ porte atteinte") if reached
                  else t("trigger_algo.common.gate_requires", "⛔ requiert PI {gate}").format(gate=gate))
        st.markdown(t("trigger_algo.common.gate_line", "- **{label}** : porte à PI **{gate}** — {status}")
                    .format(label=label, gate=gate, status=status))

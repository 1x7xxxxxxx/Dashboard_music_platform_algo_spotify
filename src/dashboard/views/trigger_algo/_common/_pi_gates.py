"""trigger_algo pi_gates — move-only split of _common."""
from plotly.subplots import make_subplots
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import show_empty_state
import plotly.graph_objects as go
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


def _show_pi_gate_section(ml_pred: dict | None) -> None:
    """B2 — 'you are HERE' on the PI→trigger curves, from the song's PI forecast."""
    st.subheader(t("trigger_algo.common.pi_gate_header", "🚪 Portes algorithmiques par Popularity Index"))
    st.caption(t(
        "trigger_algo.common.pi_gate_caption",
        "Le Popularity Index (0-100) est la porte d'entrée de chaque algorithme. "
        "La barre blanche situe votre titre ; n = taille d'échantillon par tranche."
    ))
    tables = _load_threshold_tables()
    if not tables:
        show_empty_state(t("trigger_algo.common.pi_tables_unavailable",
                           "Tables de seuils PI indisponibles — lancer `python3 machine_learning/train.py`."))
        return

    pi = ml_pred.get("pi_forecast_7d") if ml_pred else None
    here = _pi_bracket(pi)
    if pi is not None:
        st.metric(t("trigger_algo.common.pi_predicted_metric", "Popularity Index prédit"),
                  f"{int(pi)} / 100",
                  help=t("trigger_algo.common.pi_predicted_help",
                         "Régresseur PI (modèle v3). R²=0.92 [0.88–0.94] validé en "
                         "group-CV par chanson, MAE ~2 pts — robuste (vérifié 2026-06-05)."))
    else:
        st.info(t("trigger_algo.common.pi_no_pred",
                  "Pas de PI prédit pour ce titre (scoring ML quotidien non encore exécuté)."))

    brackets = tables.get("pi_brackets", [])
    algos = [("release_radar", "Release Radar (<35j)", "#4C78A8"),
             ("discover_weekly", "Discover Weekly", "#E45756"),
             ("radio", "Radio", "#54A24B")]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[a[1] for a in algos])
    for i, (key, _label, color) in enumerate(algos, start=1):
        data = tables.get(key, {})
        probs = [data.get(b, {}).get("prob") for b in brackets]
        ns = [data.get(b, {}).get("n", 0) for b in brackets]
        # Highlight the song's current bracket in white (visible on the dark
        # theme — the former #111111 was invisible on the near-black background).
        colors = ["#FFFFFF" if b == here else color for b in brackets]
        line_widths = [2 if b == here else 0 for b in brackets]
        fig.add_trace(go.Bar(
            x=brackets, y=probs, marker_color=colors,
            marker_line=dict(color="#1DB954", width=line_widths),
            text=[f"n={n}" for n in ns], textposition="outside",
            hovertemplate="PI %{x}<br>%{y:.0f}% déclenchement<br>%{text}<extra></extra>",
            showlegend=False,
        ), row=1, col=i)
        fig.update_yaxes(range=[0, 112], row=1, col=i)
    fig.update_layout(height=360, margin=dict(t=46, b=20))
    st.plotly_chart(fig, width='stretch')

    def _fmt(p):
        return f"{p:.0f}%" if p is not None else "n/a"

    if here:
        rr = tables.get("release_radar", {}).get(here, {}).get("prob")
        dw = tables.get("discover_weekly", {}).get(here, {}).get("prob")
        radio = tables.get("radio", {}).get(here, {}).get("prob")
        st.markdown(t(
            "trigger_algo.common.pi_chances",
            "À **PI {here}**, vos chances de déclenchement : "
            "Release Radar **{rr}** · Discover Weekly **{dw}** · Radio **{radio}**."
        ).format(here=here, rr=_fmt(rr), dw=_fmt(dw), radio=_fmt(radio)))
        # Reco engine — the highest-leverage DW gate (DW is the hardest door).
        dw_data = tables.get("discover_weekly", {})
        best = max(
            ((b, dw_data.get(b, {}).get("prob")) for b in brackets
             if dw_data.get(b, {}).get("prob") is not None),
            key=lambda t: t[1], default=(None, None),
        )
        if best[0] and best[0] != here:
            st.info(t(
                "trigger_algo.common.pi_lever1",
                "🎯 Levier #1 — le sésame Discover Weekly est à **PI {bracket}** "
                "({prob:.0f}% de déclenchement). Concentrez streams organiques + saves "
                "pour pousser le PI vers cette tranche avant de scaler le budget."
            ).format(bracket=best[0], prob=best[1]))
    st.caption(tables.get("note", ""))


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

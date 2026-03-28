"""Vue Performance Monitor — temps de rendu Streamlit + santé système.

Type: Feature
Uses: st.session_state._perf_log, psutil, get_db_connection
Depends on: app.py routing timer (_t0 / _render_ms)

Indicateurs :
- Render time par page (session courante, rolling 100 renders)
- DB ping (latence connexion)
- CPU / RAM process (psutil)
- Seuils : vert <1s, orange 1-3s, rouge >3s
"""
import time
import streamlit as st
import pandas as pd

from src.dashboard.auth import is_admin

# Thresholds in ms
_GREEN  = 1_000
_ORANGE = 3_000


def _render_badge(ms: int) -> str:
    if ms < _GREEN:
        return f"🟢 {ms} ms"
    if ms < _ORANGE:
        return f"🟠 {ms} ms"
    return f"🔴 {ms} ms"


def _db_ping_ms() -> int | None:
    """Return round-trip time to PostgreSQL in ms, or None if unreachable."""
    from src.dashboard.utils import get_db_connection
    t0 = time.perf_counter()
    db = get_db_connection()
    if db is None:
        return None
    try:
        db.fetch_query("SELECT 1", ())
        return int((time.perf_counter() - t0) * 1000)
    finally:
        db.close()


def _system_metrics() -> dict:
    """Return CPU % and RSS memory in MB for the current process."""
    try:
        import psutil, os
        proc = psutil.Process(os.getpid())
        return {
            'cpu_pct': proc.cpu_percent(interval=0.1),
            'ram_mb':  proc.memory_info().rss / 1_048_576,
        }
    except ImportError:
        return {'cpu_pct': None, 'ram_mb': None}


def show():
    if not is_admin():
        st.error("Accès réservé aux admins.")
        st.stop()

    st.title("⚡ Performance Dashboard")
    st.caption("Temps de rendu Streamlit par page · Session courante uniquement (non persisté entre sessions)")

    # ── Section 1 : KPIs instantanés ─────────────────────────────────────────
    st.subheader("État en temps réel")

    db_ms  = _db_ping_ms()
    sys_m  = _system_metrics()
    log    = st.session_state.get('_perf_log', [])
    last   = log[-1] if log else None

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if last:
            st.metric("Dernier rendu", _render_badge(last['ms']), help="Temps Python pour rendre la dernière page (DB + calculs + Streamlit)")
        else:
            st.metric("Dernier rendu", "— (navigue vers une page)")

    with col2:
        if db_ms is None:
            st.metric("DB ping", "❌ Inaccessible")
        else:
            st.metric("DB ping", _render_badge(db_ms), help="Latence aller-retour SELECT 1 sur PostgreSQL")

    with col3:
        if sys_m['ram_mb'] is not None:
            ram = sys_m['ram_mb']
            color = "🟢" if ram < 400 else ("🟠" if ram < 800 else "🔴")
            st.metric("RAM process", f"{color} {ram:.0f} MB", help="Mémoire RSS du process Streamlit")
        else:
            st.metric("RAM process", "psutil non installé")

    with col4:
        if sys_m['cpu_pct'] is not None:
            cpu = sys_m['cpu_pct']
            color = "🟢" if cpu < 30 else ("🟠" if cpu < 70 else "🔴")
            st.metric("CPU process", f"{color} {cpu:.1f} %", help="CPU du process Streamlit sur 0.1s")
        else:
            st.metric("CPU process", "psutil non installé")

    st.markdown("---")

    # ── Section 2 : Seuils de migration ──────────────────────────────────────
    st.subheader("Seuils d'alerte")
    st.markdown("""
| Indicateur | 🟢 OK | 🟠 Surveiller | 🔴 Migrer |
|---|---|---|---|
| Render time | < 1 000 ms | 1 000 – 3 000 ms | > 3 000 ms |
| DB ping | < 50 ms | 50 – 200 ms | > 200 ms |
| RAM process | < 400 MB | 400 – 800 MB | > 800 MB |
| CPU process | < 30 % | 30 – 70 % | > 70 % |

**Déclencheur de migration Streamlit → React/Next.js** : render time > 3 000 ms de façon répétée avec plusieurs artistes connectés simultanément.
""")

    st.markdown("---")

    # ── Section 3 : Historique session ───────────────────────────────────────
    st.subheader(f"Historique session ({len(log)} renders)")

    if not log:
        st.info("Navigue vers plusieurs pages pour alimenter l'historique.")
        return

    df = pd.DataFrame(log)
    df['badge'] = df['ms'].apply(_render_badge)

    # Summary par page
    summary = (
        df.groupby('page')['ms']
        .agg(renders='count', moy='mean', max='max', min='min')
        .reset_index()
        .sort_values('moy', ascending=False)
    )
    summary['moy'] = summary['moy'].round(0).astype(int)
    summary['max'] = summary['max'].astype(int)
    summary['min'] = summary['min'].astype(int)
    summary.columns = ['Page', 'Renders', 'Moy (ms)', 'Max (ms)', 'Min (ms)']

    st.dataframe(summary, use_container_width=True, hide_index=True)

    # Sparkline
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['ts'], y=df['ms'],
        mode='lines+markers',
        line=dict(color='#1DB954', width=2),
        marker=dict(
            color=['#28a745' if m < _GREEN else ('#ffc107' if m < _ORANGE else '#dc3545') for m in df['ms']],
            size=7,
        ),
        hovertemplate='%{x}<br>%{y} ms<extra></extra>',
        name='Render time',
    ))
    fig.add_hline(y=_GREEN,  line_dash='dot', line_color='orange', annotation_text='1 000 ms')
    fig.add_hline(y=_ORANGE, line_dash='dot', line_color='red',    annotation_text='3 000 ms')
    fig.update_layout(
        height=280,
        margin=dict(t=10, b=10, l=0, r=0),
        xaxis_title='Heure',
        yaxis_title='ms',
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Log brut
    with st.expander("Log brut (100 derniers renders)"):
        st.dataframe(df[['ts', 'page', 'ms', 'badge']].iloc[::-1], use_container_width=True, hide_index=True)

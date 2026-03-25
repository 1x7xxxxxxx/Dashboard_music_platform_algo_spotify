"""Page Export PDF — Rapport artiste paramétrable."""
import streamlit as st
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.pdf_exporter import (
    get_available_songs, get_artists_list, generate_pdf, ALL_SECTIONS,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_period(period_label, custom_from, custom_to):
    now = datetime.now()
    mapping = {
        "3 derniers mois":  3,
        "6 derniers mois":  6,
        "12 derniers mois": 12,
        "Cette année":      None,
        "Personnalisé":     "custom",
    }
    v = mapping[period_label]
    if v == "custom":
        return custom_from, custom_to
    if v is None:
        return date(now.year, 1, 1), now.date()
    return (now - relativedelta(months=v)).replace(day=1).date(), now.date()


# ─── UI ──────────────────────────────────────────────────────────────────────

def show():
    st.title("📄 Export PDF — Rapport Artiste")
    st.caption(
        "Configurez le rapport, sélectionnez les sections et les chansons à inclure, "
        "puis générez le PDF téléchargeable."
    )
    st.markdown("---")

    db = get_db_connection()
    if db is None:
        return

    try:
        _show_form(db)
    finally:
        db.close()


def _show_form(db):
    admin = is_admin()
    now = datetime.now()

    # ── Ligne 1 : Artiste + Période ──────────────────────────────────────────
    col_artist, col_period, col_custom = st.columns([2, 2, 2])

    with col_artist:
        st.markdown("**👤 Artiste**")
        if admin:
            artists = get_artists_list(db)
            if not artists:
                st.warning("Aucun artiste actif en base.")
                return
            artist_options = {a['name']: a['id'] for a in artists}
            selected_name  = st.selectbox("Artiste", list(artist_options.keys()),
                                          label_visibility="collapsed")
            report_artist_id   = artist_options[selected_name]
            report_artist_name = selected_name
        else:
            report_artist_id   = get_artist_id()
            report_artist_name = st.session_state.get('name', f'Artiste #{report_artist_id}')
            st.info(f"👤 {report_artist_name}")

    with col_period:
        st.markdown("**📅 Période**")
        period_label = st.selectbox(
            "Période", ["3 derniers mois", "6 derniers mois", "12 derniers mois",
                        "Cette année", "Personnalisé"],
            index=2, label_visibility="collapsed"
        )

    with col_custom:
        if period_label == "Personnalisé":
            st.markdown("**📅 Dates**")
            c1, c2 = st.columns(2)
            custom_from = c1.date_input("Du", value=date(now.year, 1, 1), label_visibility="visible")
            custom_to   = c2.date_input("Au", value=now.date(), label_visibility="visible")
        else:
            custom_from = custom_to = None
            st.empty()

    from_date, to_date = _resolve_period(period_label, custom_from, custom_to)

    st.markdown("---")

    # ── Ligne 2 : Sections à inclure ────────────────────────────────────────
    st.markdown("**📑 Sections à inclure**")
    sec_cols = st.columns(len(ALL_SECTIONS))
    sections = {}
    defaults = {'freshness': True, 'streams': True, 'kpi': True, 'roi': True, 'songs': False}
    for col, (key, label) in zip(sec_cols, ALL_SECTIONS.items()):
        sections[key] = col.checkbox(label, value=defaults.get(key, True), key=f"sec_{key}")

    # ── Ligne 3 : Sélection chansons (conditionnel) ──────────────────────────
    selected_songs = []
    if sections.get('songs'):
        st.markdown("**🎵 Chansons à inclure dans le focus**")
        available = get_available_songs(db, report_artist_id)
        if available:
            selected_songs = st.multiselect(
                "Chansons", available, default=available[:5],
                label_visibility="collapsed",
                placeholder="Choisissez une ou plusieurs chansons…"
            )
            if not selected_songs:
                st.warning("Sélectionnez au moins une chanson pour activer la section Focus.")
        else:
            st.info("Aucune donnée S4A disponible pour cet artiste.")
            sections['songs'] = False

    st.markdown("---")

    # ── Aperçu du rapport ───────────────────────────────────────────────────
    active_sections = [ALL_SECTIONS[k] for k, v in sections.items() if v]
    period_str = f"{from_date.strftime('%d/%m/%Y')} → {to_date.strftime('%d/%m/%Y')}"
    st.caption(
        f"Rapport pour **{report_artist_name}** · Période : {period_str} · "
        f"Sections : {', '.join(active_sections) if active_sections else '⚠️ aucune'}"
    )

    if not active_sections:
        st.warning("Cochez au moins une section pour générer le rapport.")
        return

    # ── Bouton Générer ──────────────────────────────────────────────────────
    col_gen, _ = st.columns([1, 3])
    with col_gen:
        generate_clicked = st.button("📄 Générer le rapport PDF", type="primary",
                                     width="stretch")

    if generate_clicked:
        db2 = get_db_connection()
        if db2 is None:
            return
        try:
            with st.spinner("Génération du PDF en cours…"):
                pdf_bytes = generate_pdf(
                    db2,
                    artist_id=report_artist_id,
                    artist_name=report_artist_name,
                    from_date=from_date,
                    to_date=to_date,
                    sections=sections,
                    songs=selected_songs if sections.get('songs') else None,
                )
            st.session_state['_export_pdf_bytes']  = pdf_bytes
            st.session_state['_export_pdf_artist'] = report_artist_name
            st.success("PDF généré avec succès !")
        except Exception as e:
            st.error(f"Erreur lors de la génération : {e}")
        finally:
            db2.close()

    # ── Bouton Télécharger (persiste entre reruns) ───────────────────────────
    if st.session_state.get('_export_pdf_bytes'):
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug     = (st.session_state.get('_export_pdf_artist') or 'artiste').replace(" ", "_").lower()
        filename = f"rapport_{slug}_{ts}.pdf"
        st.download_button(
            label="⬇️ Télécharger le rapport",
            data=st.session_state['_export_pdf_bytes'],
            file_name=filename,
            mime="application/pdf",
            width="content",
        )

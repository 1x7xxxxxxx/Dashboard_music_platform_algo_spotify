"""Page Export PDF — Rapport artiste paramétrable."""
import streamlit as st
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.pdf_exporter import (
    get_available_songs, get_artists_list, generate_pdf, ALL_SECTIONS,
    _latest_release, _get_artist_name, _release_date,
)

# Internal sentinel values (== comparisons) — display is translated via format_func.
_PERIOD_SLUGS = {
    "28 derniers jours": "last_28d",
    "3 derniers mois": "last_3m",
    "6 derniers mois": "last_6m",
    "12 derniers mois": "last_12m",
    "Cette année": "this_year",
    "Depuis le début": "all_time",
    "Depuis la sortie de la track": "since_release",
    "Personnalisé": "custom",
}


def _period_display(label: str) -> str:
    return t(f"export_pdf.period.{_PERIOD_SLUGS.get(label, 'custom')}", label)


def _section_display(key: str) -> str:
    return t(f"export_pdf.section.{key}", ALL_SECTIONS[key])


def _slug(s: str) -> str:
    """Filesystem-safe token: alnum kept, everything else → underscore."""
    s = (s or "").strip()
    out = "".join(c if c.isalnum() else "_" for c in s)
    out = "_".join(p for p in out.split("_") if p)  # collapse repeats
    return (out or "NA")[:40]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_period(period_label, custom_from, custom_to, release_date=None):
    now = datetime.now()
    today = now.date()
    if period_label == "Personnalisé":
        return custom_from, custom_to
    if period_label == "28 derniers jours":
        return today - timedelta(days=28), today
    if period_label == "Depuis la sortie de la track":
        # Release date of the selected track (earliest if several) — else full history.
        return (release_date or date(2015, 1, 1)), today
    if period_label == "Depuis le début":
        # Far-past start to capture the full history (catalogue began well after).
        return date(2015, 1, 1), today
    if period_label == "Cette année":
        return date(now.year, 1, 1), today
    months = {"3 derniers mois": 3, "6 derniers mois": 6, "12 derniers mois": 12}[period_label]
    return (now - relativedelta(months=months)).replace(day=1).date(), today


def _selected_release_date(db, artist_id, tracks):
    """Earliest real release date among the selected tracks, or None if none resolve."""
    dates = []
    for trk in tracks:
        rd = _release_date(db, artist_id, trk, None)
        if rd:
            dates.append(rd)
    return min(dates) if dates else None


# ─── UI ──────────────────────────────────────────────────────────────────────

def show():
    # Export PDF is a Free-tier feature (no plan gate).
    st.title(t("export_pdf.title", "📄 Export PDF — Rapport Artiste"))
    st.caption(t(
        "export_pdf.caption",
        "Configurez le rapport, sélectionnez les sections et les chansons à inclure, "
        "puis générez le PDF téléchargeable."
    ))
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
        st.markdown(t("export_pdf.artist_header", "**👤 Artiste**"))
        if admin:
            artists = get_artists_list(db)
            if not artists:
                st.warning(t("export_pdf.no_active_artist", "Aucun artiste actif en base."))
                return
            artist_options = {a['name']: a['id'] for a in artists}
            selected_name  = st.selectbox(t("common.artist", "Artiste"),
                                          list(artist_options.keys()),
                                          label_visibility="collapsed")
            report_artist_id   = artist_options[selected_name]
            report_artist_name = selected_name
        else:
            report_artist_id   = get_artist_id()
            # Real artist name from saas_artists — NOT session['name'] (that's the email).
            report_artist_name = _get_artist_name(db, report_artist_id)
            st.info(f"👤 {report_artist_name}")

    with col_period:
        st.markdown(t("export_pdf.period_header", "**📅 Période**"))
        period_label = st.selectbox(
            t("common.period", "Période"),
            ["28 derniers jours", "3 derniers mois", "6 derniers mois",
             "12 derniers mois", "Cette année", "Depuis le début",
             "Depuis la sortie de la track", "Personnalisé"],
            index=5, label_visibility="collapsed",
            format_func=_period_display,
        )
        st.caption(t(
            "export_pdf.period_caption",
            "Les sections pub & revenus (Meta, Hypeddit, ROI…) sont toujours "
            "calculées **depuis le début** ; la période ci-dessus ne filtre que le "
            "streaming (S4A, YouTube, etc.). « Depuis la sortie de la track » utilise "
            "la date de sortie de la chanson sélectionnée (la plus ancienne si plusieurs)."))

    with col_custom:
        if period_label == "Personnalisé":
            st.markdown(t("export_pdf.dates_header", "**📅 Dates**"))
            c1, c2 = st.columns(2)
            custom_from = c1.date_input(t("export_pdf.date_from", "Du"),
                                        value=date(now.year, 1, 1), label_visibility="visible")
            custom_to   = c2.date_input(t("export_pdf.date_to", "Au"),
                                        value=now.date(), label_visibility="visible")
        else:
            custom_from = custom_to = None
            st.empty()

    st.markdown("---")

    # ── Ligne 2 : Sections à inclure (toutes cochées par défaut) ─────────────
    # Premium-only sections (ML, prévisions, Meta breakdowns/×Spotify) are locked
    # for non-premium users so the free PDF can't leak paywalled content.
    from src.dashboard.auth import get_artist_plan
    from src.dashboard.utils.pdf_exporter import PREMIUM_SECTIONS
    is_premium = admin or get_artist_plan() == 'premium'
    st.markdown(t("export_pdf.sections_header", "**📑 Sections à inclure**"))
    if not is_premium:
        st.caption(t(
            "export_pdf.premium_locked_caption",
            "🔒 Les sections **Premium** (ML, prévisions, Meta avancé) nécessitent le "
            "plan Premium — verrouillées ci-dessous."))
    sections = {}
    items = list(ALL_SECTIONS.items())
    _per_row = 5
    for i in range(0, len(items), _per_row):
        cols = st.columns(_per_row)
        for col, (key, label) in zip(cols, items[i:i + _per_row]):
            if key in PREMIUM_SECTIONS and not is_premium:
                col.checkbox(f"🔒 {_section_display(key)}", value=False,
                             key=f"sec_{key}", disabled=True,
                             help=t("export_pdf.premium_section_help",
                                    "Section Premium — passez au plan Premium pour l'inclure."))
                sections[key] = False
            else:
                sections[key] = col.checkbox(_section_display(key), value=True,
                                             key=f"sec_{key}")

    # ── Ligne 3 : Sélecteurs de chansons (conditionnels) ────────────────────
    available = get_available_songs(db, report_artist_id)
    # Auto-focus the latest release for the song selectors.
    latest = _latest_release(db, report_artist_id)
    _default_song = [latest] if latest and latest in available else available[:1]

    s4a_songs_filter = None
    if sections.get('s4a_songs'):
        st.markdown(t("export_pdf.s4a_songs_header",
                      "**🎵 S4A — Chansons à inclure** (laisser vide = toutes)"))
        if available:
            col_s4a, col_all = st.columns([4, 1])
            with col_s4a:
                s4a_sel = st.multiselect(
                    t("export_pdf.s4a_songs_label", "Chansons S4A"), available,
                    default=_default_song,
                    label_visibility="collapsed",
                    placeholder=t("export_pdf.s4a_songs_placeholder",
                                  "Toutes les chansons (défaut top 15)…"),
                    key="sec_s4a_songs_sel",
                )
            with col_all:
                if st.checkbox(t("export_pdf.all_songs", "Toutes"),
                               value=False, key="sec_s4a_all"):
                    s4a_sel = []
            s4a_songs_filter = s4a_sel if s4a_sel else None
        else:
            st.info(t("export_pdf.no_s4a_data",
                      "Aucune donnée S4A disponible pour cet artiste."))
            sections['s4a_songs'] = False

    selected_songs = []
    if sections.get('songs'):
        st.markdown(t("export_pdf.ml_songs_header", "**🔬 Focus ML — Chansons à inclure**"))
        if available:
            selected_songs = st.multiselect(
                t("export_pdf.ml_songs_label", "Chansons ML"), available,
                default=_default_song,
                label_visibility="collapsed",
                placeholder=t("export_pdf.ml_songs_placeholder",
                              "Choisissez une ou plusieurs chansons…"),
                key="sec_songs_sel",
            )
            if not selected_songs:
                st.warning(t("export_pdf.ml_songs_warning",
                             "Sélectionnez au moins une chanson pour activer la section Focus ML."))
        else:
            st.info(t("export_pdf.no_s4a_data",
                      "Aucune donnée S4A disponible pour cet artiste."))
            sections['songs'] = False

    st.markdown("---")

    # ── Résolution de la période (après les sélecteurs : « Depuis la sortie » a
    #    besoin des chansons choisies) ─────────────────────────────────────────
    release_date = None
    if period_label == "Depuis la sortie de la track":
        _picked = list(dict.fromkeys((s4a_songs_filter or []) + (selected_songs or [])))
        if not _picked and latest:
            _picked = [latest]
        release_date = _selected_release_date(db, report_artist_id, _picked)
        if release_date is None:
            st.warning(t(
                "export_pdf.no_release_date",
                "Aucune date de sortie connue pour la sélection — le rapport couvrira "
                "tout l'historique. Sélectionnez une chanson avec une date de sortie."))
    from_date, to_date = _resolve_period(period_label, custom_from, custom_to, release_date)

    # ── Aperçu du rapport ───────────────────────────────────────────────────
    # Defense-in-depth: never let a non-premium request carry premium sections.
    if not is_premium:
        sections = {k: (v and k not in PREMIUM_SECTIONS) for k, v in sections.items()}

    active_sections = [_section_display(k) for k, v in sections.items() if v]
    period_str = f"{from_date.strftime('%d/%m/%Y')} → {to_date.strftime('%d/%m/%Y')}"
    st.caption(t(
        "export_pdf.report_summary",
        "Rapport pour **{name}** · Période : {period} · Sections : {sections}"
    ).format(
        name=report_artist_name, period=period_str,
        sections=(', '.join(active_sections) if active_sections
                  else t("export_pdf.no_sections", "⚠️ aucune"))))

    if not active_sections:
        st.warning(t("export_pdf.check_one_section",
                     "Cochez au moins une section pour générer le rapport."))
        return

    # ── Bouton Générer ──────────────────────────────────────────────────────
    col_gen, _ = st.columns([1, 3])
    with col_gen:
        generate_clicked = st.button(t("export_pdf.generate_btn", "📄 Générer le rapport PDF"),
                                     type="primary", width="stretch")

    if generate_clicked:
        db2 = get_db_connection()
        if db2 is None:
            return
        try:
            with st.spinner(t("export_pdf.spinner", "Génération du PDF en cours…")):
                pdf_bytes = generate_pdf(
                    db2,
                    artist_id=report_artist_id,
                    artist_name=report_artist_name,
                    from_date=from_date,
                    to_date=to_date,
                    sections=sections,
                    songs=selected_songs if sections.get('songs') else None,
                    s4a_songs_filter=s4a_songs_filter,
                )
            # Track token for the filename: the single selected song, else ALL_TRACK.
            _picked = (s4a_songs_filter or []) + (selected_songs or [])
            _track = _picked[0] if len(set(_picked)) == 1 else "ALL_TRACK"
            st.session_state['_export_pdf_bytes']  = pdf_bytes
            st.session_state['_export_pdf_artist'] = report_artist_name
            st.session_state['_export_pdf_track']  = _track
            st.session_state['_export_pdf_autodl'] = True  # trigger one auto-download
            try:
                from src.dashboard.utils.usage_tracker import track
                track('pdf_generate', page='export_pdf',
                      meta={'sections': [k for k, v in sections.items() if v]})
            except Exception:
                pass
        except Exception as e:
            st.error(t("export_pdf.gen_error",
                       "Erreur lors de la génération : {err}").format(err=e))
        finally:
            db2.close()

    # ── Téléchargement (auto au moment de la génération + bouton de secours) ──
    if st.session_state.get('_export_pdf_bytes'):
        day      = datetime.now().strftime("%Y%m%d")
        artist_s = _slug(st.session_state.get('_export_pdf_artist') or 'artiste')
        track_s  = _slug(st.session_state.get('_export_pdf_track') or 'ALL_TRACK')
        filename = f"{artist_s}_{track_s}_{day}.pdf"

        # Auto-download once, right after generation. The anchor is created + clicked in
        # the PARENT document (not the sandboxed component iframe) so it inherits the
        # transient user activation from the "Générer" click — that's what lets the
        # browser allow the download. Falls back silently if the parent is unreachable.
        if st.session_state.pop('_export_pdf_autodl', False):
            import base64 as _b64
            import streamlit.components.v1 as _components
            b64 = _b64.b64encode(st.session_state['_export_pdf_bytes']).decode('ascii')
            _components.html(
                f"""<script>
                try {{
                  const d = window.parent.document;
                  const a = d.createElement('a');
                  a.href = 'data:application/pdf;base64,{b64}';
                  a.download = {filename!r};
                  d.body.appendChild(a); a.click();
                  setTimeout(function(){{ a.remove(); }}, 1500);
                }} catch (e) {{}}
                </script>""",
                height=0,
            )

        st.success(t("export_pdf.ready",
                     "✅ Rapport prêt. Téléchargement lancé — sinon, bouton ci-dessous."))
        st.download_button(
            label=t("export_pdf.download_btn", "⬇️ Télécharger le rapport"),
            data=st.session_state['_export_pdf_bytes'],
            file_name=filename,
            mime="application/pdf",
            type="primary",
            width="content",
        )

"""Page « Rapport PDF » — rapport artiste paramétrable.

R428 (2026-10-06): this page is LOCKED like Home (R425) — its render is compared to
`tests/fixtures/pdf_report_snapshot.json`; a new photo needs a roadmap row carrying
`<!-- rapport_pdf: oui -->`.
"""
import streamlit as st
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.filters import account_scope
from src.dashboard.utils.i18n import t
from src.dashboard.auth import is_admin, tenant_scope
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
    # Free again since 2026-09-26 (ADR-029): the on-demand report is a reading of the
    # artist's own data. ⚠️ This line said « Free » from 2026-09-04 to 2026-09-26 while the
    # page was Premium — it was false for three weeks. The ML sections stay Premium
    # (`PREMIUM_SECTIONS`), and so does the weekly e-mailed report (`weekly_digest`).
    st.title(t("export_pdf.title", "📄 Rapport PDF"))
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


def _artist_cell(db, admin):
    """The report's artist: a picker for the admin, the session's tenant otherwise."""
    st.markdown(t("export_pdf.artist_header", "**👤 Artiste**"))
    if admin:
        artists = get_artists_list(db)
        if not artists:
            st.warning(t("export_pdf.no_active_artist", "Aucun artiste actif en base."))
            return None, None
        options = {a['name']: a['id'] for a in artists}
        name = st.selectbox(t("common.artist", "Artiste"), list(options.keys()),
                            label_visibility="collapsed")
        return options[name], name
    # `admin` is False here, so tenant_scope() cannot return None — it stops the
    # session instead of exporting every tenant.
    artist_id = tenant_scope()
    # Real artist name from saas_artists — NOT session['name'] (that's the email).
    name = _get_artist_name(db, artist_id)
    st.info(f"👤 {name}")
    return artist_id, name


def _period_cell():
    st.markdown(t("export_pdf.period_header", "**📅 Période**"))
    period_label = st.selectbox(
        t("common.period", "Période"), list(_PERIOD_SLUGS),
        index=5, label_visibility="collapsed", format_func=_period_display,
    )
    st.caption(t(
        "export_pdf.period_caption",
        "Les sections pub & revenus (Meta, Hypeddit, ROI…) sont toujours "
        "calculées **depuis le début** ; la période ci-dessus ne filtre que le "
        "streaming (S4A, YouTube, etc.). « Depuis la sortie de la track » utilise "
        "la date de sortie de la chanson sélectionnée (la plus ancienne si plusieurs)."))
    return period_label


def _songs_cell(available, latest, artist_id):
    """ONE song filter for every section (R386): empty means the whole catalogue.

    It replaces « S4A — chansons à inclure » and « Focus ML — chansons à inclure »,
    which could disagree: a report whose S4A table and ML focus spoke of two different
    sets of titles read as one report about neither.
    """
    key = f"export_pdf_songs_{artist_id}"
    st.markdown(t("export_pdf.songs_header", "**🎵 Chansons**"))
    if not available:
        st.caption(t("export_pdf.no_s4a_data",
                     "Aucune donnée S4A disponible pour cet artiste."))
        return []

    def _pick_latest() -> None:
        st.session_state[key] = [latest]

    picked = st.multiselect(
        t("export_pdf.songs_label", "Chansons"), available, key=key,
        label_visibility="collapsed",
        placeholder=t("export_pdf.songs_placeholder", "Toutes les chansons"))
    st.button(t("export_pdf.latest_btn", "🆕 Dernière sortie"), on_click=_pick_latest,
              disabled=latest not in available, key=f"export_pdf_latest_{artist_id}")
    return picked


def _custom_dates(period_label, now):
    if period_label != "Personnalisé":
        return None, None
    c1, c2, _ = st.columns([1, 1, 2])
    return (c1.date_input(t("export_pdf.date_from", "Du"), value=date(now.year, 1, 1)),
            c2.date_input(t("export_pdf.date_to", "Au"), value=now.date()))


def _section_boxes(is_premium):
    """Sections to include, all ticked by default; Premium ones locked for a free plan."""
    from src.dashboard.utils.pdf_exporter import PREMIUM_SECTIONS
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
        for col, (key, _label) in zip(cols, items[i:i + _per_row]):
            if key in PREMIUM_SECTIONS and not is_premium:
                col.checkbox(f"🔒 {_section_display(key)}", value=False,
                             key=f"sec_{key}", disabled=True,
                             help=t("export_pdf.premium_section_help",
                                    "Section Premium — passez au plan Premium pour l'inclure."))
                sections[key] = False
            else:
                sections[key] = col.checkbox(_section_display(key), value=True,
                                             key=f"sec_{key}")
    # Defense-in-depth: never let a non-premium request carry premium sections.
    return {k: (v and (is_premium or k not in PREMIUM_SECTIONS)) for k, v in sections.items()}


def _show_form(db):
    from src.dashboard.auth import get_artist_plan
    admin = is_admin()
    now = datetime.now()

    # ── Les trois filtres sur une ligne : Artiste · Période · Chansons ───────
    col_artist, col_period, col_songs = st.columns([2, 2, 2])
    with col_artist:
        report_artist_id, report_artist_name = _artist_cell(db, admin)
    if report_artist_id is None:
        return
    # Compte publicitaire Meta — rendu SEULEMENT si l'artiste en a plusieurs
    # (R53 / ADR-013). Un rapport qui additionne les budgets de deux annonceurs
    # distincts donne un CPR qui n'est celui d'aucun des deux ; et c'est un document
    # qu'on envoie à un tiers, donc l'ambiguïté y coûte plus cher qu'à l'écran.
    report_ad_account = account_scope(db, report_artist_id, key="export_pdf_acct")
    with col_period:
        period_label = _period_cell()
    available = get_available_songs(db, report_artist_id)
    latest = _latest_release(db, report_artist_id)
    with col_songs:
        picked = _songs_cell(available, latest, report_artist_id)
    custom_from, custom_to = _custom_dates(period_label, now)

    # ── Le bouton juste après les filtres (R386) ─────────────────────────────
    col_gen, _ = st.columns([1, 3])
    with col_gen:
        generate_clicked = st.button(t("export_pdf.generate_btn", "📄 Générer le rapport PDF"),
                                     type="primary", width="stretch")
    st.markdown("---")
    is_premium = admin or get_artist_plan() == 'premium'
    sections = _section_boxes(is_premium)
    if not available:
        sections['s4a_songs'] = sections['songs'] = False

    # « Depuis la sortie » a besoin des chansons choisies — la dernière sortie à défaut.
    release_date = None
    if period_label == "Depuis la sortie de la track":
        anchor = picked or ([latest] if latest else [])
        release_date = _selected_release_date(db, report_artist_id, anchor)
        if release_date is None:
            st.warning(t(
                "export_pdf.no_release_date",
                "Aucune date de sortie connue pour la sélection — le rapport couvrira "
                "tout l'historique. Sélectionnez une chanson avec une date de sortie."))
    from_date, to_date = _resolve_period(period_label, custom_from, custom_to, release_date)

    if not any(sections.values()):
        st.warning(t("export_pdf.check_one_section",
                     "Cochez au moins une section pour générer le rapport."))
        return

    if generate_clicked:
        # `_show_form(db)` is handed the connection show() already opened and will
        # close. Opening a second one here was the `db2` fallback rule #9 forbids
        # by name — the starker case of the two, since the right connection was
        # already a parameter.
        try:
            with st.spinner(t("export_pdf.spinner", "Génération du PDF en cours…")):
                pdf_bytes = generate_pdf(
                    db,
                    artist_id=report_artist_id,
                    artist_name=report_artist_name,
                    from_date=from_date,
                    to_date=to_date,
                    sections=sections,
                    # ONE list for both song sections: the ML focus covers the titles
                    # the S4A table is filtered on — the whole catalogue when empty.
                    songs=(picked or available) if sections.get('songs') else None,
                    s4a_songs_filter=picked or None,
                    ad_account=report_ad_account,
                )
            # Track token for the filename: the single selected song, else ALL_TRACK.
            _track = picked[0] if len(picked) == 1 else "ALL_TRACK"
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

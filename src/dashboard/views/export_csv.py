"""Page Export CSV global — ZIP téléchargeable avec toutes les données artiste."""
import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import is_admin, tenant_scope
from src.dashboard.utils.csv_exporter import (
    SOURCE_GROUPS as _SOURCE_GROUPS, export_all, export_excel, table_names as _all_table_names)


def _get_artists_list(db) -> list[dict]:
    df = db.fetch_df("SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id")
    return df.to_dict("records")


def _selected_tables() -> list[str]:
    """The tables of every checked source, read from the checkbox state (default: all).

    The prepare button sits ABOVE the source checkboxes (R392), so it reads their state
    rather than their return value — each checkbox keeps its value in `src_<source>`."""
    return [tbl for source, tbls in _SOURCE_GROUPS.items()
            if st.session_state.get(f"src_{source}", True) for tbl in tbls]


def _render_prepare(db, artist_id: int, artist_name: str, tables: list[str]) -> None:
    """Format, « Préparer l'export » and the download — the head of the page (R392, V87)."""
    col_fmt, col_btn, _ = st.columns([1, 1, 2])
    with col_fmt:
        fmt = st.radio(t("export_csv.format", "Format"), ["ZIP (CSV)", "Excel (.xlsx)"],
                       horizontal=True)
    with col_btn:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        generate_clicked = st.button(t("export_csv.prepare_btn", "📦 Préparer l'export"),
                                     type="primary", disabled=not tables)
    if not tables:
        st.warning(t("export_csv.select_one_source", "Sélectionnez au moins une source."))
    if generate_clicked:
        _generate(db, artist_id, artist_name, tables, fmt)
    if st.session_state.get("_export_csv_bytes"):
        _render_download()


def _generate(db, artist_id: int, artist_name: str, tables: list[str], fmt: str) -> None:
    # Rule #9 names this case: never open a `db2` fallback inside the same function.
    try:
        if fmt == "Excel (.xlsx)":
            with st.spinner(t("export_csv.spinner_xlsx", "Génération du fichier Excel en cours…")):
                buf = export_excel(db, artist_id, tables=tables or None)
            st.session_state["_export_csv_fmt"] = "xlsx"
        else:
            with st.spinner(t("export_csv.spinner_zip", "Génération du ZIP en cours…")):
                buf = export_all(db, artist_id, tables=tables or None)
            st.session_state["_export_csv_fmt"] = "zip"
        st.session_state["_export_csv_bytes"] = buf.getvalue()
        st.session_state["_export_csv_artist"] = artist_name
        try:
            from src.dashboard.utils.usage_tracker import track
            track('csv_export', page='export_csv',
                  meta={'fmt': st.session_state.get('_export_csv_fmt'), 'n_tables': len(tables)})
        except Exception:
            pass
        st.success(t("export_csv.ready", "Fichier prêt — cliquez sur Télécharger ci-dessous."))
    except Exception as e:
        st.error(t("export_csv.gen_error", "Erreur lors de la génération : {err}").format(err=e))


def _render_download() -> None:
    """The download button — persists across reruns."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = (st.session_state.get("_export_csv_artist") or "artiste").replace(" ", "_").lower()
    file_fmt = st.session_state.get("_export_csv_fmt", "zip")
    mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if file_fmt == "xlsx" else "application/zip")
    st.download_button(
        label=t("export_csv.download_btn", "⬇️ Télécharger le fichier (.{ext})").format(ext=file_fmt),
        data=st.session_state["_export_csv_bytes"],
        file_name=f"export_{slug}_{ts}.{file_fmt}",
        mime=mime,
    )


def _resolve_artist(db) -> tuple[int, str] | None:
    """(artist_id, name) to export. Admin: from the picker's state — the picker itself is
    drawn BELOW the prepare button (R392), so its value is read before it is drawn."""
    if not is_admin():
        # Same shape as export_pdf: `admin` is False here, so a None would
        # build an export with no tenant filter (R25).
        artist_id = tenant_scope()
        return artist_id, st.session_state.get(
            "name", t("export_csv.artist_fallback", "Artiste #{id}").format(id=artist_id))
    artists = _get_artists_list(db)
    if not artists:
        st.warning(t("export_csv.no_active_artist", "Aucun artiste actif en base."))
        return None
    options = {a["name"]: a["id"] for a in artists}
    name = st.session_state.get(_ARTIST_KEY)
    name = name if name in options else next(iter(options))
    return options[name], name


_ARTIST_KEY = "export_csv_artist"


def show():
    st.title(t("export_csv.title", "⬇️ Export CSV — Données artiste"))
    # « ZIP », « CSV », « table » : trois mots de développeur dans deux lignes, pour
    # une page qui produit… un fichier qu'on ouvre dans Excel. Réécrit le 2026-09-04 —
    # la première phrase dit CE QUE C'EST, les détails viennent après.
    st.caption(t(
        "export_csv.caption",
        "**Un fichier tableur — comme un Excel — avec tes données brutes**, celles que "
        "la plateforme a collectées pour toi. Tu peux l'ouvrir dans Excel, Google "
        "Sheets ou Numbers, et en faire ce que tu veux.\n\n"
        "Le téléchargement est une archive **.zip** : un fichier par source (Spotify, "
        "YouTube, Meta Ads…). Tes données uniquement.\n\n"
        "Ton compte, ta facturation et les journaux techniques n'y sont pas : ils te "
        "sont communiqués sur simple demande — voir la [politique de "
        "confidentialité](?page=privacy)."
    ))

    db = get_db_connection()
    if db is None:
        return

    try:
        resolved = _resolve_artist(db)
        if resolved is None:
            return
        export_artist_id, export_artist_name = resolved

        # R392 (V87) : le geste de la page — choisir ZIP ou Excel et préparer — EN TÊTE ;
        # les réglages (artiste, sources) viennent dessous, déjà remplis par défaut.
        _render_prepare(db, export_artist_id, export_artist_name, _selected_tables())
        st.markdown("---")

        if is_admin():
            col1, _ = st.columns([2, 4])
            with col1:
                st.selectbox(t("export_csv.artist_select", "👤 Artiste à exporter"),
                             [a["name"] for a in _get_artists_list(db)], key=_ARTIST_KEY)
        else:
            st.info(t("export_csv.export_for", "👤 Export pour : **{name}**")
                    .format(name=export_artist_name))

        # `_SOURCE_GROUPS` vient de `csv_exporter.SOURCE_GROUPS` depuis le 2026-09-23
        # (R164) : une seconde liste ici laissait une table exportable jamais cochable.
        # Les tables sans écrivain (`apple_daily_plays`, `youtube_playlists`…) sont
        # dans `csv_exporter._NOT_EXPORTED`, avec leur raison.
        st.subheader(t("export_csv.sources_header", "📋 Sources à inclure"))
        col_sel, _ = st.columns([1, 5])
        if col_sel.button(t("export_csv.select_all", "Tout sélectionner")):
            for k in _SOURCE_GROUPS:
                st.session_state[f"src_{k}"] = True
            st.rerun()
        cols = st.columns(4)
        for i, source in enumerate(_SOURCE_GROUPS):
            _slug_src = source.lower().replace(" ", "_")
            # setdefault, not value= : a widget given both a default and a state value
            # prints Streamlit's warning on screen.
            st.session_state.setdefault(f"src_{source}", True)
            cols[i % 4].checkbox(t(f"export_csv.source.{_slug_src}", source),
                                 key=f"src_{source}")
        st.caption(t("export_csv.tables_selected", "{n} table(s) sélectionnée(s) sur {total}.")
                   .format(n=len(_selected_tables()), total=len(_all_table_names())))

    finally:
        db.close()

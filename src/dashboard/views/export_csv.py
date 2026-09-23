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
    st.markdown("---")

    db = get_db_connection()
    if db is None:
        return

    try:
        admin = is_admin()

        # ── Sélection artiste ─────────────────────────────────────────────
        if admin:
            artists = _get_artists_list(db)
            if not artists:
                st.warning(t("export_csv.no_active_artist", "Aucun artiste actif en base."))
                return
            artist_options = {a["name"]: a["id"] for a in artists}
            col1, _ = st.columns([2, 4])
            with col1:
                selected_name = st.selectbox(
                    t("export_csv.artist_select", "👤 Artiste à exporter"),
                    list(artist_options.keys()))
            export_artist_id = artist_options[selected_name]
            export_artist_name = selected_name
        else:
            # Same shape as export_pdf: `admin` is False here, so a None would
            # build an export with no tenant filter (R25).
            export_artist_id = tenant_scope()
            export_artist_name = st.session_state.get(
                "name",
                t("export_csv.artist_fallback", "Artiste #{id}").format(id=export_artist_id))
            st.info(t("export_csv.export_for", "👤 Export pour : **{name}**")
                    .format(name=export_artist_name))

        st.markdown("---")

        # ── Sélection des sources ─────────────────────────────────────────
        # `_SOURCE_GROUPS` vient de `csv_exporter.SOURCE_GROUPS` depuis le 2026-09-23
        # (R164) : une seconde liste ici laissait une table exportable jamais cochable.
        # Les tables sans écrivain (`apple_daily_plays`, `youtube_playlists`…) sont
        # dans `csv_exporter._NOT_EXPORTED`, avec leur raison.

        st.subheader(t("export_csv.sources_header", "📋 Sources à inclure"))
        col_sel, col_desel = st.columns([1, 5])
        if col_sel.button(t("export_csv.select_all", "Tout sélectionner")):
            for k in _SOURCE_GROUPS:
                st.session_state[f"src_{k}"] = True
        selected_tables: list[str] = []
        cols = st.columns(4)
        for i, (source, tbls) in enumerate(_SOURCE_GROUPS.items()):
            _slug_src = source.lower().replace(" ", "_")
            checked = cols[i % 4].checkbox(
                t(f"export_csv.source.{_slug_src}", source),
                value=st.session_state.get(f"src_{source}", True),
                key=f"src_{source}",
            )
            if checked:
                selected_tables.extend(tbls)

        if not selected_tables:
            st.warning(t("export_csv.select_one_source", "Sélectionnez au moins une source."))

        st.caption(t("export_csv.tables_selected",
                     "{n} table(s) sélectionnée(s) sur {total}.")
                   .format(n=len(selected_tables), total=len(_all_table_names())))
        st.markdown("---")

        # ── Format d'export ──────────────────────────────────────────────
        col_fmt, col_btn, _ = st.columns([1, 1, 2])
        with col_fmt:
            fmt = st.radio(
                t("export_csv.format", "Format"),
                ["ZIP (CSV)", "Excel (.xlsx)"],
                horizontal=True,
            )
        with col_btn:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            generate_clicked = st.button(
                t("export_csv.prepare_btn", "📦 Préparer l'export"),
                type="primary",
                disabled=not selected_tables,
            )

        if generate_clicked:
            # Rule #9 names this case: never open a `db2` fallback inside the same
            # function. `db` is opened at the top of show() and closed in its
            # finally — it is still open right here, so the second connection
            # bought nothing but another socket per click.
            try:
                if fmt == "Excel (.xlsx)":
                    with st.spinner(t("export_csv.spinner_xlsx",
                                      "Génération du fichier Excel en cours…")):
                        buf = export_excel(db, export_artist_id, tables=selected_tables or None)
                    st.session_state["_export_csv_bytes"] = buf.getvalue()
                    st.session_state["_export_csv_fmt"] = "xlsx"
                else:
                    with st.spinner(t("export_csv.spinner_zip", "Génération du ZIP en cours…")):
                        buf = export_all(db, export_artist_id, tables=selected_tables or None)
                    st.session_state["_export_csv_bytes"] = buf.getvalue()
                    st.session_state["_export_csv_fmt"] = "zip"
                st.session_state["_export_csv_artist"] = export_artist_name
                try:
                    from src.dashboard.utils.usage_tracker import track
                    track('csv_export', page='export_csv',
                          meta={'fmt': st.session_state.get('_export_csv_fmt'),
                                'n_tables': len(selected_tables)})
                except Exception:
                    pass
                st.success(t("export_csv.ready",
                             "Fichier prêt — cliquez sur Télécharger ci-dessous."))
            except Exception as e:
                st.error(t("export_csv.gen_error",
                           "Erreur lors de la génération : {err}").format(err=e))

        # ── Bouton télécharger (persiste entre reruns) ───────────────────
        if st.session_state.get("_export_csv_bytes"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = (
                st.session_state.get("_export_csv_artist") or "artiste"
            ).replace(" ", "_").lower()
            file_fmt  = st.session_state.get("_export_csv_fmt", "zip")
            filename  = f"export_{slug}_{ts}.{file_fmt}"
            mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
                        if file_fmt == "xlsx" else "application/zip"
            st.download_button(
                label=t("export_csv.download_btn",
                        "⬇️ Télécharger le fichier (.{ext})").format(ext=file_fmt),
                data=st.session_state["_export_csv_bytes"],
                file_name=filename,
                mime=mime,
            )

    finally:
        db.close()

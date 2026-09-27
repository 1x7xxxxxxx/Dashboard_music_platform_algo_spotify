"""Data Wrapped — la saisie annuelle Spotify for Artists, et son évolution.

Type: Feature
Uses: get_db_connection, fragment_db, secondary_analyses, i18n
Depends on: artist_wrapped
Persists in: artist_wrapped

⚠️ CETTE PAGE N'EST PLUS DANS LE MENU depuis le 2026-09-21. Son contenu est
RENDU par `views/spotify_s4a_combined.py`, où il appartient : les métriques d'un
Wrapped sont des chiffres Spotify for Artists, saisis pour la seule plateforme
que cette page-là raconte. La ROUTE survit — `show()` reste valide, des liens la
visent, et le dépôt garde `process_guide` pour exactement cette raison.

CE QUI EST PARTI AVEC LE DÉPLACEMENT
--------------------------------------
Le « Recap auto », qui recalculait en carrière des chiffres ayant déjà leur page.
Le détail du raisonnement est écrit au-dessus de `_tab_charts`, à l'endroit où
les cinq fonctions vivaient.
"""
import pandas as pd
import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.utils.ui import flash, secondary_analyses
from src.dashboard.auth import get_artist_id, is_admin


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load_wrapped(db, artist_id):
    if artist_id is None:
        query = """
            SELECT w.*, s.name AS artist_name
            FROM artist_wrapped w
            JOIN saas_artists s ON s.id = w.artist_id
            ORDER BY w.year DESC
        """
        return db.fetch_df(query)
    query = """
        SELECT * FROM artist_wrapped
        WHERE artist_id = %s
        ORDER BY year DESC
    """
    return db.fetch_df(query, (artist_id,))


def _load_row_for_year(db, artist_id, year):
    """Return existing row as dict (keyed by column name), or empty dict if not found."""
    df = db.fetch_df(
        "SELECT * FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def _upsert_wrapped(db, artist_id, year, values: dict):
    db.execute_query(
        """
        INSERT INTO artist_wrapped (
            artist_id, year,
            listeners, streams, hours_listened, countries,
            listener_gain_pct, stream_gain_pct, save_gain_pct, playlist_add_gain_pct,
            saves, playlist_adds,
            top_fans_count, top_fans_rank,
            updated_at
        ) VALUES (
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            NOW()
        )
        ON CONFLICT (artist_id, year) DO UPDATE SET
            listeners           = EXCLUDED.listeners,
            streams             = EXCLUDED.streams,
            hours_listened      = EXCLUDED.hours_listened,
            countries           = EXCLUDED.countries,
            listener_gain_pct       = EXCLUDED.listener_gain_pct,
            stream_gain_pct         = EXCLUDED.stream_gain_pct,
            save_gain_pct           = EXCLUDED.save_gain_pct,
            playlist_add_gain_pct   = EXCLUDED.playlist_add_gain_pct,
            saves               = EXCLUDED.saves,
            playlist_adds       = EXCLUDED.playlist_adds,
            top_fans_count      = EXCLUDED.top_fans_count,
            top_fans_rank       = EXCLUDED.top_fans_rank,
            updated_at          = NOW()
        """,
        (
            artist_id, year,
            values['listeners'], values['streams'], values['hours_listened'],
            values['countries'],
            values['listener_gain_pct'], values['stream_gain_pct'],
            values['save_gain_pct'], values['playlist_add_gain_pct'],
            values['saves'], values['playlist_adds'],
            values['top_fans_count'], values['top_fans_rank'],
        )
    )


def _delete_wrapped(db, artist_id, year):
    db.execute_query(
        "DELETE FROM artist_wrapped WHERE artist_id = %s AND year = %s",
        (artist_id, year)
    )


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _absent(v) -> bool:
    """None, or the NaN pandas makes of a NULL in a numeric column (`nan != nan`)."""
    return v is None or v != v


def _prefill(value, cast):
    """The stored value for a form field — or None, never a widget default.

    ⚠️ A FORM DEFAULT IS NOT A MEASUREMENT (2026-09-26). Every field of this form
    was built with `value=int(g(col) or 0)`, and the save writes every widget
    value. A field nobody filled therefore went into `artist_wrapped` as **0**:
    measured on artist 1, the 2025 row carries saves 0, playlist adds 0, the four
    gains at 0.00 and top_fans_count 0 — next to 5 210 saves, +475 % and 11 fans
    in 2024. The charts drew +0.0 % where the volumes say −84 %, because a stored
    0 is not NA and the readers' `dropna()` cannot see it. `hypeddit.py` met the
    same form default on 2026-09-21 : a typed 0 and an unmeasured 0 are
    indistinguishable once in the base, so the distinction is kept HERE, where
    it can still be made. Streamlit renders `value=None` as an empty field and
    returns None for it.
    """
    return None if _absent(value) else cast(value)


def _fmt_big(n):
    if _absent(n):
        return "—"
    n = int(n)
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _fmt_pct(v):
    if _absent(v):
        return "—"
    return f"{float(v):+.1f}%"


# ---------------------------------------------------------------------------
# Recap auto — all-time multi-platform bilan (read-only, reuses kpi_helpers)
# ---------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════
# LE « RECAP AUTO » A ÉTÉ SUPPRIMÉ le 2026-09-21 — demandé, et mesuré redondant.
# ═══════════════════════════════════════════════════════════════════════════
#
# Cinq blocs partaient avec lui : `_recap_spotify`, `_recap_platforms`,
# `_recap_revenue`, `_recap_ml`, `_recap_freshness`. Chacun recalculait, en
# « carrière / all-time », des chiffres qui ont déjà leur page :
#
#     🎧 Spotify            → 🎵 Spotify & Spotify for Artists
#     📺 Autres plateformes → Apple, YouTube, SoundCloud, Instagram
#     💶 Revenus            → 💶 Revenus (iMusician, SACEM, Prévisions)
#     🔮 Highlight ML       → 🚀 Prédiction déclenchement algos
#     🩺 Fraîcheur          → 🚦 Santé onboarding + 🗄️ Santé des données
#
# Ce n'est pas seulement du doublon d'écran : c'est une SECONDE DÉFINITION de
# chaque chiffre. Le dépôt a déjà payé cette forme — un total Apple différent
# entre deux pages du même produit, pour le même artiste au même instant. Une
# page qui re-somme ce qu'une autre somme déjà finit par en différer.
#
# Ce qui reste ici est ce qui n'existe nulle part ailleurs : la SAISIE annuelle
# Spotify for Artists (Wrapped), son évolution, et ses données brutes.


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

# R214 (2026-09-27) — the owner: « Wrapped : peu de plus-value, graphes laids — tuiles
# annuelles repliées, rien retiré ». The eight charts drew ONE number per year each (a
# Wrapped is a yearly recap): a line through three points, a bar per gain. Every value
# they drew is now a TILE, one row per year, folded under the latest year's tiles.
_YEAR_TILES = (
    ("listeners", "Listeners", "listener_gain_pct"),
    ("streams", "Streams", "stream_gain_pct"),
    ("saves", "Saves", "save_gain_pct"),
    ("playlist_adds", "Playlist adds", "playlist_add_gain_pct"),
    ("countries", "Pays", None),
    ("hours_listened", "Heures d'écoute", None),
    ("top_fans_count", "Super-fans", None),
)


@st.fragment
def _tab_charts(artist_options: dict) -> None:
    """L'onglet Évolution — rejoué SEUL quand on change d'artiste.

    @st.fragment (R118, 2026-09-16). C'est la deuxième vue la plus chère de la
    session mesurée le 2026-09-16 : **357,7 ms de phase `view`** contre 13,4 ms de
    chrome. Changer le sélecteur rejouait tout le script — les quatre onglets, dont
    `st.tabs` exécute TOUS les corps, plus la barre latérale.

    ⚠️ Elle ouvre sa PROPRE connexion, et c'est obligatoire, pas un style : son
    sélecteur pilote `_load_wrapped(db, …)`, donc elle relit la base à chaque
    changement — alors que la connexion de `show()` est fermée par son `finally` dès
    la fin du rendu complet. Un fragment qui capturerait celle-là la ré-emprunterait
    au pool sans jamais la rendre : une fuite par session, sur un pool à 10. Garde :
    `tests/test_a_fragment_never_captures_a_connection.py`.
    """
    from src.dashboard.utils.fragment_db import fragment_db

    with fragment_db() as (db, _artist_id):
        # Même règle que la saisie : pas de question quand la réponse est forcée.
        chart_artist_id = _artiste(artist_options, "chart_artist")
        df = _load_wrapped(db, chart_artist_id)

        if df.empty:
            st.info(t("data_wrapped.charts_no_data",
                      "Aucune donnée. Renseignez au moins deux années via l'onglet Saisie."))
        else:
            # KPI row — latest year
            latest = df.iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(t("data_wrapped.field_listeners", "Listeners"),
                      _fmt_big(latest.get('listeners')),
                      delta=_fmt_pct(latest.get('listener_gain_pct')))
            k2.metric(t("data_wrapped.col_streams", "Streams"),
                      _fmt_big(latest.get('streams')),
                      delta=_fmt_pct(latest.get('stream_gain_pct')))
            k3.metric(t("data_wrapped.field_saves", "Saves"),
                      _fmt_big(latest.get('saves')),
                      delta=_fmt_pct(latest.get('save_gain_pct')))
            k4.metric(t("data_wrapped.kpi_countries", "Pays"),
                      _fmt_big(latest.get('countries')))

            # R214 — every yearly value, one ROW per year (newest first), folded. ONE table
            # and not a row of tiles per year: a figure per element of a query is what
            # `test_a_loop_never_draws_one_figure_per_row` refuses — the years are
            # unbounded, the first-screen count would not see them.
            with secondary_analyses(t("data_wrapped.years_expander",
                                      "📅 Mes Wrapped, année par année ({n})").format(n=len(df))):
                years = pd.DataFrame({
                    t("data_wrapped.tile.year", "Année"): df['year'].astype(int).astype(str)})
                for field, label, gain in _YEAR_TILES:
                    cell = df[field].map(_fmt_big)
                    if gain:
                        cell = cell + df[gain].map(
                            lambda v: "" if _absent(v) else f" ({_fmt_pct(v)})")
                    years[t(f"data_wrapped.tile.{field}", label)] = cell
                years[t("data_wrapped.tile.top_fans_rank", "Rang super-fans")] = \
                    df['top_fans_rank'].map(lambda v: "—" if _absent(v) else f"top {int(v)}")
                st.dataframe(years, hide_index=True, width="stretch")




def render_wrapped_section(db, artist_id: int) -> None:
    """La section Wrapped, rendue dans une page qui a DÉJÀ sa connexion.

    Ajoutée le 2026-09-21 pour l'intégration dans `spotify_s4a_combined`. Elle
    ne prend ni ne ferme de connexion : c'est celle de l'appelant (règle #9,
    une connexion par vue).

    ⚠️ Elle N'OUVRE PAS de sélecteur d'artiste — la page hôte a déjà résolu son
    locataire. Le sélecteur de `show()` existe pour l'usage ADMIN de la route
    autonome, qui survit : des liens la visent, et le dépôt garde
    `process_guide` pour exactement cette raison.
    """
    _render_wrapped_body(db, {"": artist_id})


def _artiste(artist_options: dict, cle: str):
    """L'artiste visé, et un sélecteur SEULEMENT s'il y a un choix à faire.

    ⚠️ POSÉ LE 2026-09-22, demandé en regardant l'écran : « pour le choix d'artiste
    il faudrait automatiquement mettre celui du compte ».

    Quatre sélecteurs d'artiste vivaient sur cette page — saisie, suppression,
    évolution, données. Pour un artiste, `artist_options` ne porte qu'UNE entrée :
    les quatre lui demandaient donc de choisir entre lui-même et rien, quatre fois,
    et il devait le faire avant de pouvoir saisir. Un choix qui n'en est pas un est
    une étape de trop.

    Le sélecteur SURVIT quand il y a plusieurs options, parce qu'alors il sert
    vraiment : `show()` est la route autonome et un admin y voit toute la flotte.
    C'est le même critère que partout ailleurs dans ce dépôt — on ne supprime pas la
    possibilité, on supprime la question quand la réponse est forcée.
    """
    noms = list(artist_options.keys())
    if len(noms) <= 1:
        return artist_options[noms[0]] if noms else None
    return artist_options[st.selectbox(
        t("data_wrapped.artist_label", "Artiste"), noms, key=cle)]


def _render_wrapped_body(db, artist_options: dict) -> None:
    """Saisie → évolution → données, sur une connexion FOURNIE.

    Extraite de `show()` le 2026-09-21 pour que `spotify_s4a_combined` puisse
    rendre la même section sans ouvrir une seconde connexion (règle #9). Les
    deux appelants passent donc la leur.
    """
    # L'ORDRE EST LINÉAIRE DEPUIS LE 2026-09-21 : saisie, puis évolution,
    # puis données. Demandé — « intègre le panneau évolution en dessous de
    # saisie et le panneau données ».
    #
    # Et les onglets partent avec le récap, pour une raison mesurée : `st.tabs`
    # exécute le corps de TOUS ses onglets à chaque rendu. Quatre onglets, c'est
    # quatre fois le travail pour un seul regardé — c'est ce qui faisait de
    # cette page la deuxième plus chère de la session du 2026-09-16 (357,7 ms
    # de phase `view` contre 13,4 ms de chrome). Trois sections empilées ne
    # coûtent pas moins en soi ; ce qui coûte moins, c'est d'en avoir supprimé
    # une sur quatre — la plus lourde, qui interrogeait cinq domaines.
    if True:
        st.subheader(t("data_wrapped.form_header", "Ajouter / modifier une année"))

        # L'ARTISTE EST CELUI DU COMPTE quand il n'y a qu'un candidat (2026-09-22).
        # L'année reste pleine largeur : c'est la seule chose à choisir ici.
        target_artist_id = _artiste(artist_options, "form_artist")
        year = st.number_input(
            t("data_wrapped.year_label", "Année"),
            min_value=2015, max_value=datetime.now().year,
            value=datetime.now().year - 1, step=1, key="form_year"
        )

        # Pre-fill from DB if row exists
        existing = _load_row_for_year(db, target_artist_id, int(year))
        g = existing.get  # shorthand

        st.markdown("---")
        st.markdown(t("data_wrapped.section_audience", "**Audience**"))
        c1, c2, c3 = st.columns(3)
        with c1:
            listeners = st.number_input(
                t("data_wrapped.field_listeners", "Listeners"),
                min_value=0, value=_prefill(g('listeners'), int), step=1000
            )
        with c2:
            listener_gain_pct = st.number_input(
                t("data_wrapped.field_listener_gain", "Gain listeners (%)"),
                value=_prefill(g('listener_gain_pct'), float),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )
        with c3:
            countries = st.number_input(
                t("data_wrapped.field_countries", "Pays"),
                min_value=0, value=_prefill(g('countries'), int), step=1
            )

        st.markdown(t("data_wrapped.section_streams", "**Streams**"))
        c4, c5, c6 = st.columns(3)
        with c4:
            streams = st.number_input(
                t("data_wrapped.field_total_streams", "Streams totaux"),
                min_value=0, value=_prefill(g('streams'), int), step=10000
            )
        with c5:
            stream_gain_pct = st.number_input(
                t("data_wrapped.field_stream_gain", "Gain streams (%)"),
                value=_prefill(g('stream_gain_pct'), float),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )
        with c6:
            hours_listened = st.number_input(
                t("data_wrapped.field_hours_listened", "Heures d'écoute"),
                min_value=0.0,
                value=_prefill(g('hours_listened'), float), step=100.0, format="%.1f"
            )

        st.markdown(t("data_wrapped.section_engagement", "**Engagement**"))
        c7, c8, c9, c10 = st.columns(4)
        with c7:
            saves = st.number_input(
                t("data_wrapped.field_saves", "Saves"),
                min_value=0, value=_prefill(g('saves'), int), step=100
            )
        with c8:
            save_gain_pct = st.number_input(
                t("data_wrapped.field_save_gain", "Gain saves (%)"),
                value=_prefill(g('save_gain_pct'), float),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )
        with c9:
            playlist_adds = st.number_input(
                t("data_wrapped.field_playlist_adds", "Playlist adds"),
                min_value=0, value=_prefill(g('playlist_adds'), int), step=100
            )
        with c10:
            playlist_add_gain_pct = st.number_input(
                t("data_wrapped.field_playlist_add_gain", "Gain playlist adds (%)"),
                value=_prefill(g('playlist_add_gain_pct'), float),
                step=0.1, format="%.1f",
                help=t("data_wrapped.gain_help", "Croissance annuelle en %, ex: 45.3")
            )

        st.markdown(t("data_wrapped.section_superfans",
                      "**Super-fans (vous dans leur top artistes)**"))
        ct1, ct2 = st.columns(2)
        with ct1:
            top_fans_count = st.number_input(
                t("data_wrapped.field_fans_count", "Nombre de fans"),
                min_value=0,
                value=_prefill(g('top_fans_count'), int), step=1,
                help=t("data_wrapped.fans_count_help",
                       "Fans qui vous avaient en top artiste, ex: 11")
            )
        with ct2:
            top_fans_rank = st.number_input(
                t("data_wrapped.field_fans_rank", "Rang (vous dans leur top N)"),
                min_value=1,
                value=_prefill(g('top_fans_rank'), int), step=1,
                help=t("data_wrapped.fans_rank_help", "Ex: 5 = vous étiez dans leur top 5")
            )

        st.markdown("---")
        if st.button(t("data_wrapped.btn_save", "💾 Enregistrer"), type="primary"):
            # An empty field is written as NULL — every column is NULLABLE — and a
            # typed 0 stays 0. A form with nothing typed writes nothing at all.
            values = {
                'listeners': listeners, 'streams': streams,
                'hours_listened': hours_listened, 'countries': countries,
                'listener_gain_pct': listener_gain_pct,
                'stream_gain_pct': stream_gain_pct,
                'save_gain_pct': save_gain_pct,
                'playlist_add_gain_pct': playlist_add_gain_pct,
                'saves': saves, 'playlist_adds': playlist_adds,
                'top_fans_count': top_fans_count,
                'top_fans_rank': top_fans_rank,
            }
            if all(v is None for v in values.values()):
                st.warning(t(
                    "data_wrapped.nothing_to_save",
                    "Rien à enregistrer : aucun champ n'est rempli. Un champ laissé "
                    "vide reste vide en base — il ne devient pas un zéro."))
            else:
                try:
                    _upsert_wrapped(db, target_artist_id, int(year), values)
                    flash(t("data_wrapped.save_success",
                            "✅ Données {year} enregistrées.").format(year=int(year)))
                    st.rerun()
                except Exception as e:
                    st.error(t("data_wrapped.error_generic",
                               "Erreur : {err}").format(err=e))

    # ── Évolution, sous la saisie ───────────────────────────────────────
    st.markdown("---")
    _tab_charts(artist_options)

    # ── LA SUPPRESSION, TOUT EN BAS — 2026-09-22 ────────────────────────
    #
    # Demandé en regardant l'écran : « déplace supprimer une année tout en bas
    # après les graphiques d'évolution ». Elle vivait sous le formulaire de saisie,
    # donc un geste destructeur était le voisin immédiat d'un geste de création —
    # et il fallait passer devant lui pour atteindre les courbes.
    #
    # En bas, l'ordre de la page raconte : je saisis, je regarde ce que ça donne, et
    # si je me suis trompé je corrige. La suppression reste dans un `st.expander`
    # REFERMÉ : c'est le seul geste irréversible de cette page.
    st.markdown("---")
    with st.expander(t("data_wrapped.expander_delete", "🗑️ Supprimer une année")):
        del_artist_id = _artiste(artist_options, "del_artist")
        del_year = st.number_input(
            t("data_wrapped.year_label", "Année"),
            min_value=2015, max_value=datetime.now().year,
            value=datetime.now().year - 1, step=1, key="del_year"
        )
        if st.button(t("data_wrapped.btn_delete", "🗑️ Supprimer"), type="secondary"):
            try:
                _delete_wrapped(db, del_artist_id, int(del_year))
                flash(t("data_wrapped.delete_success",
                        "Année {year} supprimée.").format(year=int(del_year)))
                st.rerun()
            except Exception as e:
                st.error(t("data_wrapped.error_generic",
                           "Erreur : {err}").format(err=e))

    # ⚠️ LE TABLEAU RÉCAP A ÉTÉ RETIRÉ le 2026-09-22, demandé en regardant l'écran :
    # « supprime le tableau récap car déjà la visualisation via graphique ».
    #
    # C'était une section « Données brutes » de treize colonnes — listeners, streams,
    # heures, pays, saves, playlist adds, super-fans, et les quatre pourcentages de
    # gain — plus son propre sélecteur d'artiste. Chacune de ces colonnes est déjà une
    # COURBE au-dessus : le tableau redisait en chiffres ce que les figures montrent
    # en formes, sur une page dont la valeur est justement de voir l'évolution.
    #
    # ⚠️ CE QUI EST PERDU, et le dire est le point : la valeur EXACTE de chaque année.
    # Une courbe se lit à l'œil, un tableau se lit au chiffre — et la saisie
    # elle-même sert de relecture, puisqu'elle recharge l'année choisie. Le petit
    # tableau des super-fans SURVIT, parce qu'il porte `top_fans_rank`, que AUCUNE
    # figure ne dessine.


def show():
    # « Spotify Wrapped (bilan annuel) » depuis le 2026-09-22 : « Data Wrapped »
    # était le nom du fichier, pas celui de la chose. Ce qu'on saisit ici est le
    # Wrapped for Artists de Spotify, une fois l'an.
    st.title(t("data_wrapped.title", "🎁 Spotify Wrapped (bilan annuel)"))
    st.caption(t(
        "data_wrapped.intro",
        "Les métriques annuelles de ton **Spotify Wrapped for Artists**, saisies à "
        "la main : elles ne sont dans aucune API. Saisie, puis évolution année par "
        "année, puis les données brutes."
    ))

    db = get_db_connection()
    if db is None:
        st.error(t("data_wrapped.db_unreachable", "Base de données inaccessible."))
        return

    # Les fragments de cette page REUTILISENT cette connexion pendant un rendu
    # complet (~13 ms de poignee SCRAM economises chacun) et n'en ouvrent une que
    # lors d'un rerun de fragment. Libere AVANT `close()` : entre les deux, un
    # fragment verrait une connexion fermee dans la fente.
    from src.dashboard.utils.fragment_db import declare_page_db, release_page_db

    declare_page_db(db)
    try:
        # Resolve artist context — include inactive artists (historical data entry)
        if is_admin():
            artists_df = db.fetch_df(
                "SELECT id, name FROM saas_artists ORDER BY name"
            )
            if artists_df.empty:
                st.warning(t("data_wrapped.no_artist", "Aucun artiste en base."))
                return
            artist_options = {row['name']: row['id'] for _, row in artists_df.iterrows()}
        else:
            aid = get_artist_id()
            # Guard (CLAUDE.md rule #7): a non-admin with no artist_id must never fall
            # through to target_artist_id=None, which _load_wrapped treats as the admin
            # all-tenants query → cross-tenant leak. Stop the session instead.
            if aid is None:
                st.error(t("data_wrapped.session_invalid", "Session invalide."))
                st.stop()
            name_row = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (aid,))
            name = name_row[0][0] if name_row else f"Artiste {aid}"
            artist_options = {name: aid}

        _render_wrapped_body(db, artist_options)

    finally:
        release_page_db()
        db.close()

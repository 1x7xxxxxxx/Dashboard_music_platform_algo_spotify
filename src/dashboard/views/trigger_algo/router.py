"""trigger_algo — router: the slim show() entry point (move-only split)."""
from datetime import date
from datetime import timedelta
from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import smart_period_filter
from src.dashboard.utils.ui import secondary_analyses
from src.utils.track_matching import canonical_song_sql
import streamlit as st
from ._common import (
    _load_lifecycle_benchmark,
    _load_ml_pred,
)
from ._tab_algo_streams import _show_tab_algo_streams
from ._tab_titre import _show_tab_titre
from ._tab_budget_roi import _show_tab_budget_roi
from ._tab_catalogue import _show_tab_catalogue
from ._tab_lifecycle import _show_tab_lifecycle


def show():
    from src.dashboard.auth import require_plan
    if not require_plan('premium'):
        return

    st.title(t("trigger_algo.title", "🚀 Road to Algorithms (J+28)"))
    st.markdown(t("trigger_algo.subtitle",
                  "Suivi ML, budget, ROI et explainabilité des scores algorithmiques."))

    with st.expander(t("trigger_algo.guide_expander",
                       "📖 Comment lire cette page (guide artiste) — à ouvrir une fois"),
                     expanded=False):
        st.markdown(t(
            "trigger_algo.guide_body",
            "Cette page répond à **une seule question** : *« Spotify va-t-il pousser mon "
            "titre tout seul dans ses algorithmes ? »* Les **28 premiers jours** après la "
            "sortie (J+28) sont décisifs — c'est la fenêtre où les algorithmes décident.\n\n"

            "**🎚️ Les 3 algorithmes suivis**\n"
            "- 💎 **Discover Weekly (DW)** — playlist perso hebdomadaire envoyée à des auditeurs "
            "qui ne te connaissent PAS encore. C'est la découverte pure, le Graal pour gagner de "
            "nouveaux fans. La porte la plus dure à ouvrir.\n"
            "- 📡 **Release Radar (RR)** — playlist hebdo poussée à **tes abonnés** à chaque "
            "sortie. Plus facile à déclencher (ils te suivent déjà), mais touche surtout ton "
            "audience existante.\n"
            "- 📻 **Radio** — flux algorithmique « infini » qui enchaîne des titres similaires. "
            "Signe que Spotify te juge « fiable » pour nourrir ses recommandations. Demande le "
            "plus de volume de streams.\n\n"

            "**🔢 Les 2 chiffres à NE PAS confondre**\n"
            "- **DW % / RR % / Radio %** = probabilité **absolue et calibrée** de déclenchement "
            "(50 % = vraiment 1 chance sur 2). C'est LA mesure de ta vraie chance. Bandes de "
            "décision : 🔴 < 20 % **STOP** · 🟠 20–50 % **OPTIMISER** · 🟢 ≥ 50 % **SCALER**.\n"
            # ⚠️ LE « SCORE /20 » EST RETIRÉ — 2026-09-22. Il étirait en min-max sur
            # une échelle de 20 un écart de probabilité de 0,36 point, mesuré sur les
            # dix titres de l'artiste 1. Il fabriquait l'apparence d'un classement à
            # partir d'une donnée qui n'en portait aucun — c'est-à-dire exactement ce
            # qu'il prétendait offrir. Sa prose le disait déjà : « un titre peut être
            # 20/20 avec seulement 10 % de proba réelle ».
            "- ⚠️ **Une probabilité proche de 6,5 % (DW/RR) ou 10,7 % (Radio) est le "
            "PLANCHER de la calibration** : elle veut dire que le modèle a rendu zéro, "
            "pas qu'il hésite. Deux titres posés dessus ne se comparent pas.\n\n"

            "**🧭 Les notions clés**\n"
            "- **Popularity Index (0–100)** — la « note de popularité » Spotify du titre. C'est "
            "la porte d'entrée : chaque algo a un PI minimum. Plus ton PI monte, plus les portes "
            "s'ouvrent.\n"
            "- **Seuils elbow (28j)** — volume d'algo-streams **générés par la playlist "
            "elle-même** qui marque le *début* d'un trigger : **~130 (RR)**, **~137 (DW)**, "
            "**~639 (Radio)**. C'est le minimum que la playlist produit une fois déclenchée — "
            "**pas** le nombre de streams à générer soi-même pour la déclencher.\n"
            "- **Velocity (momentum)** — vitesse d'accélération récente des streams. Un titre qui "
            "monte vite est favorisé ; un titre à plat stagne.\n"
            "- **Discovery Mode** — option Spotify (commission sur tes royalties) qui force "
            "l'entrée en Radio. À activer/désactiver selon le contexte (onglet Suivi "
            "Algorithmes).\n\n"

            "**🗂️ Les onglets**\n"
            "- 🎯 **Vue Globale** — métriques du titre et probabilités.\n"
            "- 📊 **Suivi Algorithmes** — verdict, leviers d'action, trajectoire J+28, portes par PI.\n"
            "- 💰 **Budget & ROI** — combien dépenser en pub et quand.\n"
            "- 🔍 **Explainabilité** — *pourquoi* le modèle donne ce score (SHAP, leviers).\n"
            "- 📈 **Modèle** — fiabilité technique du modèle ML.\n"
            "- 📉 **Cycle de vie & Benchmark** — où en est ton titre vs les autres, dans le temps.\n"
            # ⚠️ CETTE LISTE EN ANNONÇAIT SIX POUR SEPT ONGLETS (corrigé 2026-09-22).
            # L'absent était « Streams algos générés » — le seul onglet qui parle d'un
            # fait CONSTATÉ (ce qu'une playlist a réellement rapporté) plutôt que
            # d'une prédiction. Le guide envoyait donc le lecteur partout sauf là.
            "- 📈 **Streams algos générés** — ce que chaque playlist t'a réellement rapporté.\n\n"

            "⚠️ **Limite honnête** : le modèle prédit BIEN *si* un titre va déclencher "
            "(classification, AUC ~0.92), mais MAL *combien* de streams il fera (le volume n'est "
            "pas fiable). **Fie-toi aux %, pas aux prévisions de volume en €.**"
        ))

    with view_session() as (db, artist_id):
        # Track list — ordered by release_date DESC from tracks table.
        # S4A CSVs replace '?' with '_' in song names, so the JOIN uses REPLACE().
        try:
            if artist_id:
                tracks = db.fetch_df(
                    f"""SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s AND artist_id = %s GROUP BY song) t
                       LEFT JOIN tracks tk ON {canonical_song_sql('tk.track_name')} = t.song
                                              AND tk.saas_artist_id = %s
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%", artist_id, artist_id)
                )["song"].tolist()
            else:
                tracks = db.fetch_df(
                    f"""SELECT t.song
                       FROM (SELECT song FROM s4a_song_timeline
                             WHERE song NOT ILIKE %s GROUP BY song) t
                       LEFT JOIN tracks tk ON {canonical_song_sql('tk.track_name')} = t.song
                       ORDER BY tk.release_date DESC NULLS LAST, t.song""",
                    ("%1x7xxxxxxx%",)
                )["song"].tolist()
        except Exception:
            tracks = []

        if not tracks:
            st.warning(t("trigger_algo.no_timeline", "Aucune donnée de timeline disponible."))
            return

        # Global selectors
        today = date.today()
        sel1, sel2 = st.columns([2, 2])
        with sel1:
            selected_track = st.selectbox(t("trigger_algo.sel_track", "🎵 Titre"), tracks)

        # Fetch release_date of selected track via tracks table (same '?' → '_' normalisation).
        # tracks is tenant-scoped by saas_artist_id (migration 039); admin (None) = no filter.
        _track_frag = "AND saas_artist_id = %s" if artist_id else ""
        _track_params = (artist_id,) if artist_id else ()
        try:
            rd_rows = db.fetch_query(
                f"SELECT release_date FROM tracks WHERE {canonical_song_sql('track_name')} = %s {_track_frag} LIMIT 1",
                (selected_track, *_track_params)
            )
            track_release_date = rd_rows[0][0] if rd_rows and rd_rows[0][0] else (today - timedelta(days=28))
        except Exception:
            track_release_date = today - timedelta(days=28)

        with sel2:
            # LE FILTRE PARTAGÉ — 2026-09-21. Ce bloc portait SIX préréglages
            # écrits à la main (« 28 derniers jours », « Mois précédent »,
            # « Mois / Année », « Personnalisé »…), chacun avec son propre calcul
            # de bornes, plus deux sous-sélecteurs mois/année et un `date_input`
            # de repli — une soixantaine de lignes qui refaisaient
            # `smart_period_filter`, en moins bien.
            #
            # Ce qu'il perdait, et qui n'est pas cosmétique : la borne sur
            # l'ÉTENDUE RÉELLE des données. « 28 derniers jours » sur un titre
            # dont l'import S4A s'arrête six mois plus tôt rend une page vide, et
            # l'artiste ne peut pas savoir si c'est la donnée ou son choix.
            # `smart_period_filter` dérive ses choix de `_data_span`, donc ne
            # propose jamais une fenêtre sans donnée.
            #
            # L'ancre reste la sortie DU TITRE sélectionné — la plus précise
            # disponible ici — et le défaut est « depuis la dernière release »,
            # comme partout ailleurs.
            #
            # ⚠️ La table est la vue OR, pas `s4a_song_timeline` : cette dernière
            # porte la ligne « Total » des CSV, et son étendue l'inclurait.
            window = smart_period_filter(
                db, table="v_s4a_song_daily", date_column="day",
                artist_id=artist_id, key=f"trigger_algo_{selected_track}",
                latest_release=track_release_date,
                default_override="last_release",
            )
        date_from, date_to = window.start, window.end

        # Load ML prediction + global benchmark once — shared across tabs
        ml_pred = _load_ml_pred(db, selected_track, artist_id)
        benchmark_df = _load_lifecycle_benchmark(db)

        # ⚠️ L'ONGLET 1 S'OUVRE SUR LE CATALOGUE, PLUS SUR UN TITRE — 2026-09-22.
        # « Où en sont mes titres » répond à la question qu'on se pose en arrivant :
        # lequel je pousse. « Vue Globale » ouvrait sur onze figures d'UN titre,
        # classé par un `Score /20` qui étirait 0,36 point de probabilité sur une
        # échelle de 20. Le catalogue est classé par l'avancement vers la porte la
        # plus proche — mesuré de 0,7 % à 98,9 % sur les dix mêmes titres.
        # ⚠️ SEPT ONGLETS → QUATRE. « 📈 Modèle » et « 🔍 Explainabilité » sont
        # partis dans la page admin `ml_performance` : ils exposaient AUC, F1,
        # log-odds, drift et LIME à un artiste, et leur figure principale était vide
        # par construction sur ce catalogue (`streams_7d = 0` sur les dix titres).
        # Le coach et la sensibilité locale, eux, sont REMONTÉS en première ligne de
        # « Ce titre » — c'est ce qu'un artiste vient chercher.
        tab1, tab2, tab3, tab4 = st.tabs([
            t("trigger_algo.tab_catalogue", "🎯 Où en sont mes titres"),
            t("trigger_algo.tab_titre", "🎧 Ce titre : ce qu'il reste à faire"),
            t("trigger_algo.tab_realise", "📈 Ce qui s'est vraiment passé"),
            t("trigger_algo.tab_budget", "💰 Budget & ROI"),
        ])
        with tab1:
            _show_tab_catalogue(db, artist_id)
        with tab2:
            _show_tab_titre(db, selected_track, artist_id, ml_pred)
        with tab3:
            # « Ce qui s'est vraiment passé » : les streams réellement produits par
            # chaque playlist, puis le cycle de vie replié. Le seul onglet qui parle
            # d'un fait CONSTATÉ — et le seul qui puisse un jour fermer la boucle
            # d'apprentissage, aujourd'hui vide (`s4a_song_algo_outcomes` : 0 ligne).
            _show_tab_algo_streams(db, selected_track, artist_id)
            with secondary_analyses(t("trigger_algo.lifecycle_folded",
                                      "📉 Cycle de vie & benchmark de cohorte")):
                _show_tab_lifecycle(db, selected_track, artist_id,
                                    release_date=track_release_date,
                                    benchmark_df=benchmark_df)
        with tab4:
            _show_tab_budget_roi(db, selected_track, artist_id, date_from, date_to,
                                 ml_pred=ml_pred)

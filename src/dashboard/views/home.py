"""Page d'accueil — KPI globaux, fraîcheur des sources, statut des pipelines."""
import html as _html
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t
from src.dashboard.auth import tenant_scope
from src.dashboard.utils.navigation import goto
from src.dashboard.utils.status_matrix import render_status_matrix
from src.dashboard.utils.airflow_monitor import AirflowMonitor, cached_last_run_per_dag
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
    get_total_streams_s4a, get_total_views_youtube,
    get_total_plays_soundcloud, get_total_plays_apple,
    get_instagram_followers,
)


def _freshness_badge(label, icon, last_dt):
    """Génère une carte de fraîcheur HTML."""
    emoji, color, age_label = freshness_status(last_dt)
    date_str = last_dt.strftime("%d/%m %H:%M") if last_dt else "—"
    return f"""
    <div style="border:1px solid {color}; border-radius:8px; padding:8px 12px;
                background:{color}18; text-align:center; min-width:110px;">
        <div style="font-size:1.3em;">{icon}</div>
        <div style="font-weight:600; font-size:0.85em;">{label}</div>
        <div style="font-size:0.75em; color:{color};">{emoji} {age_label}</div>
        <div style="font-size:0.65em; color:#888;">{date_str}</div>
    </div>
    """


def _section_freshness(db, artist_id):
    st.subheader(t("home.freshness_header", "📡 Fraîcheur des données"))
    st.caption(t(
        "home.freshness_caption",
        "🔄 Sources **API** (Spotify, YouTube, SoundCloud, Instagram, Meta Ads) : collecte "
        "**automatique chaque jour** pour chaque artiste. Sources **fichier** (Spotify for "
        "Artists, Apple Music, distributeurs) : mises à jour **à chaque import CSV** "
        "(dossier surveillé toutes les 15 min)."
    ))
    freshness = get_source_freshness(db, artist_id)
    cols = st.columns(len(freshness))
    for col, (label, info) in zip(cols, freshness.items()):
        emoji, color, age_label = freshness_status(info['last_dt'])
        date_str = info['last_dt'].strftime("%d/%m %H:%M") if info['last_dt'] else "—"
        with col:
            # HIGH-07: html.escape() on all interpolated values — defence-in-depth
            # against stored XSS if a DB-sourced value ever reaches these variables.
            st.markdown(
                f"""<div style="border:1px solid {_html.escape(color)}; border-radius:8px;
                    padding:8px 6px; background:{_html.escape(color)}18; text-align:center;">
                    <div style="font-size:1.2em;">{_html.escape(str(info['icon']))}</div>
                    <div style="font-weight:600; font-size:0.8em; white-space:nowrap;">{_html.escape(label)}</div>
                    <div style="font-size:0.75em; color:{_html.escape(color)};">{_html.escape(emoji)} {_html.escape(age_label)}</div>
                    <div style="font-size:0.65em; color:#888;">{_html.escape(date_str)}</div>
                </div>""",
                unsafe_allow_html=True
            )


def _section_streams(db, artist_id):
    st.subheader(t("home.streams_header", "🎧 Streams totaux"))
    s4a = get_total_streams_s4a(db, artist_id)
    yt = get_total_views_youtube(db, artist_id)
    sc = get_total_plays_soundcloud(db, artist_id)
    apple = get_total_plays_apple(db, artist_id)
    ig = get_instagram_followers(db, artist_id)
    ig_count = ig['followers'] if ig else 0
    grand_total = s4a + yt + sc + apple  # Instagram followers ≠ streams, not summed

    # Quatre zéros ne disent pas « pas encore », ils disent « rien ». Le premier jour,
    # c'est faux et décourageant : la collecte automatique tourne le matin, et un
    # déclenchement manuel ramène des chiffres en ~2 min. Une phrase DATÉE vaut mieux
    # qu'un tableau vide — c'est le plus gros écart attente/réalité du parcours.
    if grand_total == 0 and ig_count == 0:
        st.info(t(
            "home.no_data_yet",
            "🕐 **Tes premiers chiffres ne sont pas encore là — c'est normal.**\n\n"
            "La collecte automatique tourne **chaque matin entre 9 h et 10 h** (heure "
            "de Paris) et remplit cette page toute seule. Tu n'as rien à faire.\n\n"
            "Tu ne veux pas attendre demain ? Le bouton **🚀 Lancer TOUTES les "
            "collectes** dans la barre latérale ramène tes chiffres en ~2 minutes."))
        st.caption(t("home.no_data_hint",
                     "Si rien n'arrive après une collecte, la page **🚦 Santé "
                     "onboarding** dit quelle source ne répond pas, et pourquoi."))
        return

    st.markdown(
        f"""<div style="text-align:center; padding:16px; background:#f0f2f6;
            border-radius:10px; margin-bottom:16px;">
            <div style="color:#555; font-size:1em; font-weight:600;">{t("home.total_all_platforms", "🎧 Total streams toutes plateformes")}</div>
            <div style="font-size:3em; color:#1DB954; font-weight:800;">{grand_total:,}</div>
        </div>""",
        unsafe_allow_html=True
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🎵 Spotify S4A", f"{s4a:,}")
    c2.metric("🎬 YouTube", f"{yt:,}")
    c3.metric("☁️ SoundCloud", f"{sc:,}")
    c4.metric("🍎 Apple Music", f"{apple:,}")
    # Instagram followers — colour-differentiated from stream platforms (rose Instagram)
    c5.markdown(
        f"""<div style="border:1px solid #E4405F; background:#E4405F18;
            border-radius:8px; padding:10px 12px; text-align:center;
            margin-top:4px;">
            <div style="color:#666; font-size:0.85em;">{t("home.ig_followers", "📸 Followers Instagram")}</div>
            <div style="font-size:1.75em; color:#E4405F; font-weight:700;">{ig_count:,}</div>
        </div>""",
        unsafe_allow_html=True
    )


_DAG_LABELS = {
    "spotify_api_daily":        ("🎵", "Spotify API"),
    "youtube_daily":            ("🎬", "YouTube"),
    "soundcloud_daily":         ("☁️", "SoundCloud"),
    "instagram_daily":          ("📸", "Instagram"),
    "meta_ads_api_daily":       ("📊", "Meta Ads"),
    "ml_scoring_daily":         ("🤖", "ML Scoring"),
    "data_quality_check":       ("🔍", "Qualité données"),
}

_STATE_COLOR = {
    "success": ("#00CC96", "🟢"),
    "failed":  ("#EF553B", "🔴"),
    "running": ("#636EFA", "🔵"),
    "queued":  ("#FFA500", "🟡"),
}


def _section_onboarding(db, artist_id: int) -> None:
    """Brick 29 — Onboarding progress tracker for new artists."""
    # La définition des quatre étapes vit dans `utils.setup_completion`, pas ici.
    # Elle était écrite ICI et l'aiguillage d'accueil en posait une AUTRE (« l'artiste
    # n'a-t-il rien branché du tout ? ») : deux surfaces, même question, réponses
    # opposées dès la deuxième connexion. Une seule règle, deux lecteurs.
    from src.dashboard.utils.setup_completion import STEP_LABELS, read_setup_state

    state = read_setup_state(db, artist_id, st.session_state.get('user_id'))
    if not state.steps:
        return

    steps = [(s.done, STEP_LABELS[s.key](), s.page) for s in state.steps]
    completed = state.done_count
    all_done = state.complete

    if all_done:
        st.markdown(t("home.onboarding_done_header", "#### ✅ Mise en route — configuration terminée"))
        st.success(t("home.onboarding_done", "Toutes les étapes de mise en route sont complètes. 🎉"))
    else:
        st.markdown(t("home.onboarding_progress",
                      "#### 🚀 Mise en route — {done}/{total} étapes complétées").format(
                          done=completed, total=len(steps)))
        st.progress(completed / len(steps))
        # Ce que la coche MESURE. Un artiste en test a cliqué « Connecter ma
        # sélection », est arrivé sur la page, et s'est étonné que la case reste
        # vide : « ça ne coche pas le rond de données credentials API, c'est
        # confus ». La case suit l'ACTION, pas la visite — la cocher à l'arrivée
        # dirait que c'est fait alors que rien n'est enregistré.
        st.caption(t("home.onboarding_ticks_on_action",
                     "Une étape se coche quand l'action est **faite**, pas quand la "
                     "page est ouverte."))

    # Les quatre étapes NOMMAIENT leur destination sans y mener : la clé de page était
    # liée à `_page` puis jetée, et les lignes étaient du `st.markdown`. Un artiste en
    # test l'a dit ainsi — « lien cliquable mise en route dans la page d'accueil ».
    # Few (*Information Dashboard Design*) : un tableau de bord sert de rampe de
    # lancement, on clique la donnée elle-même. Une étape faite reste du texte : il n'y
    # a rien à y faire, et un bouton inutile est du bruit.
    for idx, (done, label, page_key) in enumerate(steps):
        if done:
            st.markdown(f"✅ {label}")
            continue
        # L'étape « lancer ta première collecte » NOMMAIT le geste et envoyait vers une
        # autre page pour le faire ; le bouton, lui, est dans la barre latérale. Deux
        # endroits pour une action, c'est une consigne — et une consigne est ce qu'on
        # écrit quand le bouton est ailleurs. Elle le fait maintenant elle-même.
        if page_key == "onboarding" and idx == len(steps) - 1:
            if st.button(f"⬜ {label}", key=f"home_step_{idx}",
                         use_container_width=True, type="primary"):
                _launch_collections()
            continue
        if st.button(f"⬜ {label}", key=f"home_step_{idx}",
                     use_container_width=True):
            goto(page_key)

    # One compact line of per-platform boxes, only while something is still amber or
    # red. The steps above are STAGES ("import a CSV"); this is per PLATFORM, which
    # is the axis an artist actually asks about — "is my SoundCloud working?".
    if not all_done:
        st.caption(t("home.matrix_caption",
                     "Par plateforme — survole une case pour le détail :"))
        render_status_matrix(db, artist_id, compact=True, allow_probe=False,
                             key_suffix="home")

    st.markdown("---")


def _launch_collections() -> None:
    """Déclenche les collectes de CE locataire, depuis l'étape qui les nomme."""
    from src.dashboard.utils.collection_trigger import trigger_all_collections
    from src.dashboard.utils.collection_progress import (
        remember_not_launched, remember_runs)

    try:
        from src.utils.airflow_trigger import AirflowTrigger
        from src.dashboard.app import COLLECTION_DAGS      # noqa: PLC0415
    except Exception:      # noqa: BLE001 — hors app : le bouton ne doit pas casser la page
        st.warning(t("home.launch_unavailable",
                     "⚠️ Le déclenchement n'est pas disponible ici. Utilise le bouton "
                     "**🚀 Lancer TOUTES les collectes** dans la barre latérale."))
        return

    artist_id = tenant_scope()
    with st.status(t("home.launching", "Lancement des collectes…"), expanded=False):
        launched, not_launched = trigger_all_collections(
            artist_id, AirflowTrigger(), COLLECTION_DAGS)
    remember_runs(launched)
    remember_not_launched(not_launched)
    if launched:
        st.success(t("home.launched",
                     "🚀 Collecte lancée — tes premiers chiffres arrivent dans "
                     "~2 minutes. Recharge la page pour les voir.").format())
    if not_launched:
        st.error(t("home.launch_refused",
                   "❌ {n} collecte(s) refusée(s) : {why}").format(
                       n=len(not_launched),
                       why=" · ".join(f"{k} — {v}" for k, v in not_launched.items())))


def _section_dag_status():
    """Résumé du dernier run de chaque DAG. **Admin seulement.**

    Cette section montre l'état Airflow de TOUTE LA FLOTTE : `get_dag_list()` ne
    prend pas d'`artist_id`, et il n'en existe pas de version par locataire — un run
    de DAG appartient à l'infrastructure, pas à un artiste.

    Rapporté par un artiste en test le 2026-08-30, sur un compte créé la minute
    d'avant, sans une seule credential : « DAG spotify_api_daily — 🟢 success —
    dernier run 15:27 ». Il a demandé si c'était le bug des données d'un autre.
    Ce n'en est pas un — aucune donnée d'artiste ne fuit — mais l'effet est pire
    qu'inutile : un vert affiché à quelqu'un qui n'a rien connecté lui dit que sa
    collecte a fonctionné.

    Sa remarque suivante tranche le sort de la section : « cette ligne n'a rien à
    faire là, on s'en fout ici vu qu'on a déjà l'état des plateformes ». La matrice
    Configuré / Répond / Données répond à SA question, par locataire. Celle-ci
    répond à la mienne.
    """
    from src.dashboard.auth import is_admin
    if not is_admin():
        return

    st.subheader(t("home.dag_header", "🚦 Statut des pipelines"))

    monitor = AirflowMonitor()
    try:
        dag_list = monitor.get_dag_list()
    except Exception:
        st.warning(t("home.airflow_unreachable", "API Airflow inaccessible — démarrer Docker."))
        return

    if not dag_list:
        st.warning(t("home.no_dags", "Aucun DAG trouvé. Vérifier que Airflow est lancé."))
        return

    # Single batch call for every DAG's latest run (was N+1: one call per DAG).
    # Cached 60 s: 16 HTTP round-trips, re-paid on every widget interaction.
    last_states = cached_last_run_per_dag()
    rows = []
    for dag_id in dag_list:
        r = last_states.get(dag_id)
        if not r:
            rows.append((dag_id, None, None, None))
        else:
            rows.append((dag_id, r['state'], r['start_date'], r['end_date']))

    # Grille responsive : 5 colonnes
    n_cols = 5
    cols = st.columns(n_cols)
    for i, (dag_id, state, start, end) in enumerate(rows):
        icon_dag, label = _DAG_LABELS.get(dag_id, ("⚙️", dag_id))
        label = t(f"home.dag.{dag_id}", label)
        color, state_icon = _STATE_COLOR.get(state, ("#888888", "⚫"))
        state_label = state or t("home.never_run", "jamais lancé")
        date_str = start[:16].replace("T", " ") if start else "—"

        with cols[i % n_cols]:
            st.markdown(
                f"""<div style="border:1px solid {color};border-radius:8px;
                    padding:8px 10px;background:{color}18;text-align:center;margin-bottom:8px;">
                    <div style="font-size:1.4em">{icon_dag}</div>
                    <div style="font-weight:600;font-size:0.8em;white-space:nowrap">{label}</div>
                    <div style="font-size:0.85em">{state_icon} {state_label}</div>
                    <div style="font-size:0.65em;color:#888">{date_str}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def show():
    st.title(t("home.title", "🎵 streaMLytics — Dashboard plateformes musicales"))
    st.markdown("---")

    artist_id = tenant_scope()  # None = admin only, never a stray artist

    with project_db() as db:
        try:
            # Onboarding tracker — only shown to artists with incomplete setup
            if artist_id is not None:
                _section_onboarding(db, artist_id)

            _section_streams(db, artist_id)
            st.markdown("---")
            # PDF shortcut removed here — redundant with the dedicated "📄 Export PDF" page.
            _section_dag_status()
            st.markdown("---")
            _section_freshness(db, artist_id)
        except Exception as e:
            st.error(t("home.display_error", "Erreur d'affichage : {err}").format(err=e))

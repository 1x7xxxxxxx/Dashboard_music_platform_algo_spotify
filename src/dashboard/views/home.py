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
    """Le filtre en haut au centre, la courbe à gauche, les chiffres à droite.

    Disposition demandée le 2026-09-08. Elle n'est pas qu'esthétique : la courbe est ce
    qu'on regarde, les tuiles ce qu'on vérifie. Côte à côte, elles répondent à la même
    période sans qu'on ait à faire défiler entre les deux — c'était le vrai défaut de
    la version empilée, où le filtre était à un écran de la figure qu'il commande.
    """
    from src.dashboard.utils import date_range
    from src.dashboard.utils.platform_timeseries import (
        daily_streams_by_platform, measured_days,
    )

    st.subheader(t("home.streams_header", "🎧 Tes chiffres"))

    # LE FILTRE, EN HAUT AU CENTRE. Un seul propriétaire du réglage : tout ce qui suit
    # le LIT.
    _l, _mid, _r = st.columns([1, 3, 1])
    with _mid:
        range_key = date_range.render_selector()
    since, until = date_range.bounds(range_key)

    series = daily_streams_by_platform(db, artist_id)
    ig = get_instagram_followers(db, artist_id)
    ig_count = ig['followers'] if ig else 0

    if since is None:
        s4a = get_total_streams_s4a(db, artist_id)
        yt = get_total_views_youtube(db, artist_id)
        sc = get_total_plays_soundcloud(db, artist_id)
        apple = get_total_plays_apple(db, artist_id)
    else:
        def _sum(pkey):
            # ZÉRO MESURE ≠ ZÉRO ÉCOUTE. Sans ce test, une plateforme non collectée
            # sur la période afficherait « 0 », ce qui affirme qu'il ne s'est rien
            # passé — alors qu'on n'a pas regardé.
            if not measured_days(series, pkey, since, until):
                return None
            return sum(v for d, v in series.get(pkey, []) if since <= d <= until)
        s4a, yt, sc = _sum("spotify"), _sum("youtube"), _sum("soundcloud")
        # Apple n'a pas de résolution quotidienne, mais elle a des RELEVÉS datés
        # depuis la migration 093 : sur une période qui en contient deux, l'écart est
        # calculable. `None` tant qu'il n'y en a qu'un.
        from src.dashboard.utils.platform_timeseries import apple_period_plays
        apple = apple_period_plays(db, artist_id, since, until)
    grand_total = sum(v for v in (s4a, yt, sc, apple) if v)

    if not grand_total and not ig_count:
        st.info(t(
            "home.no_data_yet",
            "🕐 **Tes premiers chiffres ne sont pas encore là — c'est normal.**\n\n"
            "La collecte automatique tourne **chaque matin entre 5 h et 11 h** (heure "
            "de Paris) et remplit cette page toute seule. Tu n'as rien à faire.\n\n"
            "Elle démarre aussi d'elle-même dès que tu enregistres des identifiants."))
        st.caption(t("home.no_data_hint",
                     "Si rien n'arrive après une collecte, la page **🚦 Santé "
                     "onboarding** dit quelle source ne répond pas, et pourquoi."))
        return

    left, right = st.columns([3, 2], gap="large")
    with left:
        _render_trend(series, since, until, range_key, artist_id)
    with right:
        _render_totals(db, artist_id, series, since, until,
                       s4a, yt, sc, apple, ig_count, grand_total)

    st.caption(date_range.RANGE_NOTE)


def _fmt(value) -> str:
    """Un nombre, ou « — » quand rien n'a été mesuré. Jamais « 0 » pour une absence."""
    return "—" if value is None else f"{value:,}"


def _render_totals(db, artist_id, series, since, until,
                   s4a, yt, sc, apple, ig_count, grand_total) -> None:
    """La colonne de droite : le total, les quatre plateformes, les abonnés."""
    from src.dashboard.utils.platform_timeseries import followers_change

    st.markdown(
        f"""<div style="text-align:center; padding:14px; background:#f0f2f6;
            border-radius:10px; margin-bottom:12px;">
            <div style="color:#555; font-size:0.95em; font-weight:600;">{t("home.total_all_platforms", "🎧 Total streams toutes plateformes")}</div>
            <div style="font-size:2.4em; color:#1DB954; font-weight:800;">{grand_total:,}</div>
        </div>""",
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    c1.metric("🎵 Spotify S4A", _fmt(s4a))
    c2.metric("🎬 YouTube", _fmt(yt))
    c3, c4 = st.columns(2)
    c3.metric("☁️ SoundCloud", _fmt(sc))
    # APPLE N'A QU'UN RELEVÉ PAR DÉPÔT DE CSV, et pour l'instant un seul en tout.
    # Le message le dit plutôt que d'annoncer une impossibilité de principe : au
    # deuxième CSV, la comparaison de deux relevés devient possible.
    from src.dashboard.utils.platform_timeseries import apple_snapshot_count
    c4.metric("🍎 Apple Music", _fmt(apple),
              help=None if apple is not None else t(
                  "home.apple_no_window",
                  "Apple Music ne fournit pas de série quotidienne : chaque dépôt de "
                  "CSV est un relevé daté, et l'écart se calcule entre deux relevés. "
                  "Tu en as **{n}** pour l'instant — au prochain dépôt à une autre "
                  "date, ce chiffre se remplira. « Depuis le début » affiche le total."
              ).format(n=apple_snapshot_count(db, artist_id)))

    # LES ABONNÉS INSTAGRAM SONT UN ÉTAT, pas un flux : on ne les additionne pas sur
    # une période, on regarde de combien ils ont bougé. Demandé le 2026-09-08.
    change = followers_change(db, artist_id, since, until)
    if change is None:
        delta_html = ('<div style="font-size:0.75em; color:#888;">'
                      + t("home.ig_no_change", "évolution : pas assez de relevés")
                      + '</div>')
    else:
        _first, _last, diff = change
        sign = "+" if diff > 0 else ""
        colour = "#00A870" if diff > 0 else ("#C0392B" if diff < 0 else "#888")
        delta_html = (f'<div style="font-size:0.9em; color:{colour}; font-weight:700;">'
                      f'{sign}{diff:,} ' + t("home.ig_delta", "sur la période") + '</div>')
    st.markdown(
        f"""<div style="border:1px solid #E4405F; background:#E4405F18;
            border-radius:8px; padding:10px 12px; text-align:center; margin-top:8px;">
            <div style="color:#666; font-size:0.85em;">{t("home.ig_followers", "📸 Followers Instagram")}</div>
            <div style="font-size:1.75em; color:#E4405F; font-weight:700;">{ig_count:,}</div>
            {delta_html}
        </div>""",
        unsafe_allow_html=True
    )


def _render_trend(series, since, until, range_key, artist_id) -> None:
    """La colonne de gauche : l'évolution, sur la même période que les chiffres.

    Chaque valeur est une quantité du JOUR : `platform_timeseries` ramène les compteurs
    cumulatifs (SoundCloud, YouTube) à leur écart quotidien, sans quoi la courbe
    additionnerait des totaux-depuis-toujours à des streams quotidiens.
    """
    from src.dashboard.utils import date_range
    from src.dashboard.utils.platform_chart import (
        render_missing_history_note, render_platform_chart,
    )

    # QUELLES SOURCES TRACER. Toutes par défaut : le filtre sert à ISOLER une
    # plateforme, pas à en cacher. Les cases ne proposent que ce que la période
    # contient — cocher une source qui n'a rien à dire ne montrerait rien et se
    # lirait comme une panne.
    from src.dashboard.utils.platform_timeseries import PLATFORM_LABELS, measured_days
    available = [k for k in PLATFORM_LABELS if measured_days(series, k, since, until)]
    chosen = available
    if len(available) > 1:
        chosen = st.multiselect(
            t("home.trend_sources", "Sources affichées"), available,
            default=available, format_func=lambda k: PLATFORM_LABELS[k],
            key=f"home_trend_sources_{artist_id}",
            label_visibility="collapsed",
            placeholder=t("home.trend_sources_ph", "Toutes les sources")) or available

    if not render_platform_chart(
            series, since=since, until=until, only=chosen,
            title=t("home.trend_title", "Toutes tes plateformes, un seul écran")
            + f" — {date_range.label(range_key)}",
            key=f"home_trend_{artist_id}"):
        st.info(t(
            "home.trend_no_series",
            "Pas encore assez d'historique pour tracer une évolution : il faut au "
            "moins deux journées de collecte consécutives sur une plateforme."))
        return
    # La légende sous la figure et non au-dessus : le titre de la figure dit DÉJÀ ce
    # qu'elle montre et sur quelle période. Le sous-titre « 📈 Évolution par
    # plateforme » qui la coiffait a disparu avec la mise en colonnes — il redisait le
    # titre porté par la figure elle-même, à trois centimètres de lui.
    st.caption(t(
        "home.trend_caption",
        "Écoutes **du jour**, plateforme par plateforme. Un blanc dans la bande veut "
        "dire qu'on n'a pas de mesure ce jour-là — pas zéro écoute."))
    render_missing_history_note()


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

    # LE BANDEAU EST REPLIÉ QUAND LA CONFIGURATION EST FINIE, et déplié tant qu'elle
    # ne l'est pas. Demandé le 2026-09-08.
    #
    # C'est la même information dans les deux cas ; ce qui change est ce qu'elle
    # DEMANDE. Tant qu'il reste une étape, le bandeau est la première chose à faire et
    # il occupe la place ; une fois terminé, il ne réclame rien et n'a plus à pousser
    # les chiffres vers le bas à chaque visite. Le repli n'est pas un masquage : le
    # titre porte le verdict, et on l'ouvre pour revoir le détail.
    header = (t("home.onboarding_done_header",
                "✅ Mise en route — configuration terminée") if all_done
              else t("home.onboarding_progress",
                     "🚀 Mise en route — {done}/{total} étapes complétées").format(
                         done=completed, total=len(steps)))
    with st.expander(header, expanded=not all_done):
        _render_onboarding_body(db, artist_id, steps, completed, all_done)


def _render_onboarding_body(db, artist_id: int, steps, completed: int,
                            all_done: bool) -> None:
    """Le CONTENU du bandeau, extrait pour qu'il puisse être replié.

    Extrait tel quel le 2026-09-08 : le corps n'a pas changé, seul son contenant. Le
    titre, lui, a quitté le corps — il est devenu l'étiquette du repli, sans quoi il
    aurait été écrit deux fois.
    """
    if all_done:
        st.success(t("home.onboarding_done", "Toutes les étapes de mise en route sont complètes. 🎉"))
    else:
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
                         width="stretch", type="primary"):
                _launch_collections()
            continue
        if st.button(f"⬜ {label}", key=f"home_step_{idx}",
                     width="stretch"):
            goto(page_key)

    # One compact line of per-platform boxes, only while something is still amber or
    # red. The steps above are STAGES ("import a CSV"); this is per PLATFORM, which
    # is the axis an artist actually asks about — "is my SoundCloud working?".
    if not all_done:
        st.caption(t("home.matrix_caption",
                     "Par plateforme — survole une case pour le détail :"))
        render_status_matrix(db, artist_id, compact=True, allow_probe=False,
                             key_suffix="home")


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
                     "Elle démarre aussi d'elle-même dès que tu enregistres des identifiants."))
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
    # Pas de filet sous le titre ni sous le bandeau de mise en route. Demandé le
    # 2026-09-08 : « enlève les 2 traits blancs qui entourent mise en route ». Un
    # séparateur sépare deux choses ; celui-ci encadrait un bloc qui porte déjà sa
    # propre bordure d'accordéon, donc il doublait un trait déjà là.
    st.title(t("home.title", "🎵 streaMLytics — Dashboard plateformes musicales"))

    artist_id = tenant_scope()  # None = admin only, never a stray artist

    with project_db() as db:
        try:
            # Onboarding tracker — only shown to artists with incomplete setup
            if artist_id is not None:
                _section_onboarding(db, artist_id)

            _section_streams(db, artist_id)
            # PDF shortcut removed here — redundant with the dedicated "📄 Export PDF" page.
            # Pas de filet avant la fraîcheur : demandé le 2026-09-08, « retire les
            # 2 traits au-dessus de fraîcheur des données ». Les sous-titres suffisent
            # à séparer trois blocs qui ne se ressemblent pas.
            _section_dag_status()
            _section_freshness(db, artist_id)
        except Exception as e:
            st.error(t("home.display_error", "Erreur d'affichage : {err}").format(err=e))

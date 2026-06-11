"""
Vue "Liens & Outils" — Référence opérationnelle pour gérer la plateforme.
Regroupe : URLs externes, commandes Docker/infra, guide credentials, commandes debug.
"""
import os
from datetime import datetime

import streamlit as st

from src.dashboard.auth import is_admin
from src.dashboard.utils.i18n import t

# Service base URLs — env-driven so the admin "Services locaux" links work on a deployed
# VPS (behind the real domain) and not only on localhost. Fallbacks keep local dev intact.
_AIRFLOW_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080").rstrip("/")
_DASHBOARD_URL = os.getenv("APP_BASE_URL", "http://localhost:8501").rstrip("/")
_API_URL = os.getenv("API_BASE_URL", "http://localhost:8502").rstrip("/")


def _card(title: str, body: str):
    st.markdown(
        f"""<div style="background:#1e1e2e;border:1px solid #444;border-radius:8px;
        padding:14px 18px;margin-bottom:10px">
        <b style="color:#cdd6f4">{title}</b><br>
        <span style="color:#a6adc8;font-size:0.92em">{body}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def _link_row(label: str, url: str, note: str = ""):
    cols = st.columns([3, 1])
    with cols[0]:
        st.markdown(f"**{label}**" + (f" — *{note}*" if note else ""))
        st.code(url, language=None)
    with cols[1]:
        st.link_button(t("useful_links.open_btn", "Ouvrir →"), url, width="stretch")
    st.divider()


def _cmd(description: str, command: str):
    st.markdown(f"**{description}**")
    st.code(command, language="bash")


def show():
    if not is_admin():
        st.error(t("useful_links.access_denied", "⛔ Accès réservé à l'administrateur."))
        st.stop()

    st.title(t("useful_links.title", "🔧 Liens & Outils"))
    st.caption(t("useful_links.caption",
                 "Référence opérationnelle — tous les liens et commandes pour gérer la plateforme."))

    tab_ext, tab_local, tab_docker, tab_credentials, tab_debug = st.tabs([
        t("useful_links.tab_external", "🌐 Liens Externes"),
        t("useful_links.tab_local", "🏠 Outils Locaux"),
        t("useful_links.tab_docker", "🐳 Docker & Infra"),
        t("useful_links.tab_credentials", "🔑 Guide Credentials"),
        t("useful_links.tab_debug", "🐛 Debug & Scripts"),
    ])

    # ─────────────────────────────────────────────
    # TAB 1 — LIENS EXTERNES
    # ─────────────────────────────────────────────
    with tab_ext:
        st.subheader(t("useful_links.sec_meta", "Meta / Instagram / Facebook"))
        _link_row("Graph API Explorer", "https://developers.facebook.com/tools/explorer",
                  t("useful_links.note_graph_explorer", "Générer un access token Instagram"))
        _link_row("Débogueur de token", "https://developers.facebook.com/tools/debug/accesstoken",
                  t("useful_links.note_token_debugger",
                    "Vérifier expiration + étendre le token (bouton 'Extend Access Token')"))
        _link_row("Facebook App Settings", "https://developers.facebook.com/apps",
                  t("useful_links.note_fb_app_settings", "App ID + App Secret"))
        _link_row("Meta Business Manager", "https://business.facebook.com",
                  t("useful_links.note_business_manager", "Comptes publicitaires, pages"))
        _link_row("Meta Ads Manager", "https://www.facebook.com/adsmanager",
                  t("useful_links.note_ads_manager", "Campagnes, ad sets, performances"))

        st.subheader(t("useful_links.sec_spotify", "Spotify"))
        _link_row("Spotify Developer Dashboard", "https://developer.spotify.com/dashboard",
                  t("useful_links.note_spotify_dev", "Client ID + Client Secret"))
        _link_row("Spotify for Artists", "https://artists.spotify.com",
                  t("useful_links.note_s4a", "Export CSV (streams, audience, songs)"))
        _link_row("Spotify API Reference", "https://developer.spotify.com/documentation/web-api",
                  t("useful_links.note_spotify_api", "Endpoints, scopes, rate limits"))

        st.subheader(t("useful_links.sec_soundcloud", "SoundCloud"))
        _link_row("SoundCloud Developer Apps", "https://soundcloud.com/you/apps",
                  t("useful_links.note_sc_dev_apps", "Client ID (si accès développeur actif)"))
        _link_row("SoundCloud", "https://soundcloud.com",
                  t("useful_links.note_sc_inspect",
                    "Inspecter client_id via DevTools F12 → Network → filtre 'client_id='"))

        st.subheader(t("useful_links.sec_youtube", "YouTube / Google"))
        _link_row("Google Cloud Console — Credentials", "https://console.cloud.google.com/apis/credentials",
                  t("useful_links.note_gcp_creds", "OAuth 2.0 Client IDs, API Keys"))
        _link_row("YouTube Studio", "https://studio.youtube.com",
                  t("useful_links.note_yt_studio", "Analytics, export données"))
        _link_row("YouTube Data API v3", "https://console.cloud.google.com/apis/library/youtube.googleapis.com",
                  t("useful_links.note_yt_api", "Activer/désactiver l'API"))

        st.subheader(t("useful_links.sec_apple", "Apple Music"))
        _link_row("Apple Music for Artists", "https://artists.apple.com",
                  t("useful_links.note_apple_a4a", "Export CSV Songs Performance"))

        st.subheader(t("useful_links.sec_imusician", "iMusician"))
        _link_row("iMusician Dashboard", "https://www.imusician.pro/app",
                  t("useful_links.note_imusician", "Revenus mensuels à saisir manuellement dans le dashboard"))

        st.subheader(t("useful_links.sec_hypeddit", "Hypeddit"))
        _link_row("Hypeddit", "https://hypeddit.com",
                  t("useful_links.note_hypeddit", "Export CSV campagnes"))

    # ─────────────────────────────────────────────
    # TAB 2 — OUTILS LOCAUX
    # ─────────────────────────────────────────────
    with tab_local:
        st.subheader(t("useful_links.sec_local_services", "Services locaux"))
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Airflow UI", _AIRFLOW_URL.split("//")[-1])
            st.link_button(t("useful_links.airflow_open_btn", "Ouvrir Airflow →"),
                           _AIRFLOW_URL, width="stretch")
            st.caption(t("useful_links.airflow_login", "Login : admin / admin (par défaut)"))

        with col2:
            st.metric("Streamlit Dashboard", _DASHBOARD_URL.split("//")[-1])
            st.link_button(t("useful_links.dashboard_open_btn", "Ouvrir Dashboard →"),
                           _DASHBOARD_URL, width="stretch")
            st.caption(t("useful_links.dashboard_caption",
                         "Ce dashboard — `streamlit run src/dashboard/app.py`"))

        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            st.metric("REST API (FastAPI)", _API_URL.split("//")[-1])
            st.link_button("Swagger UI →", f"{_API_URL}/docs", width="stretch")
            st.caption(t("useful_links.api_caption",
                         "Brick 14 — `uvicorn src.api.main:app --reload --port 8502`"))
        with col4:
            st.metric("API ReDoc", f'{_API_URL.split("//")[-1]}/redoc')
            st.link_button("ReDoc →", f"{_API_URL}/redoc", width="stretch")
            st.caption(t("useful_links.redoc_caption", "Documentation alternative (lisible)"))

        st.divider()
        st.subheader(t("useful_links.sec_postgres", "PostgreSQL"))
        st.markdown(t("useful_links.pg_table", """
| Paramètre | Valeur |
|---|---|
| Host (depuis WSL) | `localhost` |
| Port | `5433` |
| Database | `spotify_etl` |
| User | `postgres` |
| Password | voir `config/config.yaml` |
"""))
        _cmd(t("useful_links.cmd_psql_connect", "Connexion directe psql"),
             "docker exec -it dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl")

        st.divider()
        st.subheader(t("useful_links.sec_airflow_dags", "Airflow — Accès rapide aux DAGs"))
        dags = [
            ("spotify_api_daily", t("useful_links.dag_spotify_api_daily", "Spotify API quotidien")),
            ("youtube_daily", t("useful_links.dag_youtube_daily", "YouTube quotidien")),
            ("soundcloud_daily", t("useful_links.dag_soundcloud_daily", "SoundCloud quotidien")),
            ("instagram_daily", t("useful_links.dag_instagram_daily", "Instagram quotidien")),
            ("s4a_csv_watcher", t("useful_links.dag_s4a_csv_watcher", "CSV Spotify for Artists")),
            ("apple_music_csv_watcher", t("useful_links.dag_apple_music_csv_watcher", "CSV Apple Music")),
            ("meta_ads_api_daily", t("useful_links.dag_meta_ads_api_daily", "Meta Ads API")),
            ("ml_scoring_daily", t("useful_links.dag_ml_scoring_daily", "ML Scoring quotidien")),
            ("data_quality_check", t("useful_links.dag_data_quality_check", "Qualité des données")),
        ]
        for dag_id, label in dags:
            url = f"{_AIRFLOW_URL}/dags/{dag_id}/grid"
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"`{dag_id}` — {label}")
            c2.link_button(t("useful_links.grid_btn", "Grid →"), url, width="stretch")

    # ─────────────────────────────────────────────
    # TAB 3 — DOCKER & INFRA
    # ─────────────────────────────────────────────
    with tab_docker:
        st.subheader(t("useful_links.sec_start_stop", "Démarrage & arrêt"))
        _cmd(t("useful_links.cmd_start_all", "Démarrer tous les services"), "docker-compose up -d")
        _cmd(t("useful_links.cmd_stop_all", "Arrêter tous les services"), "docker-compose down")
        _cmd(t("useful_links.cmd_rebuild_all", "Rebuild après modif requirements.txt ou Dockerfile"),
             "docker-compose build && docker-compose up -d")
        _cmd(t("useful_links.cmd_rebuild_one", "Rebuild un seul service"),
             "docker-compose build airflow-scheduler && docker-compose up -d airflow-scheduler")

        st.subheader(t("useful_links.sec_logs", "Logs"))
        _cmd(t("useful_links.cmd_logs_scheduler", "Logs scheduler (erreurs DAGs, imports)"),
             "docker-compose logs -f airflow-scheduler")
        _cmd(t("useful_links.cmd_logs_webserver", "Logs webserver (UI)"), "docker-compose logs -f airflow-webserver")
        _cmd(t("useful_links.cmd_logs_postgres", "Logs PostgreSQL"), "docker-compose logs -f postgres")
        _cmd(t("useful_links.cmd_logs_tail", "Dernières 100 lignes scheduler"),
             "docker-compose logs --tail=100 airflow-scheduler")
        _cmd(t("useful_links.cmd_logs_wsl", "Logs via docker.exe (WSL2)"),
             '/mnt/c/Program\\ Files/Docker/Docker/resources/bin/docker.exe logs --tail 80 airflow_scheduler 2>&1')

        st.subheader(t("useful_links.sec_containers", "État des conteneurs"))
        _cmd(t("useful_links.cmd_list_containers", "Lister les conteneurs actifs"), "docker ps")
        _cmd(t("useful_links.cmd_stats", "Stats ressources (CPU/RAM)"), "docker stats --no-stream")

        st.subheader(t("useful_links.sec_database", "Base de données"))
        _cmd(t("useful_links.cmd_run_sql", "Exécuter un script SQL sur spotify_etl"),
             "docker exec -i dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl < scripts/mon_script.sql")
        _cmd(t("useful_links.cmd_list_tables", "Lister toutes les tables"),
             'docker exec dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl -c "\\dt"')
        _cmd(t("useful_links.cmd_check_rows", "Vérifier les lignes d'une table"),
             'docker exec dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl -c "SELECT COUNT(*) FROM s4a_song_timeline;"')
        _cmd(t("useful_links.cmd_backup", "Backup DB"),
             "docker exec dashboard_music_platform_algo_spotify-postgres-1 pg_dump -U postgres spotify_etl > backup_$(date +%Y%m%d).sql")

        st.subheader(t("useful_links.sec_volumes", "Volumes & reset"))
        _cmd(t("useful_links.cmd_list_volumes", "Voir les volumes Docker"), "docker volume ls")
        st.warning(t("useful_links.warn_reset",
                     "⚠️ La commande suivante supprime TOUTES les données de la DB — irréversible."))
        _cmd(t("useful_links.cmd_reset", "Reset complet DB (DANGER)"), "docker-compose down -v && docker-compose up -d")

    # ─────────────────────────────────────────────
    # TAB 4 — GUIDE CREDENTIALS
    # ─────────────────────────────────────────────
    with tab_credentials:
        st.info(t("useful_links.creds_retrigger_info",
                  "Après chaque mise à jour de credential, retrigger le DAG correspondant depuis Airflow UI."))

        with st.expander(t("useful_links.exp_instagram",
                           "📘 Instagram / Meta — Token long-lived (expire dans 60 jours)"), expanded=True):
            st.markdown(t("useful_links.body_instagram", """
**Process complet :**
1. Aller sur [Graph API Explorer](https://developers.facebook.com/tools/explorer)
2. Sélectionner ton app Meta dans le dropdown en haut à droite
3. Cliquer **"Generate Access Token"** → autoriser les permissions :
   - `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement`, `ads_read`
4. Token généré → cliquer l'icône ℹ️ bleue → **"Open in Access Token Debugger"**
5. Sur la page debugger → bouton **"Extend Access Token"** en bas → copier le long-lived token
6. Dashboard → **🔑 Credentials API** → Instagram → coller → Save
7. Retrigger : `instagram_daily` dans Airflow

**Rappel expiration** : le token dure **60 jours**. Mettre une alarme calendrier à J-5.

**DAG concerné** : `instagram_daily`
"""))

        with st.expander(t("useful_links.exp_soundcloud", "🎵 SoundCloud — client_id")):
            st.markdown(t("useful_links.body_soundcloud", """
**Méthode navigateur (recommandée) :**
1. Ouvrir SoundCloud dans Chrome/Firefox
2. DevTools F12 → onglet **Network**
3. Lancer une musique
4. Filtrer les requêtes : chercher `client_id=` dans les requêtes vers `api-v2.soundcloud.com`
5. Copier la valeur du paramètre `client_id` (~32 caractères alphanumériques)
6. Dashboard → **🔑 Credentials API** → SoundCloud → coller → Save
7. Retrigger : `soundcloud_daily`

**Durée de validité** : variable, peut expirer sans préavis (SoundCloud a fermé l'API publique).
"""))

        with st.expander(t("useful_links.exp_spotify", "🎵 Spotify — Client ID + Secret")):
            st.markdown(t("useful_links.body_spotify", """
1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → ton app
2. Copier **Client ID** et **Client Secret**
3. Dashboard → **🔑 Credentials API** → Spotify → Save
4. Retrigger : `spotify_api_daily` dans Airflow

ℹ️ Le collecteur utilise le flow **client_credentials** : le token d'accès
(~1 h) est re-généré automatiquement à chaque run. **Aucun refresh_token,
aucun flow OAuth, aucune action récurrente.** Le seul cas d'intervention :
`client_secret` révoqué/régénéré côté Spotify → recoller dans le dashboard.

**DAG concerné** : `spotify_api_daily`
"""))

        with st.expander(t("useful_links.exp_youtube", "🎬 YouTube — Clé API (YouTube Data API v3)")):
            st.markdown(t("useful_links.body_youtube", """
1. [console.cloud.google.com/apis/library/youtube.googleapis.com](https://console.cloud.google.com/apis/library/youtube.googleapis.com) → **Activer** l'API YouTube Data API v3
2. [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) → **Créer des identifiants → Clé API**
3. (Recommandé) Restreindre la clé à *YouTube Data API v3*
4. Récupérer le **Channel ID** (format `UC…`) : YouTube Studio → Paramètres → Chaîne → Paramètres avancés
5. Dashboard → **🔑 Credentials API** → YouTube → coller `api_key` + `channel_id` → Save
6. Retrigger : `youtube_daily` dans Airflow

ℹ️ Le collecteur utilise une **clé API statique** (`developerKey`), **pas
OAuth**. Une clé API **n'expire pas** et **ne se rafraîchit pas**. Si elle
est révoquée ou que le quota journalier est dépassé : régénérer une clé dans
Google Cloud Console et la recoller.

**DAG concerné** : `youtube_daily`
"""))

        with st.expander(t("useful_links.exp_meta_ads", "📊 Meta Ads — Même token que Instagram")):
            st.markdown(t("useful_links.body_meta_ads", """
Le même long-lived token Meta sert pour Instagram **et** Meta Ads.
Si le DAG `meta_ads_api_daily` échoue → vérifier le token Instagram.

**DAG concerné** : `meta_ads_api_daily`
"""))

    # ─────────────────────────────────────────────
    # TAB 5 — DEBUG & SCRIPTS
    # ─────────────────────────────────────────────
    with tab_debug:
        st.subheader(t("useful_links.sec_debug_dags", "Debug DAGs sans Airflow (local)"))
        st.caption(t("useful_links.debug_caption",
                     "Ces scripts reproduisent chaque DAG en local, sans Docker Airflow."))

        debug_scripts = [
            ("debug_spotify_api.py", "spotify_api_daily", t("useful_links.dbg_spotify", "Test collecte Spotify API")),
            ("debug_youtube.py", "youtube_daily", t("useful_links.dbg_youtube", "Test collecte YouTube")),
            ("debug_soundcloud.py", "soundcloud_daily", t("useful_links.dbg_soundcloud", "Test collecte SoundCloud")),
            ("debug_instagram.py", "instagram_daily", t("useful_links.dbg_instagram", "Test collecte Instagram")),
            ("debug_s4a.py", "s4a_csv_watcher", t("useful_links.dbg_s4a", "Test traitement CSV S4A")),
            ("debug_apple_music.py", "apple_music_csv_watcher",
             t("useful_links.dbg_apple", "Test traitement CSV Apple Music")),
            ("debug_meta_ads_api.py", "meta_ads_api_daily", t("useful_links.dbg_meta", "Test collecte Meta Ads API")),
            ("debug_ml_scoring.py", "ml_scoring_daily", t("useful_links.dbg_ml", "Test scoring ML")),
        ]

        for script, dag_id, desc in debug_scripts:
            st.markdown(f"**{desc}** (`{dag_id}`)")
            st.code(f"python airflow/debug_dag/{script}", language="bash")

        st.divider()
        st.subheader(t("useful_links.sec_util_scripts", "Scripts utilitaires"))
        _cmd(t("useful_links.cmd_migrate", "Appliquer les migrations manquantes en DB"), "make migrate")
        _cmd(t("useful_links.cmd_manage_mapping", "Gérer le mapping artistes"), "python scripts/manage_mapping.py")
        st.caption(t(
            "useful_links.util_caption",
            "Spotify (client_credentials) et YouTube (clé API statique) "
            "n'ont aucun script d'auth : tester depuis Dashboard → "
            "Credentials → bouton « Tester la connexion » de la plateforme."
        ))

        st.divider()
        st.subheader(t("useful_links.sec_db_checks", "Vérifications rapides DB"))
        queries = [
            (t("useful_links.q_spotify", "Dernière collecte Spotify"),
             "SELECT MAX(collected_at) FROM track_popularity_history;"),
            (t("useful_links.q_youtube", "Dernière collecte YouTube"),
             "SELECT MAX(collected_at) FROM youtube_video_stats;"),
            (t("useful_links.q_soundcloud", "Dernière collecte SoundCloud"),
             "SELECT MAX(collected_at) FROM soundcloud_tracks;"),
            (t("useful_links.q_instagram", "Dernière collecte Instagram"),
             "SELECT MAX(collected_at) FROM instagram_media;"),
            (t("useful_links.q_s4a", "Dernière collecte S4A"),
             "SELECT MAX(collected_at) FROM s4a_song_timeline;"),
            (t("useful_links.q_apple", "Dernière collecte Apple Music"),
             "SELECT MAX(collected_at) FROM apple_songs_performance;"),
            (t("useful_links.q_meta", "Dernière collecte Meta Insights"),
             "SELECT MAX(collected_at) FROM meta_insights_performance_day;"),
            (t("useful_links.q_ml", "Nombre de prédictions ML"),
             "SELECT COUNT(*) FROM ml_song_predictions;"),
            (t("useful_links.q_artists", "Artistes enregistrés"),
             "SELECT id, name, active FROM saas_artists ORDER BY id;"),
        ]
        for label, query in queries:
            st.markdown(f"**{label}**")
            st.code(f'docker exec dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl -c "{query}"', language="bash")

        st.divider()
        st.subheader(t("useful_links.sec_ruff", "Ruff — vérification syntaxe Python"))
        _cmd(t("useful_links.cmd_ruff_check", "Vérifier tout le projet"), "ruff check src/ airflow/ scripts/")
        _cmd(t("useful_links.cmd_ruff_fix", "Fix automatique"), "ruff check --fix src/ airflow/ scripts/")

        st.divider()
        st.caption(t("useful_links.page_generated", "Page générée le {ts}").format(
            ts=datetime.now().strftime('%d/%m/%Y à %H:%M')))


if __name__ == "__main__":
    show()

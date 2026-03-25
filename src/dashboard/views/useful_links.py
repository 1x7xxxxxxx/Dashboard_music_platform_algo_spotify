"""
Vue "Liens & Outils" — Référence opérationnelle pour gérer la plateforme.
Regroupe : URLs externes, commandes Docker/infra, guide credentials, commandes debug.
"""
import streamlit as st
from datetime import datetime
from src.dashboard.auth import is_admin


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
        st.link_button("Ouvrir →", url, width="stretch")
    st.divider()


def _cmd(description: str, command: str):
    st.markdown(f"**{description}**")
    st.code(command, language="bash")


def show():
    if not is_admin():
        st.error("⛔ Accès réservé à l'administrateur.")
        st.stop()

    st.title("🔧 Liens & Outils")
    st.caption("Référence opérationnelle — tous les liens et commandes pour gérer la plateforme.")

    tab_ext, tab_local, tab_docker, tab_credentials, tab_debug = st.tabs([
        "🌐 Liens Externes",
        "🏠 Outils Locaux",
        "🐳 Docker & Infra",
        "🔑 Guide Credentials",
        "🐛 Debug & Scripts",
    ])

    # ─────────────────────────────────────────────
    # TAB 1 — LIENS EXTERNES
    # ─────────────────────────────────────────────
    with tab_ext:
        st.subheader("Meta / Instagram / Facebook")
        _link_row("Graph API Explorer", "https://developers.facebook.com/tools/explorer",
                  "Générer un access token Instagram")
        _link_row("Débogueur de token", "https://developers.facebook.com/tools/debug/accesstoken",
                  "Vérifier expiration + étendre le token (bouton 'Extend Access Token')")
        _link_row("Facebook App Settings", "https://developers.facebook.com/apps",
                  "App ID + App Secret")
        _link_row("Meta Business Manager", "https://business.facebook.com",
                  "Comptes publicitaires, pages")
        _link_row("Meta Ads Manager", "https://www.facebook.com/adsmanager",
                  "Campagnes, ad sets, performances")

        st.subheader("Spotify")
        _link_row("Spotify Developer Dashboard", "https://developer.spotify.com/dashboard",
                  "Client ID + Client Secret")
        _link_row("Spotify for Artists", "https://artists.spotify.com",
                  "Export CSV (streams, audience, songs)")
        _link_row("Spotify API Reference", "https://developer.spotify.com/documentation/web-api",
                  "Endpoints, scopes, rate limits")

        st.subheader("SoundCloud")
        _link_row("SoundCloud Developer Apps", "https://soundcloud.com/you/apps",
                  "Client ID (si accès développeur actif)")
        _link_row("SoundCloud", "https://soundcloud.com",
                  "Inspecter client_id via DevTools F12 → Network → filtre 'client_id='")

        st.subheader("YouTube / Google")
        _link_row("Google Cloud Console — Credentials", "https://console.cloud.google.com/apis/credentials",
                  "OAuth 2.0 Client IDs, API Keys")
        _link_row("YouTube Studio", "https://studio.youtube.com",
                  "Analytics, export données")
        _link_row("YouTube Data API v3", "https://console.cloud.google.com/apis/library/youtube.googleapis.com",
                  "Activer/désactiver l'API")

        st.subheader("Apple Music")
        _link_row("Apple Music for Artists", "https://artists.apple.com",
                  "Export CSV Songs Performance")

        st.subheader("iMusician")
        _link_row("iMusician Dashboard", "https://www.imusician.pro/app",
                  "Revenus mensuels à saisir manuellement dans le dashboard")

        st.subheader("Hypeddit")
        _link_row("Hypeddit", "https://hypeddit.com",
                  "Export CSV campagnes")

    # ─────────────────────────────────────────────
    # TAB 2 — OUTILS LOCAUX
    # ─────────────────────────────────────────────
    with tab_local:
        st.subheader("Services locaux")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Airflow UI", "localhost:8080")
            st.link_button("Ouvrir Airflow →", "http://localhost:8080", width="stretch")
            st.caption("Login : admin / admin (par défaut)")

        with col2:
            st.metric("Streamlit Dashboard", "localhost:8501")
            st.link_button("Ouvrir Dashboard →", "http://localhost:8501", width="stretch")
            st.caption("Ce dashboard — `streamlit run src/dashboard/app.py`")

        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            st.metric("REST API (FastAPI)", "localhost:8502")
            st.link_button("Swagger UI →", "http://localhost:8502/docs", width="stretch")
            st.caption("Brick 14 — `uvicorn src.api.main:app --reload --port 8502`")
        with col4:
            st.metric("API ReDoc", "localhost:8502/redoc")
            st.link_button("ReDoc →", "http://localhost:8502/redoc", width="stretch")
            st.caption("Documentation alternative (lisible)")

        st.divider()
        st.subheader("PostgreSQL")
        st.markdown("""
| Paramètre | Valeur |
|---|---|
| Host (depuis WSL) | `localhost` |
| Port | `5433` |
| Database | `spotify_etl` |
| User | `postgres` |
| Password | voir `config/config.yaml` |
""")
        _cmd("Connexion directe psql", "docker exec -it dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl")

        st.divider()
        st.subheader("Airflow — Accès rapide aux DAGs")
        dags = [
            ("spotify_api_daily", "Spotify API quotidien"),
            ("youtube_daily", "YouTube quotidien"),
            ("soundcloud_daily", "SoundCloud quotidien"),
            ("instagram_daily", "Instagram quotidien"),
            ("s4a_csv_watcher", "CSV Spotify for Artists"),
            ("apple_music_csv_watcher", "CSV Apple Music"),
            ("meta_csv_watcher_config", "Meta Ads Config CSV"),
            ("meta_insights_watcher", "Meta Insights CSV"),
            ("ml_scoring_daily", "ML Scoring quotidien"),
            ("data_quality_check", "Qualité des données"),
        ]
        for dag_id, label in dags:
            url = f"http://localhost:8080/dags/{dag_id}/grid"
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"`{dag_id}` — {label}")
            c2.link_button("Grid →", url, width="stretch")

    # ─────────────────────────────────────────────
    # TAB 3 — DOCKER & INFRA
    # ─────────────────────────────────────────────
    with tab_docker:
        st.subheader("Démarrage & arrêt")
        _cmd("Démarrer tous les services", "docker-compose up -d")
        _cmd("Arrêter tous les services", "docker-compose down")
        _cmd("Rebuild après modif requirements.txt ou Dockerfile", "docker-compose build && docker-compose up -d")
        _cmd("Rebuild un seul service", "docker-compose build airflow-scheduler && docker-compose up -d airflow-scheduler")

        st.subheader("Logs")
        _cmd("Logs scheduler (erreurs DAGs, imports)", "docker-compose logs -f airflow-scheduler")
        _cmd("Logs webserver (UI)", "docker-compose logs -f airflow-webserver")
        _cmd("Logs PostgreSQL", "docker-compose logs -f postgres")
        _cmd("Dernières 100 lignes scheduler", "docker-compose logs --tail=100 airflow-scheduler")
        _cmd("Logs via docker.exe (WSL2)", '/mnt/c/Program\\ Files/Docker/Docker/resources/bin/docker.exe logs --tail 80 airflow_scheduler 2>&1')

        st.subheader("État des conteneurs")
        _cmd("Lister les conteneurs actifs", "docker ps")
        _cmd("Stats ressources (CPU/RAM)", "docker stats --no-stream")

        st.subheader("Base de données")
        _cmd("Exécuter un script SQL sur spotify_etl",
             "docker exec -i dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl < scripts/mon_script.sql")
        _cmd("Lister toutes les tables", 'docker exec dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl -c "\\dt"')
        _cmd("Vérifier les lignes d'une table",
             'docker exec dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl -c "SELECT COUNT(*) FROM s4a_song_timeline;"')
        _cmd("Backup DB",
             "docker exec dashboard_music_platform_algo_spotify-postgres-1 pg_dump -U postgres spotify_etl > backup_$(date +%Y%m%d).sql")

        st.subheader("Volumes & reset")
        _cmd("Voir les volumes Docker", "docker volume ls")
        st.warning("⚠️ La commande suivante supprime TOUTES les données de la DB — irréversible.")
        _cmd("Reset complet DB (DANGER)", "docker-compose down -v && docker-compose up -d")

    # ─────────────────────────────────────────────
    # TAB 4 — GUIDE CREDENTIALS
    # ─────────────────────────────────────────────
    with tab_credentials:
        st.info("Après chaque mise à jour de credential, retrigger le DAG correspondant depuis Airflow UI.")

        with st.expander("📘 Instagram / Meta — Token long-lived (expire dans 60 jours)", expanded=True):
            st.markdown("""
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
""")

        with st.expander("🎵 SoundCloud — client_id"):
            st.markdown("""
**Méthode navigateur (recommandée) :**
1. Ouvrir SoundCloud dans Chrome/Firefox
2. DevTools F12 → onglet **Network**
3. Lancer une musique
4. Filtrer les requêtes : chercher `client_id=` dans les requêtes vers `api-v2.soundcloud.com`
5. Copier la valeur du paramètre `client_id` (~32 caractères alphanumériques)
6. Dashboard → **🔑 Credentials API** → SoundCloud → coller → Save
7. Retrigger : `soundcloud_daily`

**Durée de validité** : variable, peut expirer sans préavis (SoundCloud a fermé l'API publique).
""")

        with st.expander("🎵 Spotify — Client ID + Secret"):
            st.markdown("""
1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → ton app
2. Copier **Client ID** et **Client Secret**
3. Dashboard → **🔑 Credentials API** → Spotify → Save
4. Si OAuth expiré : relancer le flow d'auth dans le DAG ou via `python airflow/debug_dag/debug_spotify_api.py`

**DAG concerné** : `spotify_api_daily`
""")

        with st.expander("🎬 YouTube — OAuth 2.0"):
            st.markdown("""
1. [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) → ton projet
2. Télécharger le fichier `credentials.json` (OAuth 2.0 Client ID)
3. Placer dans le dossier configuré (voir `config/config.yaml` → `youtube.credentials_path`)
4. Premier lancement : `python scripts/test_youtube_auth.py` pour générer le `token.json`
5. Les tokens YouTube se rafraîchissent automatiquement (refresh_token long terme)

**DAG concerné** : `youtube_daily`
""")

        with st.expander("📊 Meta Ads — Même token que Instagram"):
            st.markdown("""
Le même long-lived token Meta sert pour Instagram **et** Meta Ads.
Si les DAGs `meta_csv_watcher_config` et `meta_insights_watcher` échouent → vérifier le token Instagram.

**DAGs concernés** : `meta_csv_watcher_config`, `meta_insights_watcher`
""")

    # ─────────────────────────────────────────────
    # TAB 5 — DEBUG & SCRIPTS
    # ─────────────────────────────────────────────
    with tab_debug:
        st.subheader("Debug DAGs sans Airflow (local)")
        st.caption("Ces scripts reproduisent chaque DAG en local, sans Docker Airflow.")

        debug_scripts = [
            ("debug_spotify_api.py", "spotify_api_daily", "Test collecte Spotify API"),
            ("debug_youtube.py", "youtube_daily", "Test collecte YouTube"),
            ("debug_soundcloud.py", "soundcloud_daily", "Test collecte SoundCloud"),
            ("debug_instagram.py", "instagram_daily", "Test collecte Instagram"),
            ("debug_s4a.py", "s4a_csv_watcher", "Test traitement CSV S4A"),
            ("debug_apple_music.py", "apple_music_csv_watcher", "Test traitement CSV Apple Music"),
            ("debug_meta_config.py", "meta_csv_watcher_config", "Test CSV Meta Ads config"),
            ("debug_meta_insights.py", "meta_insights_watcher", "Test CSV Meta Insights"),
            ("debug_ml_scoring.py", "ml_scoring_daily", "Test scoring ML"),
        ]

        for script, dag_id, desc in debug_scripts:
            st.markdown(f"**{desc}** (`{dag_id}`)")
            st.code(f"python airflow/debug_dag/{script}", language="bash")

        st.divider()
        st.subheader("Scripts utilitaires")
        _cmd("Vérifier les clés API Meta", "python scripts/check_api_keys_meta.py")
        _cmd("Tester l'auth YouTube", "python scripts/test_youtube_auth.py")
        _cmd("Créer les tables manquantes en DB", "docker exec -i dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl < scripts/create_missing_tables.sql")
        _cmd("Gérer le mapping artistes", "python scripts/manage_mapping.py")

        st.divider()
        st.subheader("Vérifications rapides DB")
        queries = [
            ("Dernière collecte Spotify", "SELECT MAX(collected_at) FROM track_popularity_history;"),
            ("Dernière collecte YouTube", "SELECT MAX(collected_at) FROM youtube_video_stats;"),
            ("Dernière collecte SoundCloud", "SELECT MAX(collected_at) FROM soundcloud_tracks;"),
            ("Dernière collecte Instagram", "SELECT MAX(collected_at) FROM instagram_media;"),
            ("Dernière collecte S4A", "SELECT MAX(collected_at) FROM s4a_song_timeline;"),
            ("Dernière collecte Apple Music", "SELECT MAX(collected_at) FROM apple_songs_performance;"),
            ("Dernière collecte Meta Insights", "SELECT MAX(collected_at) FROM meta_insights_performance_day;"),
            ("Nombre de prédictions ML", "SELECT COUNT(*) FROM ml_song_predictions;"),
            ("Artistes enregistrés", "SELECT id, name, active FROM saas_artists ORDER BY id;"),
        ]
        for label, query in queries:
            st.markdown(f"**{label}**")
            st.code(f'docker exec dashboard_music_platform_algo_spotify-postgres-1 psql -U postgres -d spotify_etl -c "{query}"', language="bash")

        st.divider()
        st.subheader("Ruff — vérification syntaxe Python")
        _cmd("Vérifier tout le projet", "ruff check src/ airflow/ scripts/")
        _cmd("Fix automatique", "ruff check --fix src/ airflow/ scripts/")

        st.divider()
        st.caption(f"Page générée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")


if __name__ == "__main__":
    show()

@"
# 🎵 Dashboard Music Platform - Spotify & Meta Ads Analytics

Dashboard ETL complet pour analyser les performances musicales sur Spotify et Meta Ads.

---

## 🎯 Fonctionnalités

### ✅ Sources de Données Intégrées
- **Meta Ads** : Collecte automatique via API (campagnes, adsets, ads, insights)
- **Spotify for Artists** : Téléchargement manuel + intégration automatique des CSV
- **Spotify API** : Données artistes et tracks

### 📊 Dashboard Streamlit Interactif
- **Meta Ads** : Vue d'ensemble des campagnes actives
- **Spotify for Artists** : Stats globales, timeline par chanson, audience
- **Artist Stats** : Analyse complète des performances
- **Top Tracks** : Classement des meilleures chansons

### 💾 Stockage PostgreSQL
- Base de données centralisée : \`spotify_etl\`
- Schémas optimisés avec indexes
- 11,000+ enregistrements de données historiques

---

## 🚀 Installation

### 1. Prérequis
- Python 3.10+
- PostgreSQL 17+
- Compte Meta Ads Business
- Compte Spotify for Artists

### 2. Cloner le repository
\`\`\`bash
git clone https://github.com/votre-username/Dashboard_music_platform_algo_spotify.git
cd Dashboard_music_platform_algo_spotify
\`\`\`

### 3. Créer l'environnement virtuel
\`\`\`bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
\`\`\`

### 4. Installer les dépendances
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 5. Configurer PostgreSQL
\`\`\`bash
# Créer la base de données
psql -U postgres
CREATE DATABASE spotify_etl;
\q

# Créer les tables
python -c "from src.database.meta_ads_schema import create_meta_ads_tables; create_meta_ads_tables()"
python -c "from src.database.s4a_schema import create_s4a_tables; create_s4a_tables()"
\`\`\`

### 6. Configurer les APIs
Créez \`config/config.yaml\` :
\`\`\`yaml
database:
  host: localhost
  port: 5433
  database: spotify_etl
  user: postgres
  password: votre_password

meta_ads:
  access_token: "votre_token"
  ad_account_id: "act_XXXXXXXXX"

spotify:
  client_id: "votre_client_id"
  client_secret: "votre_client_secret"
  redirect_uri: "http://localhost:8888/callback"
\`\`\`

---

## 📊 Utilisation

### Dashboard Principal
\`\`\`bash
streamlit run src/dashboard/app.py
\`\`\`

### Collecte Meta Ads (Manuel)
\`\`\`bash
python collect_and_store_meta_ads.py
\`\`\`

### Monitoring Meta Ads
\`\`\`bash
python monitor_meta_ads.py
\`\`\`

### Vérification des Données
\`\`\`bash
python verify_meta_ads_data.py
\`\`\`

### Traitement CSV Spotify for Artists

**Option 1 : Traitement manuel**
\`\`\`bash
# 1. Téléchargez votre CSV depuis artists.spotify.com
# 2. Placez-le dans data/raw/spotify_for_artists/
# 3. Lancez le traitement
python process_s4a_csv.py
\`\`\`

**Option 2 : Watcher automatique** (Recommandé)
\`\`\`bash
# Lancer le watcher en arrière-plan
python watch_s4a_folder.py

# Déposez vos CSV dans data/raw/spotify_for_artists/
# → Traitement automatique en 2 secondes !
\`\`\`

---

## 🗂️ Structure du Projet

\`\`\`
src/
├── collectors/        # Collecteurs API
├── database/          # Gestionnaire PostgreSQL + Schémas
├── dashboard/         # Dashboard Streamlit
├── transformers/      # Parsers CSV
└── utils/             # Utilitaires (config, etc.)

data/
├── raw/               # Données brutes (CSV téléchargés)
└── processed/         # Données traitées (archivées)

config/
└── config.yaml        # Configuration (git ignored)
\`\`\`

---

## 📈 Prochaines Étapes (Branche Airflow)

- [ ] Orchestration Airflow pour automatisation complète
- [ ] DAGs pour collecte quotidienne Meta Ads
- [ ] Monitoring qualité des données
- [ ] Alertes automatiques par email
- [ ] Intégration Hypeddit API
- [ ] Machine Learning (prédictions de streams)

---

## 🛠️ Technologies

- **Python 3.10**
- **Streamlit** : Dashboard interactif
- **PostgreSQL** : Base de données
- **Plotly** : Visualisations
- **Pandas** : Manipulation de données
- **Meta Business SDK** : API Meta Ads
- **Spotipy** : API Spotify

---
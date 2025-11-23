# 🎵 Music Platform Dashboard - ETL & Analytics

Dashboard complet d'analyse de données musicales croisant les sources **Spotify API**, **Spotify for Artists (CSV)**, **Meta Ads** et **YouTube**.

Le projet utilise une architecture **ELT moderne** containerisée avec Docker, orchestrée par Airflow et visualisée via Streamlit.

---

## 🏗️ Architecture

* **Orchestration :** Apache Airflow (Dockerisé)
* **Base de données :** PostgreSQL 17 (Dockerisé)
* **Visualisation :** Streamlit (Local)
* **Langage :** Python 3.10
* **Connecteurs :** Spotipy, Facebook Business SDK, Google API Client

---

## 🎯 Fonctionnalités

### 🔄 Collecte Automatisée (Airflow DAGs)
| DAG | Description | Fréquence |
| :--- | :--- | :--- |
| `spotify_api_daily` | Récupère followers, popularité et top tracks via API. | Quotidien |
| `meta_ads_daily` | Récupère campagnes, adsets, pubs et insights (conversions, coût). | Quotidien |
| `youtube_daily` | Récupère stats de chaîne et vidéos via YouTube Data API. | Quotidien |
| `s4a_csv_watcher` | Détecte et ingère automatiquement les CSV *Spotify for Artists*. | 15 min |
| `apple_music_watcher` | Détecte et ingère automatiquement les CSV *Apple Music*. | 15 min |
| `data_quality_check` | Vérifie la cohérence des données et alerte en cas d'anomalie. | 22h30 |

### 📊 Dashboard (Streamlit)
* **Vue Globale :** KPIs multi-plateformes en temps réel.
* **Meta x Spotify :** Analyse de corrélation (Impact des Ads sur les Streams).
* **Hypeddit :** Saisie manuelle et suivi des campagnes Smart Link.
* **Performance Artiste :** Évolution audience et popularité.

---

## 🚀 Installation & Démarrage

### 1. Prérequis
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé.
* Python 3.10+ installé (pour le dashboard local).

### 2. Configuration
Clonez le projet et configurez les variables d'environnement :

```bash
git clone [https://github.com/votre-username/Dashboard_music_platform_algo_spotify.git](https://github.com/votre-username/Dashboard_music_platform_algo_spotify.git)
cd Dashboard_music_platform_algo_spotify

# Créez le fichier .env à partir du modèle
cp .env.example .env
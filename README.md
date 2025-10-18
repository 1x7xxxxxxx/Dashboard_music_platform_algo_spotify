# 🎵 Spotify ETL Dashboard

> Pipeline ETL automatisé collectant données Spotify, Meta Ads et Spotify for Artists avec dashboard Streamlit

## 📋 Features
- Collecte API Spotify & Meta Ads quotidienne
- Scraping Selenium Spotify for Artists
- Pipeline Airflow orchestré
- Dashboard Streamlit interactif
- Validation Pydantic + détection anomalies

## 🚀 Installation
```bash
git clone https://github.com/votre-username/Dashboard_music_platform_algo_spotify
cd Dashboard_music_platform_algo_spotify
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## ⚙️ Configuration
Créer `config/config.yaml` avec vos API keys

## 📊 Usage
```bash
streamlit run streamlit_app/app.py
```

## 🏗️ Architecture
Voir structure détaillée dans `/docs`
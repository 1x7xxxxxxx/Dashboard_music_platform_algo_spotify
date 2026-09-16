# Dockerfile — Streamlit dashboard (Railway-compatible)
#
# Build:   docker build -t music-dashboard .
# Run:     docker run -e DATABASE_URL=... -e PORT=8501 -p 8501:8501 music-dashboard
#
# In Railway: set DATABASE_URL and PORT is injected automatically.

FROM python:3.11-slim

# System deps for WeasyPrint (PDF export) + psycopg2.
# Official WeasyPrint requirements: libpango-1.0-0 + libpangoft2-1.0-0 (FT API
# used since v60+). libcairo2 + libgdk-pixbuf2 + libffi-dev + shared-mime-info
# round out the rendering stack. libpangocairo is pulled transitively.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
# `xgboost` declares `nvidia-nccl-cu12` (454 MB) as a hard dependency: pip installs
# it on every image, GPU or not. This VPS is CPU-only, and nccl is the multi-GPU
# collective-communication library — nothing here can reach it.
#
# The uninstall MUST share this RUN. A separate layer only hides the files: the
# bytes stay in the layer below and the image does not shrink. Measured on
# 2026-08-30 — the first version of this change used a second RUN and the API image
# stayed at 3.87 GB with a clean-looking `pip list`.
#
# The train() below is the proof, executed at build time, so a future xgboost that
# genuinely needs nccl fails the BUILD rather than a nightly DAG.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y nvidia-nccl-cu12 \
    && python -c "import numpy as np, xgboost as xgb; \
xgb.train({}, xgb.DMatrix(np.array([[1.0],[2.0]]), label=np.array([0,1])), 2); \
print('xgboost OK without nccl')"

# Copy project source
COPY src/ ./src/
COPY config/ ./config/
COPY .streamlit/ ./.streamlit/
# Les captures d'écran des guides d'identifiants. 240 Ko, et elles ont manqué à la
# PROD pendant cinq signalements : `screenshot_path()` renvoie un chemin inexistant,
# les deux surfaces qui l'affichent traitent l'absence comme « rien à montrer », et
# personne — moi compris — n'a regardé ailleurs qu'en local, où le fichier est là.
# `tests/test_the_image_ships_with_the_app.py` compare désormais ce COPY aux
# répertoires que le code résout à l'exécution.
COPY assets/ ./assets/

# Streamlit config — disable usage stats, listen on $PORT
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true

# PORT is injected by Railway at runtime; default to 8501 locally
EXPOSE 8501


# ── HEALTHCHECK, et la distinction qui le rend utile (2026-09-16) ─────────────
# `restart: unless-stopped` relance un processus MORT. Il ne relance jamais un
# processus FIGÉ — et c'est précisément le mode de panne mesuré contre la production
# le 2026-09-16 : à vingt-quatre onglets simultanés, **98 reruns se perdent** sans que
# le processus meure. Un conteneur qui ne répond plus reste alors « Up » pour Docker,
# et resterait dans le pool d'un répartiteur de charge.
#
# La sonde tape l'endpoint qui existe déjà et que `tools/deploy.sh:56-71` interroge
# déjà après un déploiement. Ce qui change : elle est désormais interrogée EN CONTINU,
# pas seulement à la minute du déploiement.
#
# `start-period` est large à dessein : l'import de Streamlit + pandas coûte plusieurs
# secondes, et une sonde qui échoue au démarrage ferait boucler le redémarrage.
#
# ── Pourquoi Python et pas `curl` ──
# `curl` est ABSENT des deux images — vérifié dans les conteneurs QUI TOURNENT :
# `docker exec streamlytics_dashboard command -v curl` ne rend rien. Une sonde
# `CMD curl …` aurait donc marqué le conteneur **malade à vie**, c'est-à-dire
# exactement la classe `un-contrôle-qui-ne-peut-jamais-passer` — et elle aurait été
# posée une minute après que le commentaire ci-dessus l'ait nommée.
# Python est le runtime : sa présence n'est pas une hypothèse. `urllib` suffit, et
# évite une couche apt de plus.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python3 -c "import os,sys,urllib.request as u; p=os.environ.get('PORT','8501'); sys.exit(0 if u.urlopen(f'http://localhost:{p}/_stcore/health', timeout=3).status==200 else 1)"

CMD sh -c "streamlit run src/dashboard/app.py --server.port ${PORT:-8501} --server.address 0.0.0.0"

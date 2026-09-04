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

CMD sh -c "streamlit run src/dashboard/app.py --server.port ${PORT:-8501} --server.address 0.0.0.0"

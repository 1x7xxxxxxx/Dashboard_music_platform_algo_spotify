# Dockerfile — Streamlit dashboard (Railway-compatible)
#
# Build:   docker build -t music-dashboard .
# Run:     docker run -e DATABASE_URL=... -e PORT=8501 -p 8501:8501 music-dashboard
#
# In Railway: set DATABASE_URL and PORT is injected automatically.

FROM python:3.11-slim

# System deps for WeasyPrint (PDF export) + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY src/ ./src/
COPY config/ ./config/
COPY .streamlit/ ./.streamlit/ 2>/dev/null || true

# Streamlit config — disable usage stats, listen on $PORT
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true

# PORT is injected by Railway at runtime; default to 8501 locally
EXPOSE 8501

CMD sh -c "streamlit run src/dashboard/app.py --server.port ${PORT:-8501} --server.address 0.0.0.0"

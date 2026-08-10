# Production image for the PhishShield AI demo API only (src/phishshield/api/).
# Not used for local development -- see LOCAL_SETUP.md for that.

FROM python:3.11-slim

WORKDIR /app

# System deps for lxml (bs4's parser backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY artifacts/ artifacts/
RUN pip install --no-cache-dir -e .

# Render/Cloud Run inject $PORT at runtime; default to 8000 for `docker run` locally.
ENV PORT=8000
EXPOSE 8000

# Fails fast and loudly if the model artifact didn't get copied in --
# matches api/model_store.py's own "never silently fall back" contract.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/health').status==200 else 1)"

CMD ["sh", "-c", "uvicorn phishshield.api.app:app --host 0.0.0.0 --port ${PORT}"]

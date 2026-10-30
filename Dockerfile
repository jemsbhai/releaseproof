FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RELEASEPROOF_DB_PATH=/tmp/releaseproof/releaseproof.sqlite3 \
    RELEASEPROOF_LIVE_ENABLED=0

WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock \
    && useradd --create-home --uid 1000 app
COPY --chown=app:app releaseproof /app/releaseproof
COPY --chown=app:app data /app/data
COPY --chown=app:app web /app/web
COPY --chown=app:app LICENSE /app/LICENSE
USER app
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "releaseproof.server:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--log-level", "warning"]

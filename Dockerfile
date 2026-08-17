# AI Business Analytics Platform — production image
#
# Single-stage build: the pip wheels for pandas/sklearn/xgboost/shap are
# already compiled (manylinux), so there's no real benefit to a multi-stage
# compile step here — it would just add complexity without a smaller image.
FROM python:3.12-slim

# xgboost's Python wheel dynamically links libgomp (OpenMP) at import time;
# it's not bundled in the wheel, and importing xgboost fails without it on
# a minimal base image. libpq5 is needed for psycopg2-binary's PostgreSQL
# connections at runtime (not just build time).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

# Directories the app writes to at runtime (uploads, trained models,
# generated reports, logs) — created here so they exist even before any
# volume is mounted over them.
RUN mkdir -p data/uploads/tmp data/processed data/models data/reports logs \
    && touch data/uploads/.gitkeep data/processed/.gitkeep data/models/.gitkeep data/reports/.gitkeep

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV FLASK_APP=app.py \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "120", "app:app"]

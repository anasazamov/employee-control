# Bitta image — 4 rol (api | ws | worker | beat), rol CMD bilan tanlanadi (reja §3)
FROM python:3.12-slim

WORKDIR /srv/app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# INSTALL_FACE=true bo'lsa insightface stack o'rnatiladi (haqiqiy server yuz-tanish).
# Faqat kerakli servis (api/face-worker) uni true bilan build qiladi — migrate lean qoladi.
ARG INSTALL_FACE=false

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN if [ "$INSTALL_FACE" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends \
            build-essential cmake libgomp1 libglib2.0-0 && \
        rm -rf /var/lib/apt/lists/* && \
        pip install --no-cache-dir ".[face]" ; \
    else \
        pip install --no-cache-dir . ; \
    fi

EXPOSE 8000
# api roli (default); ws/worker/beat rollari compose'da CMD override bilan
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

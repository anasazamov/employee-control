# Bitta image — 4 rol (api | ws | worker | beat), rol CMD bilan tanlanadi (reja §3)
FROM python:3.12-slim

WORKDIR /srv/app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000
# api roli (default); ws/worker/beat rollari compose'da CMD override bilan
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

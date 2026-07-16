"""Celery app — `worker` va `beat` rollari shu obyektni yuklaydi (reja §3).

Broker/backend: Redis. Queue'lar: `default` (metering, bildirishnoma) va `face`
(kelajakdagi InsightFace-tekshiruvi — CPU-og'ir, izolyatsiya qilinadi). Beat:
tungi metering-snapshot.

Task'lar sinxron kontekstda yuradi, ichida asyncio.run bilan async servis chaqiriladi
(oddiy va bu ish-yuklama uchun yetarli — reja §3: Celery tanlovi asoslandi)."""

import asyncio
from datetime import UTC, datetime

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "employee_control",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)
celery_app.conf.update(
    task_default_queue="default",
    task_routes={"app.celery_app.face_*": {"queue": "face"}},
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Tashkent",
    beat_schedule={
        "nightly-usage-snapshot": {
            "task": "app.celery_app.nightly_usage_snapshot",
            "schedule": crontab(hour=0, minute=30),  # har kuni 00:30
        },
    },
)


@celery_app.task(name="app.celery_app.nightly_usage_snapshot")
def nightly_usage_snapshot() -> int:
    """Har org uchun faol-xodim + check-in metering-snapshot (idempotent upsert)."""
    from app.modules.platform.service import snapshot_usage

    today = datetime.now(UTC).date()
    return asyncio.run(snapshot_usage(today))

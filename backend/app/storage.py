"""Obyekt-saqlash (MinIO) — selfie/foto. Mobil ilova presigned PUT bilan
to'g'ridan-to'g'ri yuklaydi: rasm baytlari app-node'lardan o'tmaydi (reja §3).

Bucket-per-tenant (`t-{org_uuid}`) — izolyatsiya (reja §4). Ichida `checkins/`
prefiksi. TODO(v2): per-tenant SSE-KMS kalit (MinIO KES) — offboarding'da kalit
yo'q qilinsa fotolar kriptografik o'chadi; `checkin-photos` object-lock (dalil
o'zgarmasligi). Hozir MVP: shifrsiz bucket, presigned yuklash/o'qish.

MinIO SDK sinxron — thread-pool'da (asyncio.to_thread) chaqiriladi."""

import asyncio
import uuid
from datetime import timedelta
from functools import lru_cache

from minio import Minio

from app.config import get_settings


@lru_cache
def _client() -> Minio:
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


def _bucket(org_id: uuid.UUID) -> str:
    return f"t-{org_id}"


def _ensure_bucket_sync(bucket: str) -> None:
    c = _client()
    if not c.bucket_exists(bucket):
        c.make_bucket(bucket)


async def presign_selfie_put(org_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Yangi selfie uchun presigned PUT. Obyekt-kaliti server tomonda quriladi —
    mijoz kalitni tanlay olmaydi (boshqa tenant bucket'iga yozib bo'lmaydi)."""
    bucket = _bucket(org_id)
    object_key = f"checkins/{user_id}/{uuid.uuid4()}.jpg"
    s = get_settings()

    def _work() -> str:
        _ensure_bucket_sync(bucket)
        return _client().presigned_put_object(
            bucket, object_key, expires=timedelta(seconds=s.selfie_url_ttl_seconds)
        )

    url = await asyncio.to_thread(_work)
    return {"url": url, "object_key": object_key, "bucket": bucket}


async def fetch_object(org_id: uuid.UUID, object_key: str) -> bytes:
    """Selfie baytlarini o'qish (server yuz-verifikatsiyasi uchun)."""
    bucket = _bucket(org_id)

    def _work() -> bytes:
        resp = _client().get_object(bucket, object_key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    return await asyncio.to_thread(_work)


async def presign_selfie_get(org_id: uuid.UUID, object_key: str) -> str:
    """Review-navbat/tafsilot uchun qisqa-muddatli o'qish-URL."""
    bucket = _bucket(org_id)
    s = get_settings()

    def _work() -> str:
        return _client().presigned_get_object(
            bucket, object_key, expires=timedelta(seconds=s.selfie_url_ttl_seconds)
        )

    return await asyncio.to_thread(_work)


def valid_selfie_key(org_id: uuid.UUID, user_id: uuid.UUID, object_key: str) -> bool:
    """Check-in'da kelgan selfie_key shu xodimning prefiksiga mos ekanini tekshirish
    (boshqa xodim/tenant kalitini biriktirib bo'lmaydi)."""
    return object_key.startswith(f"checkins/{user_id}/") and object_key.endswith(".jpg")

"""Yuz-verifikatsiya servis (reja §6). pgvector cosine bilan:
- enroll: embedding saqlash + tenant-ichi dedup 1:N;
- identify: 1:N (aktivatsiya) — top-1 chegara + margin;
- verify: 1:1 (check-in) — xodimning shabloniga eng yaqin cosine.

Xavfsizlik: 1:N va dedup HAR DOIM org-filtrli (RLS + explicit) — tenantlar aro
solishtirish yo'q (reja §4). Embedding hisoblash CPU-og'ir — thread-pool'da."""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import FaceEmbedding, User
from app.modules.face.embedder import FaceError, get_embedder


async def _embed(image_bytes: bytes) -> tuple[list[float], str]:
    emb = get_embedder()
    vec = await asyncio.to_thread(emb.embed, image_bytes)
    return vec, emb.model_ver


@dataclass
class EnrollResult:
    embedding_id: str
    model_ver: str


class DuplicateFaceError(Exception):
    def __init__(self, other_user_id: uuid.UUID, score: float):
        self.other_user_id = other_user_id
        self.score = score


async def enroll(
    session: AsyncSession, *, org_id: uuid.UUID, user_id: uuid.UUID, image_bytes: bytes
) -> EnrollResult:
    """HR-marosimi: sifat-gate (embedder yuz topmasa FaceError) + tenant-dedup 1:N."""
    vec, model_ver = await _embed(image_bytes)
    s = get_settings()

    # Dedup: shu org'da boshqa xodimga juda o'xshash yuz bormi?
    dup = (
        await session.execute(
            select(
                FaceEmbedding.user_id,
                (1 - FaceEmbedding.embedding.cosine_distance(vec)).label("sim"),
            )
            .where(FaceEmbedding.active.is_(True), FaceEmbedding.user_id != user_id)
            .order_by(FaceEmbedding.embedding.cosine_distance(vec))
            .limit(1)
        )
    ).first()
    if dup is not None and dup.sim >= s.face_dedup_threshold:
        raise DuplicateFaceError(dup.user_id, float(dup.sim))

    fe = FaceEmbedding(
        org_id=org_id,
        user_id=user_id,
        embedding=vec,
        source="enrollment",
        model_ver=model_ver,
        active=True,
    )
    session.add(fe)
    # face_enrolled_at belgilash
    user = await session.get(User, user_id)
    if user is not None:
        from datetime import UTC, datetime

        user.face_enrolled_at = datetime.now(UTC)
    await session.flush()
    return EnrollResult(embedding_id=str(fe.id), model_ver=model_ver)


@dataclass
class VerifyResult:
    score: float
    verdict: str  # "verified" | "review" | "rejected" | "no_enrollment"


async def verify(
    session: AsyncSession, *, user_id: uuid.UUID, image_bytes: bytes
) -> VerifyResult:
    """1:1 — probe embeddingni xodimning faol shablonlariga solishtirish (eng yaqin)."""
    vec, _ = await _embed(image_bytes)
    s = get_settings()
    row = (
        await session.execute(
            select((1 - FaceEmbedding.embedding.cosine_distance(vec)).label("sim"))
            .where(FaceEmbedding.user_id == user_id, FaceEmbedding.active.is_(True))
            .order_by(FaceEmbedding.embedding.cosine_distance(vec))
            .limit(1)
        )
    ).first()
    if row is None:
        return VerifyResult(score=0.0, verdict="no_enrollment")
    score = float(row.sim)
    if score >= s.face_verify_threshold:
        verdict = "verified"
    elif score >= s.face_review_threshold:
        verdict = "review"
    else:
        verdict = "rejected"
    return VerifyResult(score=score, verdict=verdict)


@dataclass
class IdentifyResult:
    user_id: str | None
    score: float
    margin: float


async def identify(
    session: AsyncSession, *, image_bytes: bytes
) -> IdentifyResult:
    """1:N (aktivatsiya) — org galereyasi bo'ylab eng yaqin. Qabul: top-1 >= chegara
    VA (top-1 − top-2) >= margin. Aks holda user_id=None (fallback: OTP)."""
    vec, _ = await _embed(image_bytes)
    s = get_settings()
    rows = (
        await session.execute(
            select(
                FaceEmbedding.user_id,
                (1 - FaceEmbedding.embedding.cosine_distance(vec)).label("sim"),
            )
            .where(FaceEmbedding.active.is_(True))
            .order_by(FaceEmbedding.embedding.cosine_distance(vec))
            .limit(2)
        )
    ).all()
    if not rows:
        return IdentifyResult(user_id=None, score=0.0, margin=0.0)
    top = rows[0]
    top2_sim = float(rows[1].sim) if len(rows) > 1 else 0.0
    margin = float(top.sim) - top2_sim
    if float(top.sim) >= s.face_identify_threshold and margin >= s.face_identify_margin:
        return IdentifyResult(user_id=str(top.user_id), score=float(top.sim), margin=margin)
    return IdentifyResult(user_id=None, score=float(top.sim), margin=margin)


# Xatoni tashqi modullar ushlashi uchun re-export
__all__ = [
    "DuplicateFaceError",
    "EnrollResult",
    "FaceError",
    "IdentifyResult",
    "VerifyResult",
    "enroll",
    "identify",
    "verify",
]

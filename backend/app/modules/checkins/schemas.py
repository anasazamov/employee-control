import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FaceResultIn(BaseModel):
    """Qurilmadagi yuz-natija — FAQAT maslahat (UX); yakuniy hukm server
    yuz-worker'ida (keyingi bosqich, InsightFace)."""

    local_match: bool | None = None
    local_score: float | None = Field(default=None, ge=0, le=1)
    liveness_passed: bool | None = None


class CheckinIn(BaseModel):
    checkin_id: uuid.UUID  # mijoz yaratadi — idempotentlik kaliti
    ts: datetime  # capture vaqti (qurilma)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    site_id: uuid.UUID | None = None  # berilmasa lokatsiyadan avto-aniqlanadi
    comment: str | None = Field(default=None, max_length=4000)
    face: FaceResultIn = FaceResultIn()
    device_integrity: dict = Field(default_factory=dict)  # is_mock, root_flags...
    signature: str | None = None  # base64 ECDSA(kanonik payload)


class CheckinOut(BaseModel):
    id: str
    user_id: str
    site_id: str | None
    ts: datetime
    lat: float
    lon: float
    inside_geofence: bool | None
    verdict: str
    verdict_reasons: list[str]
    risk_score: int
    comment: str | None
    duplicate: bool = False


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ReviewIn(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=3, max_length=1000)

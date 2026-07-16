import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LocationPointIn(BaseModel):
    point_uuid: uuid.UUID  # mijoz yaratadi — idempotentlik kaliti
    ts: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    speed_mps: float | None = None
    heading: float | None = None
    battery: int | None = Field(default=None, ge=0, le=100)
    is_mock: bool = False  # Android isMock — risk-ball signali, bloklamaydi
    provider: str | None = None


class LocationBatchIn(BaseModel):
    points: list[LocationPointIn] = Field(min_length=1, max_length=200)


class LocationBatchOut(BaseModel):
    accepted: int
    duplicates: int
    current_site_id: str | None

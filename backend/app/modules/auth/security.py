import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from app.config import get_settings


def issue_token(
    *,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    role: str,
    kind: Literal["access", "refresh"],
    device_id: uuid.UUID | None = None,
) -> str:
    s = get_settings()
    ttl = s.jwt_access_ttl_seconds if kind == "access" else s.jwt_refresh_ttl_seconds
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    if device_id is not None:
        payload["device_id"] = str(device_id)
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str, *, expected_kind: Literal["access", "refresh"]) -> dict:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    if payload.get("kind") != expected_kind:
        raise jwt.InvalidTokenError(f"token kind mismatch: expected {expected_kind}")
    return payload

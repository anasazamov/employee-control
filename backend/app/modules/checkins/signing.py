"""Qurilma-imzo (reja §9): check-in kanonik JSON'i qurilmaning Keystore/Secure
Enclave'dagi P-256 kaliti bilan imzolanadi; server ochiq kalit bilan tekshiradi.

Siyosat:
  - imzo YAROQSIZ (kalit bor, tekshiruv o'tmadi) → 400 hard-reject (dalil buzilgan);
  - imzo/kalit YO'Q → qabul, lekin `unsigned` risk-flag (eski ilova-versiya,
    Keystore'siz qurilma) — yumshoq signal qattiq bloklamaydi (reja §9).

Kanonik payload: quyidagi maydonlar, ajratgichsiz JSON, kalitlar saralangan —
mobil mijoz AYNAN shu qurilishni imzolaydi.
"""

import base64
import json
import uuid
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.utils import iso_utc


def canonical_payload(
    *,
    checkin_id: uuid.UUID,
    ts: datetime,
    lat: float,
    lon: float,
    site_id: uuid.UUID | None,
    comment: str | None,
) -> bytes:
    doc = {
        "checkin_id": str(checkin_id),
        "ts": iso_utc(ts),
        "lat": lat,
        "lon": lon,
        "site_id": str(site_id) if site_id else None,
        "comment": comment,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def verify_signature(pubkey_pem: str, payload: bytes, signature_b64: str) -> bool:
    try:
        key = serialization.load_pem_public_key(pubkey_pem.encode())
        if not isinstance(key, ec.EllipticCurvePublicKey):
            return False
        key.verify(
            base64.b64decode(signature_b64), payload, ec.ECDSA(hashes.SHA256())
        )
        return True
    except (InvalidSignature, ValueError):
        return False

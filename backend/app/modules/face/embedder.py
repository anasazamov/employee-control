"""Yuz-embedder (reja §6). Pluggable — pipeline model-agnostik (model_ver bilan).

Ikki backend (EC_FACE_BACKEND):
- `stub`  — DETERMINISTIK, faqat dev/test. Rasm baytlaridan 512-vektor hosil qiladi;
            HAQIQIY yuz-tanish EMAS (bir xil bayt → bir xil vektor). Prod'da ishlatilmaydi.
- `insightface` — server: InsightFace FaceAnalysis (SCRFD detect + ArcFace embed +
            anti-spoof imkoniyati). Model og'irliklari (buffalo_*) notijorat-litsenziyada —
            tijorat-deploy oldidan litsenziyalangan/o'z-o'qitilgan model bilan almashtirish
            kerak. Kod (insightface) Apache-2.0.

Barchasi 512-o'lchamli, L2-normalizatsiyalangan vektor qaytaradi (pgvector cosine)."""

import hashlib
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

EMBED_DIM = 512


class FaceError(Exception):
    """Yuz topilmadi / sifat past / bir nechta yuz."""


class Embedder(Protocol):
    model_ver: str

    def embed(self, image_bytes: bytes) -> list[float]:
        """Rasmdagi (bitta) yuzdan L2-normal 512-vektor. Yuz yo'q/ko'p → FaceError."""
        ...


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0:
        return vec
    return [x / norm for x in vec]


class StubEmbedder:
    """Deterministik test-embedder. Bir xil rasm → bir xil vektor; turli rasm → turli.
    HAQIQIY yuz-tanish emas — faqat pipeline/oqim testlari uchun."""

    model_ver = "stub-v1"

    def embed(self, image_bytes: bytes) -> list[float]:
        if not image_bytes or len(image_bytes) < 4:
            raise FaceError("bo'sh yoki yaroqsiz rasm")
        # Baytlardan deterministik pseudo-vektor (SHA256 seed → takroriy)
        vec: list[float] = []
        counter = 0
        while len(vec) < EMBED_DIM:
            h = hashlib.sha256(image_bytes + counter.to_bytes(4, "big")).digest()
            for i in range(0, len(h), 2):
                if len(vec) >= EMBED_DIM:
                    break
                vec.append((int.from_bytes(h[i : i + 2], "big") / 65535.0) - 0.5)
            counter += 1
        return _l2_normalize(vec)


class InsightFaceEmbedder:
    """Server-backend. Lazy-yuklanadi (og'ir importlar faqat kerak bo'lganda)."""

    def __init__(self) -> None:
        import numpy as np  # noqa: F401
        from insightface.app import FaceAnalysis

        s = get_settings()
        self.model_ver = f"insightface-{s.face_model_pack}"
        self._app = FaceAnalysis(
            name=s.face_model_pack, providers=["CPUExecutionProvider"]
        )
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def embed(self, image_bytes: bytes) -> list[float]:
        import cv2
        import numpy as np

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise FaceError("rasmni o'qib bo'lmadi")
        faces = self._app.get(img)
        if len(faces) == 0:
            raise FaceError("yuz topilmadi")
        if len(faces) > 1:
            raise FaceError("bir nechta yuz — bitta yuz kerak")
        emb = faces[0].normed_embedding  # allaqachon L2-normal
        return emb.astype(float).tolist()


@lru_cache
def get_embedder() -> Embedder:
    backend = get_settings().face_backend
    if backend == "insightface":
        return InsightFaceEmbedder()
    return StubEmbedder()

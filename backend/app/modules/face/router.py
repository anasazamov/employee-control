"""Yuz-enrollment endpoint (reja §6). HR-marosimi: xodim rasmini yuklab, embedding
saqlaydi + tenant-dedup. Check-in server-verifikatsiyasi checkins.service ichida."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.models import User
from app.modules.face import service
from app.modules.face.embedder import FaceError
from app.modules.rbac.deps import TenantContext, require_role
from app.modules.tenancy.status import require_active_org

router = APIRouter(prefix="/v1/users", tags=["face"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024


class EnrollOut(BaseModel):
    embedding_id: str
    model_ver: str
    user_id: str


@router.post("/{user_id}/face/enroll", response_model=EnrollOut)
async def enroll_face(
    user_id: uuid.UUID,
    file: UploadFile,
    ctx: TenantContext = Depends(require_role("org_admin", "hr")),
    _active: TenantContext = Depends(require_active_org),
):
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "rasm juda katta")
    async with ctx.session() as s:
        user = await s.get(User, user_id)
        if user is None:
            raise HTTPException(404, "xodim topilmadi")
        try:
            res = await service.enroll(
                s, org_id=ctx.org_id, user_id=user_id, image_bytes=data
            )
        except FaceError as e:
            raise HTTPException(422, f"yuz sifati past: {e}") from e
        except service.DuplicateFaceError as e:
            raise HTTPException(
                409,
                f"bu yuz allaqachon boshqa xodimga tegishli (o'xshashlik {e.score:.2f})",
            ) from e
        # TODO(audit): face_enrolled → audit_log; TODO(v2): qayta-enrollment 4-ko'z
        return EnrollOut(
            embedding_id=res.embedding_id, model_ver=res.model_ver, user_id=str(user_id)
        )

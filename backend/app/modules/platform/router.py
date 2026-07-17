"""Platforma-konsol API (/platform) — tenant-RBAC'dan TASHQARIDA, statik platforma-
kaliti bilan (X-Platform-Key). MVP; v2: platform_users + MFA (reja §14).

MUHIM: bu endpoint'lar biometrika/lokatsiya/check-in TAFSILOTLARINI qaytarmaydi —
faqat tenant-metadata va metering (reja §14: "biometrika/lokatsiyalar hech qachon")."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.modules.platform import service

router = APIRouter(prefix="/platform", tags=["platform"])


async def require_platform_key(x_platform_key: str = Header(default="")) -> None:
    if x_platform_key != get_settings().platform_api_key:
        raise HTTPException(status_code=401, detail="platforma kaliti yaroqsiz")


class TenantOut(BaseModel):
    id: str
    slug: str
    name: str
    status: str
    plan: str
    employees: int


@router.get(
    "/tenants",
    response_model=list[TenantOut],
    dependencies=[Depends(require_platform_key)],
)
async def list_tenants():
    return [TenantOut(**t.__dict__) for t in await service.list_tenants()]


class ProvisionIn(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, pattern="^[a-z0-9-]+$")
    owner_phone: str = Field(min_length=5)
    owner_name: str = "Org Admin"
    plan: str = Field(default="trial", pattern="^(trial|basic|pro|enterprise)$")
    # Org-admin login-kredensiali (ixtiyoriy)
    owner_username: str | None = Field(default=None, min_length=3, max_length=128)
    owner_password: str | None = Field(default=None, min_length=6, max_length=128)


@router.post("/tenants", dependencies=[Depends(require_platform_key)], status_code=201)
async def provision_tenant(body: ProvisionIn):
    return await service.provision(
        name=body.name,
        slug=body.slug,
        owner_phone=body.owner_phone,
        owner_name=body.owner_name,
        plan=body.plan,
        owner_username=body.owner_username,
        owner_password=body.owner_password,
    )


class TenantPatch(BaseModel):
    status: str | None = Field(
        default=None, pattern="^(provisioning|active|grace|suspended|offboarding|purged)$"
    )
    plan: str | None = Field(default=None, pattern="^(trial|basic|pro|enterprise)$")


@router.patch(
    "/tenants/{org_id}", response_model=TenantOut, dependencies=[Depends(require_platform_key)]
)
async def update_tenant(org_id: uuid.UUID, body: TenantPatch):
    row = await service.update_tenant(org_id, status=body.status, plan=body.plan)
    if row is None:
        raise HTTPException(404, "tenant topilmadi")
    return TenantOut(**row.__dict__)


class SnapshotIn(BaseModel):
    snapshot_date: date | None = None  # None → bugun


@router.post("/usage/snapshot", dependencies=[Depends(require_platform_key)])
async def run_snapshot(body: SnapshotIn):
    """Kunlik metering-snapshot (beat-job qo'lda ham chaqiriladi)."""
    from datetime import UTC, datetime

    d = body.snapshot_date or datetime.now(UTC).date()
    n = await service.snapshot_usage(d)
    return {"snapshot_date": d.isoformat(), "tenants_processed": n}

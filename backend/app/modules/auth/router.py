from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.modules.auth import service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class InviteResolveIn(BaseModel):
    token: str = Field(min_length=8)


class InviteResolveOut(BaseModel):
    org_id: str
    org_name: str
    masked_phone: str | None


@router.post("/invites/resolve", response_model=InviteResolveOut)
async def resolve_invite(body: InviteResolveIn):
    try:
        r = await service.resolve_invite(body.token)
    except service.AuthError as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    return InviteResolveOut(
        org_id=str(r.org_id), org_name=r.org_name, masked_phone=r.masked_phone
    )


class OtpRequestIn(BaseModel):
    token: str


class OtpRequestOut(BaseModel):
    sent: bool = True
    dev_code: str | None = None  # faqat DEBUG rejimida


@router.post("/otp/request", response_model=OtpRequestOut)
async def request_otp(body: OtpRequestIn):
    try:
        dev_code = await service.request_otp(invite_token=body.token)
    except service.AuthError as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    return OtpRequestOut(dev_code=dev_code)


class DeviceIn(BaseModel):
    platform: str
    fingerprint: str
    model: str | None = None
    # Keystore/Secure Enclave'da yaratilgan P-256 ochiq kalit (PEM) —
    # check-in imzolarini tekshirish uchun (reja §7.5, §9)
    pubkey: str | None = None


class ActivateIn(BaseModel):
    token: str
    otp_code: str = Field(min_length=4, max_length=8)
    device: DeviceIn


@router.post("/activate")
async def activate(body: ActivateIn):
    try:
        return await service.activate(
            invite_token=body.token,
            otp_code=body.otp_code,
            device_platform=body.device.platform,
            device_fingerprint=body.device.fingerprint,
            device_model=body.device.model,
            device_pubkey=body.device.pubkey,
        )
    except service.AuthError as e:
        raise HTTPException(status_code=400, detail=e.detail) from e

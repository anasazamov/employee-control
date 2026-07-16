"""Obyektlar (sites) CRUD. Geofence MVP'da markaz+radius; polygon-editor v-keyingi
(geom ustuni sxemada tayyor). Org-chegara RLS'da — bu yerda faqat rol tekshiriladi."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import literal_column, select

from app.geo import point_ewkt
from app.models import Site, SitePresence, User
from app.modules.rbac.deps import TenantContext, get_context, require_role

router = APIRouter(prefix="/v1/sites", tags=["sites"])


class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=150, ge=30, le=5000)
    min_dwell_minutes: int = Field(default=15, ge=0, le=480)
    address: str | None = None


class SitePatch(BaseModel):
    name: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    radius_m: int | None = Field(default=None, ge=30, le=5000)
    min_dwell_minutes: int | None = Field(default=None, ge=0, le=480)
    address: str | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class SiteOut(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    radius_m: int
    min_dwell_minutes: int
    address: str | None
    status: str


# lat/lon asosiy so'rov bilan birga keladi — qatorma-qator qo'shimcha SELECT yo'q (N+1'siz)
_LAT_COL = literal_column("ST_Y(sites.center::geometry)").label("lat")
_LON_COL = literal_column("ST_X(sites.center::geometry)").label("lon")


def _out(site: Site, lat: float, lon: float) -> SiteOut:
    return SiteOut(
        id=str(site.id),
        name=site.name,
        lat=lat,
        lon=lon,
        radius_m=site.radius_m,
        min_dwell_minutes=site.min_dwell_minutes,
        address=site.address,
        status=site.status,
    )


async def _fetch_out(session, site_id: uuid.UUID) -> SiteOut | None:
    row = (
        await session.execute(
            select(Site, _LAT_COL, _LON_COL).where(Site.id == site_id)
        )
    ).first()
    return _out(row.Site, row.lat, row.lon) if row else None


@router.post("", response_model=SiteOut, status_code=201)
async def create_site(
    body: SiteIn, ctx: TenantContext = Depends(require_role("org_admin", "hr"))
):
    async with ctx.session() as s:
        site = Site(
            org_id=ctx.org_id,
            name=body.name,
            address=body.address,
            center=point_ewkt(lat=body.lat, lon=body.lon),
            radius_m=body.radius_m,
            min_dwell_minutes=body.min_dwell_minutes,
        )
        s.add(site)
        await s.flush()
        # TODO(audit): site_created → audit_log
        return _out(site, body.lat, body.lon)


@router.get("", response_model=list[SiteOut])
async def list_sites(ctx: TenantContext = Depends(get_context)):
    async with ctx.session() as s:
        rows = await s.execute(
            select(Site, _LAT_COL, _LON_COL).order_by(Site.created_at)
        )
        return [_out(r.Site, r.lat, r.lon) for r in rows]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(site_id: uuid.UUID, ctx: TenantContext = Depends(get_context)):
    async with ctx.session() as s:
        out = await _fetch_out(s, site_id)
        if out is None:
            raise HTTPException(404, "obyekt topilmadi")
        return out


@router.patch("/{site_id}", response_model=SiteOut)
async def patch_site(
    site_id: uuid.UUID,
    body: SitePatch,
    ctx: TenantContext = Depends(require_role("org_admin", "hr")),
):
    async with ctx.session() as s:
        row = (
            await s.execute(select(Site, _LAT_COL, _LON_COL).where(Site.id == site_id))
        ).first()
        if row is None:
            raise HTTPException(404, "obyekt topilmadi")
        site = row.Site
        data = body.model_dump(exclude_unset=True)
        lat, lon = data.pop("lat", None), data.pop("lon", None)
        for k, v in data.items():
            setattr(site, k, v)
        new_lat = lat if lat is not None else row.lat
        new_lon = lon if lon is not None else row.lon
        if lat is not None or lon is not None:
            site.center = point_ewkt(lat=new_lat, lon=new_lon)
        await s.flush()
        # TODO(v2): geofence-o'zgartirish to'rt-ko'z tasdiqlashdan o'tadi (reja §13)
        return _out(site, new_lat, new_lon)


class OccupantOut(BaseModel):
    user_id: str
    full_name: str
    entered_at: datetime


@router.get("/{site_id}/occupants", response_model=list[OccupantOut])
async def occupants(site_id: uuid.UUID, ctx: TenantContext = Depends(get_context)):
    """Hozir obyekt ichida bo'lganlar (site_presence ochiq qatorlari)."""
    async with ctx.session() as s:
        rows = (
            await s.execute(
                select(SitePresence.user_id, User.full_name, SitePresence.entered_at)
                .join(User, User.id == SitePresence.user_id)
                .where(SitePresence.site_id == site_id, SitePresence.exited_at.is_(None))
                .order_by(SitePresence.entered_at)
            )
        ).all()
        return [
            OccupantOut(user_id=str(r.user_id), full_name=r.full_name, entered_at=r.entered_at)
            for r in rows
        ]

# Employee Control — Dala Xodimlarini Nazorat Qilish Platformasi

Multi-tenant SaaS: dala xodimlarining obyektda bo'lganini isbotlaydigan platforma —
**to'g'ri odam** (yuz), **to'g'ri joy** (GPS + geofence), **to'g'ri vaqt** (server timestamp + imzolangan yozuv).

To'liq arxitektura va yo'l xaritasi: [docs/PLAN.md](docs/PLAN.md)

## Tuzilma

```
backend/   FastAPI modulli monolit (api | ws | worker | beat) + Alembic + pytest
mobile/    Flutter ilova (xodim + rahbar rejimlari)
web/       React + TS + Vite (tenant-admin + /platform konsol)
infra/     docker-compose, nginx, monitoring
docs/      reja, API-kontrakt, shablonlar
```

## Dev-muhitni ishga tushirish

```bash
# 1. Infratuzilma (PostgreSQL+Timescale+PostGIS+pgvector, Redis, MinIO)
cd infra && docker compose -f docker-compose.dev.yml up -d

# 2. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli provision-tenant --name "Demo Tashkilot" --slug demo --owner-phone +998901234567
uvicorn app.main:app --reload

# 3. Web
cd web && npm install && npm run dev
```

## Asosiy tamoyillar

- **Bepul/ochiq-manba vositalar birinchi** — pullik vosita faqat bepul muqobili yo'q bo'lsa.
- **Server — yagona haqiqat manbai**: qurilmadagi tekshiruvlar faqat UX; yuridik kuchga ega qarorlar serverda.
- **Tenant-izolyatsiya uch qatlamda**: JWT org-claim → FastAPI dependency (`SET LOCAL app.org_id`) → Postgres RLS.
- **Append-only dalillar**: checkins/location_points/audit_log — UPDATE/DELETE yo'q.

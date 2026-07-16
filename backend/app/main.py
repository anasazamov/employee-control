from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.models import User
from app.modules.auth.router import router as auth_router
from app.modules.checkins.router import router as checkins_router
from app.modules.history.router import router as history_router
from app.modules.org.departments import router as departments_router
from app.modules.org.users import router as users_router
from app.modules.rbac.deps import TenantContext, get_context
from app.modules.shifts.router import router as shifts_router
from app.modules.sites.router import router as sites_router
from app.modules.tracking.router import router as tracking_router
from app.modules.tracking.ws import router as ws_router


def create_app() -> FastAPI:
    app = FastAPI(title="Employee Control API", version="0.1.0")

    if get_settings().debug:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(auth_router)
    app.include_router(departments_router)
    app.include_router(users_router)
    app.include_router(sites_router)
    app.include_router(tracking_router)
    app.include_router(checkins_router)
    app.include_router(shifts_router)
    app.include_router(history_router)
    app.include_router(ws_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/v1/me")
    async def me(ctx: TenantContext = Depends(get_context)):
        async with ctx.session() as s:
            user = await s.scalar(select(User).where(User.id == ctx.user_id))
            if user is None:
                return {"error": "user not found"}
            return {
                "id": str(user.id),
                "org_id": str(ctx.org_id),
                "role": user.role,
                "full_name": user.full_name,
            }

    return app


app = create_app()

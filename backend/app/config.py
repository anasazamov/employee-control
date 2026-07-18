from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EC_", extra="ignore")

    debug: bool = True

    # CORS — web admin brauzeridan API'ga ulanish uchun ruxsat etilgan origin(lar),
    # vergul bilan ajratilgan. Prod'da .env (EC_CORS_ORIGINS) orqali web admin
    # domeni beriladi. Bo'sh qiymat = CORS middleware umuman qo'shilmaydi.
    # `debug`dan mustaqil — staging (debug=false) da ham web admin ishlashi kerak.
    cors_origins: str = "http://localhost:5173"

    # Runtime ulanish — RLS'ni chetlab o'tolmaydigan app_user roli bilan.
    # Dev-portlar 5433/6380 (docker-compose.dev.yml) — 5432/6379 boshqa loyihalar bilan
    # to'qnashmasligi uchun.
    database_url: str = (
        "postgresql+asyncpg://app_user:app_password@localhost:5433/employee_control"
    )
    # Migratsiyalar superuser bilan yuradi (extension/rol/policy yaratish uchun).
    migrations_database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5433/employee_control"
    )

    redis_url: str = "redis://localhost:6380/0"

    jwt_secret: str = "dev-secret-change-me-0123456789abcdef"  # >=32 bayt (HS256 talabi)
    jwt_access_ttl_seconds: int = 15 * 60
    jwt_refresh_ttl_seconds: int = 30 * 24 * 3600

    otp_ttl_seconds: int = 5 * 60
    invite_ttl_hours: int = 72

    # Platforma-konsol kaliti (MVP — statik kalit; v2: platform_users + MFA).
    # Prod'da .env orqali kuchli qiymatga almashtiriladi.
    platform_api_key: str = "dev-platform-key-change-me"

    # MinIO (selfie/foto — presigned PUT bilan mobil to'g'ridan yuklaydi)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False  # dev: HTTP; prod: TLS
    selfie_url_ttl_seconds: int = 5 * 60

    # Yuz-verifikatsiya (reja §6)
    face_backend: str = "stub"  # "stub" (dev/test) | "insightface" (server)
    face_model_pack: str = "buffalo_s"  # server RAM-cheklovi uchun kichik model
    # 1:1 verify chegaralari (pilotda kalibrlanadi — reja §6). cosine:
    face_verify_threshold: float = 0.45  # >= → VERIFIED
    face_review_threshold: float = 0.30  # 0.30–0.45 → REVIEW; < 0.30 → REJECTED
    # 1:N identify (aktivatsiya) — qat'iyroq
    face_identify_threshold: float = 0.45
    face_identify_margin: float = 0.10  # top1 − top2
    # enrollment-dedup: shu chegaradan yuqori o'xshashlik → bloklash
    face_dedup_threshold: float = 0.55

    @property
    def cors_origin_list(self) -> list[str]:
        """`cors_origins`ni ro'yxatga aylantiradi (bo'sh elementlar tashlanadi)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

# Deploy (staging / prod)

Izolyatsiyalangan Docker-stack. Band host'da ham xavfsiz: DB/Redis porti ochilmaydi,
API `8090`, MinIO `9010/9011`, alohida tarmoq/volume.

## Staging (test server: 89.117.49.131)

Ishlab turibdi. Public endpointlar:
- **API**: `http://89.117.49.131:8090` (mobil ilova shu manzilga ulanadi)
- **MinIO**: `http://89.117.49.131:9010` (presigned selfie-yuklash shu yerga)

Staging'da `DEBUG=true` — `POST /v1/auth/otp/request` OTP-kodini `dev_code` maydonida
qaytaradi (SMS ulanmagan, test uchun). Prod'da `DEBUG` qo'yilmaydi → `false`.

### Yangilash (GitHub orqali)

```bash
ssh -i <key> root@89.117.49.131
cd /root/employee-control && git pull
cd infra && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### Birinchi o'rnatish

```bash
git clone https://github.com/anasazamov/employee-control.git /root/employee-control
cd /root/employee-control/infra
cp .env.prod.example .env.prod   # va kuchli qiymatlar qo'ying
echo 'DEBUG=true' >> .env.prod    # faqat staging
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Migratsiya `migrate` servisi orqali avtomatik yuriladi (RLS + hypertable).

## Yuz-backend (stub → insightface)

Hozir `FACE_BACKEND=stub` (yengil, deterministik — pipeline'ni isbotlaydi, lekin
HAQIQIY yuz-tanish EMAS). Haqiqiy tekshiruv uchun `.env.prod`da `FACE_BACKEND=insightface`
qilinadi — LEKIN:

- `insightface` + `onnxruntime` + `opencv` og'ir (~1GB dep, RAM zarur). Joriy test-server
  3.8GB RAM va 9 boshqa loyiha bilan band — insightface OOM xavfi bor.
- Prod'da: kamida 2GB bo'sh RAM ajratilgan alohida yuz-worker (Celery `face` queue) tavsiya.
- Model og'irliklari (`buffalo_*`) **notijorat-litsenziyada** — tijorat-deploy oldidan
  litsenziyalangan yoki o'z-o'qitilgan model bilan almashtiring (pipeline model-agnostik).

Backend image'ga insightface qo'shish uchun `backend/pyproject.toml`ga
`insightface`, `onnxruntime`, `opencv-python-headless` qo'shiladi va image qayta build qilinadi.

## Portlar xulosasi

| Servis | Ichki | Public | Izoh |
|---|---|---|---|
| API | 8000 | 8090 | mobil + web |
| MinIO API | 9000 | 9010 | presigned yuklash |
| MinIO console | 9001 | 9011 | admin |
| PostgreSQL | 5432 | — | faqat ichki tarmoq |
| Redis | 6379 | — | faqat ichki tarmoq |

## Prod nginx (ixtiyoriy)

Public HTTPS uchun API'ni mavjud nginx ortiga qo'yish (TLS): `location /api/ { proxy_pass
http://127.0.0.1:8090/; }` va MinIO uchun alohida subdomain. Staging'da to'g'ridan-to'g'ri
port ishlatilyapti (cleartext — mobil `usesCleartextTraffic`).

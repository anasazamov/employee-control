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

## Yuz-backend (insightface — staging'da YONIQ)

Staging'da `FACE_BACKEND=insightface` (haqiqiy ArcFace yuz-tanish) yoqilgan va
tekshirilgan: bir odamning turli fotolari mos (cosine ~0.72 → verified), boshqa
odam rad (~ -0.03 → rejected). Model: `buffalo_s`, det_size 320 (RAM tejash).

**Yoqish (`.env.prod`):**
```
FACE_BACKEND=insightface
FACE_MODEL_PACK=buffalo_s
INSTALL_FACE=true     # api image insightface bilan build qilinadi
API_MEM_LIMIT=2g      # host himoyasi — limit oshsa faqat api restart
```
So'ng: `docker compose -f docker-compose.prod.yml --env-file .env.prod build api && ... up -d api`.

**RAM realligi:** api-konteyner model yuklangach ~650MB (2GB limit ichida). Joriy
3.8GB umumiy serverda 9 boshqa loyiha bilan barqaror ishladi, lekin bo'sh RAM kam
(~150-200MB). Prod'da: **alohida yuz-worker** (Celery `face` queue, 2GB+ ajratilgan)
tavsiya — api'ni og'ir inference'dan ajratadi.

**Model download:** birinchi yuz-so'rovda `buffalo_s` (~50MB) yuklanadi (~10s), keyin
lru_cache'da qoladi. `libxcb1`/`libgl1` va boshqa opencv runtime-libs Dockerfile'da.

**Litsenziya:** `buffalo_*` og'irliklari **notijorat** — tijorat-deploy oldidan
litsenziyalangan yoki o'z-o'qitilgan model bilan almashtiring (pipeline model-agnostik,
`model_ver` maydoni shuning uchun).

**Stub'ga qaytarish** (RAM muammosi bo'lsa): `.env.prod`da `FACE_BACKEND=stub` + api restart.

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

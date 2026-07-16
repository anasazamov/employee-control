# Dala Xodimlarini Nazorat Qilish Platformasi (Multi-tenant SaaS) — Yakuniy Reja

## 1. Kontekst

**Mahsulot**: dala xodimlarining obyektda bo'lganini isbotlaydigan SaaS-platforma — **ko'p tashkilotga sotiladi** (multi-tenant). Har bir mijoz-tashkilot (tenant) o'z bo'limlari, xodimlari, obyektlari, biometrik galereyasi bilan to'liq izolyatsiyada ishlaydi.

**Birinchi mijoz (design-partner)**: qurilish sohasini nazorat qiluvchi davlat tashkiloti (500–5000 xodim). Muammo: inspektorlar obyektga bormasdan "borgan" deb hisobot berishi. Tizim uch narsani isbotlaydi: **to'g'ri odam** (yuz), **to'g'ri joy** (GPS + geofence), **to'g'ri vaqt** (server timestamp + imzolangan yozuv). Sotuv pozitsiyasi: "kuzatuv" emas — **"isbotlanadigan mavjudlik"** (dalil-zanjiri: liveness selfie + server yuz-tekshiruvi + imzolangan ikki-soatli yozuv + geofence dwell + append-only audit). UZ bozorida GPS-trekerlar "telefon qayerdaydi"ni, devor-terminallar "yuz ofisda edi"ni isbotlaydi — BYOD'da dalada ikkalasini birlashtirgan mahsulot yo'q.

Repo (`D:\srg\employee-control`) bo'sh — noldan boshlanadi. Reja 6 ta mustaqil arxitektura tahlili (anti-firibgarlik, backend, mobil/web, O'zbekiston ekotizimi, tenant-izolyatsiya, SaaS-mahsulot) va zidliklarni hal qilgan tanqidiy tahlil asosida tuzildi.

## 2. Tasdiqlangan qarorlar (foydalanuvchi tanlovi)

| Qaror | Tanlov |
|---|---|
| Model | **Multi-tenant SaaS** — ko'p tashkilotga sotiladi; yirik/davlat mijozlar uchun dedicated/on-prem varianti (bitta kod baza, `TENANCY_MODE` flag) |
| Backend | Python **FastAPI** + PostgreSQL/PostGIS |
| Mobil | **Flutter** (Android + iOS, bitta kod baza, bitta store-binary) |
| Yuz tekshiruvi | **Gibrid**: qurilmada ML Kit (liveness) + MobileFaceNet; serverda InsightFace **majburiy qayta tekshiruv** |
| Masshtab | Tenant boshiga 500–5000 xodim; platforma ko'p tenant |
| Qurilmalar | **BYOD** — xodimlarning shaxsiy telefonlari |
| GPS tracking | **Bepul stack** (geolocator + custom foreground service) — Transistor litsenziyasisiz |
| MyID | **Ishlatilmaydi** — o'z yuz-tanish tizimi (HR ro'yxatga olish marosimi trust-root) |
| Xarita | **MapLibre GL + OpenStreetMap** (bepul, o'z serverida) — Yandex bepul tarifi monitoring-tizimlarni taqiqlaydi (§11); xarita-qatlam almashtiriladigan |
| Vositalar tamoyili | **Bepul/ochiq-manba birinchi**: pullik vosita faqat bepul muqobili umuman yo'q bo'lsa ishlatiladi (foydalanuvchi talabi) |

Muhim texnik eslatma: **ML Kit yuzni faqat aniqlaydi (detection), kimligini tanimaydi.** Shuning uchun: ML Kit = sifat nazorati + liveness; MobileFaceNet (TFLite, ~1 MB) = qurilmada tezkor 1:1 (faqat UX, yuridik kuchsiz); server InsightFace/ArcFace = **har check-in uchun majburiy yakuniy hukm**. Root qilingan telefon lokal natijani soxtalashtiradi, lekin serverga yuklangan rasmni serverning mustaqil baholashini soxtalashtira olmaydi.

## 3. Umumiy arxitektura

```
[Flutter ilova] ──HTTPS batch──> [nginx LB] ──> [FastAPI api ×2]──┬─> PostgreSQL 16 (+RLS)
  xodim + rahbar rejimi              │                            │   (PostGIS+Timescale+pgvector+ltree)
  GPS bufer (SQLite) offline         │                            ├─> Redis (t:{org}: prefiks — pub/sub,
  imzolangan check-in                │                            │    last-loc, presence, entitlements)
                                     │                            ├─> MinIO (bucket-per-tenant + KES kalit)
[React web admin] ──WS──> [FastAPI ws ×2] <──Redis pub/sub────────┤
[Platforma konsoli /platform/*]      │                            └─> Celery worker (face queue, InsightFace CPU,
                                 [Celery beat ×1] — retention,         tenant-fairness token-bucket)
                                  downsample, metering, hisobotlar
                                 [Tile-server (Martin)] — o'z OSM vector tile'lari (bepul, §11)
```

**Modulli monolit** — bitta FastAPI kod bazasi, bitta Docker image, 4 rol (`api`, `ws`, `worker`, `beat`). Microservices 3–6 kishilik jamoa uchun xato. Modullar: `auth`, `rbac`, `tenancy`, `tracking`, `checkins`, `face`, `sites`, `shifts`, `billing`, `reports`. Biometrika alohida DB-sxema + alohida DB-rol bilan izolyatsiya.

**Asosiy stack qarorlari**: Celery (Redis broker, alohida `face` queue) · yuz-worker **CPU** (InsightFace `buffalo_l` ≈150–250 ms/rasm/yadro — 8 yadro = burst'dan 10× zaxira) · ingestion **batched HTTPS POST** (WebSocket/MQTT emas — mobil tarmoqqa chidamli, idempotent) · TimescaleDB (siqish ~10–15×, retention, continuous aggregate) · pgvector (tenant-doirali exact cosine scan <10 ms, ANN keraksiz) · MinIO (presigned PUT, `checkin-photos`da object lock — dalil o'zgarmasligi).

## 4. Multi-tenant qatlam (SaaS yadrosi)

**Tenancy modeli: shared schema — har tenant-jadvalda `org_id UUID NOT NULL`.** Schema-per-tenant Timescale obyektlarini (hypertable+policy+aggregate) tenant soniga ko'paytiradi — 3–6 dev uchun o'lik yo'l; DB-per-tenant — bu dedicated-deploy modeli, cloud emas.

- **Timescale**: faqat vaqt bo'yicha partitsiya (org_id bo'yicha space-partitsiya YO'Q — mayda tenantlarda chunk-portlash); siqish `segmentby=(org_id, user_id)`; continuous aggregate GROUP BY'ga org_id qo'shiladi; retention global, tenant-override'lar tungi delete-job bilan.
- **pgvector**: har 1:N qat'iy `WHERE org_id=:org` — tenant-doiralash tezlikni oshiradi (≤5k vektor skan). Global vektor-indeks hech qachon qurilmaydi.
- **ltree**: har daraxt org-ildiz bilan: `o_{shortid}.boshqarma.hudud` — global unikal, GiST subtree so'rovlar o'zgarmaydi.

**Izolyatsiya — himoya qatlamlari (bitta unutilgan WHERE kompaniyani o'ldiradigan hodisa bo'lmasligi uchun):**
1. JWT'da `org_id` claim (token davomida o'zgarmas);
2. FastAPI dependency: org-status tekshiruvi (Redis kesh 60 s — suspension shu yerda) + tranzaksiyaga `SET LOCAL app.org_id`;
3. **Postgres RLS har tenant-jadvalda**: `USING (org_id = current_setting('app.org_id')::uuid)`; app-rol `BYPASSRLS`siz; GUC yo'q = nol qator (leak emas);
4. Repository-qatlam baribir explicit org-filter qo'yadi (RLS = to'g'rilik, filter = tezlik).

**Boshqa tekisliklar**: WS kanallar `loc.{org_id}.{dept_path}` (subscribe'da JWT org tekshiriladi) · Redis kalitlar `t:{org_id}:` prefiks (bitta helper-modul quradi) · Celery `TenantTask` bazasi org_id'siz ishlamaydi, GUC+prefiksni o'zi o'rnatadi · face-queue **tenant-fairness token-bucket** enqueue'da (bitta toshgan tenant boshqalarning verdiktlarini kechiktirmaydi) · MinIO **bucket-per-tenant** (`t-{org_uuid}`) + **per-tenant SSE-KMS kalit (MinIO KES)** — offboarding'da kalit yo'q qilinadi = barcha fotolar kriptografik o'chirilgan · per-tenant API rate-limit, WS-cap, plan-limitlar.

**Yuz-doiralash**: 1:N identify va enrollment-dedup **qat'iy tenant ichida**. Bir odam ikki tashkilotda ishlashi mumkin (pudratchi) — ikki alohida yozuv, ikki alohida rozilik; **tenantlar aro biometrik solishtirish hech qachon qilinmaydi** (rozilik doirasidan tashqari ishlov — huquqiy mina). Qurilma-bog'lash (org_id, user_id) juftligi bo'yicha.

**Tenant hayot-sikli**: `provision_tenant` (idempotent CLI/task): organizations-qator, MinIO bucket+KES kalit, ltree-ildiz, default rollar, plan/limitlar, owner-invite — tenant <1 daqiqada tayyor. Suspension mashinasi `active → grace → suspended`: grace'da banner+to'liq funksiya; suspended'da **tracking va check-in TO'XTAYDI** (yetkazilmasligi mumkin bo'lgan biometrika yig'ish — huquqiy xavf), web read-only, eksport ochiq. Offboarding: eksport-paket → qat'iy purge (embeddinglar + KES-kalit yo'q qilish), isbotlanadigan. Backup: umumiy klaster pgBackRest + **tungi per-tenant logical eksport** (halol javob: shared-schema'dan bitta tenantni PITR qilib bo'lmaydi — kerak bo'lsa dedicated tier).

**Platforma operatsiyalari**: platforma-rollar tenant-RBAC'dan TASHQARIDA (`platform_owner/ops/support/billing`, alohida auth-realm, o'z MFA); default ko'rinish — faqat tenant-metadata, status, metering; **biometrika/foto/lokatsiyalar hech qachon** (RLS ham shuni majburlaydi). **Support-access**: tenant-admin vaqt-cheklangan (4–72 soat) ruxsat beradi → read-only impersonatsiya, har amal ikkala audit-logga (tenant + platforma), tenant ko'radi — jim kirish yo'q. Metering: append-only `billing_events` (faol-xodim soni tungi job, check-in/yuz-tekshiruv hisoblagichlari, MinIO storage).

## 5. Ma'lumotlar modeli

```sql
organizations  -- id, slug, name, status(provisioning|active|grace|suspended|offboarding|purged),
               -- plan, limits jsonb, settings jsonb (feature-flags, thresholds, terminologiya), kms_key_id, ltree_root
invites        -- org_id, employee_id (nullable — org-wide kod ham bo'ladi), token_hash, 72h TTL, used_at
support_sessions, billing_events (append-only), subscriptions, usage_snapshots, invoices
platform_users -- tenant-userlardan ALOHIDA
site_types     -- tenant-belgilaydigan lookup (nomi, ikon); shablondan seed
-- Barcha quyidagilar org_id NOT NULL + RLS policy bilan:
departments    -- ltree path ('o_abc.toshkent.inspeksiya2'); (org_id, path) unikal
users          -- role: org_admin|hr|dept_head|field_employee; (org_id, phone) unikal — telefon TENANT ichida unikal,
               -- global emas (pudratchi ikki org'da); attributes jsonb (tenant custom-fields)
user_scope_grants, devices -- partial unique (org_id, user_id) WHERE status='active'
shifts         -- smena jadvali; tracking faqat smena ichida
sites          -- geofence polygon YOKI center+radius (default 150 m); site_type; min_dwell; attributes jsonb
assignments    -- topshiriqlar: muddat, reveal_at (v2), status
site_presence  -- JONLI OBYEKT-BANDLIK: org_id, user_id, site_id, entered_at, exited_at (NULL = hozir ichkarida),
               -- dwell hisoblangan; enter/exit hodisalari shu yerdan; "kim qaysi obyektda" ning manbasi
checkins       -- GPS+aniqlik, geofence-ichidami, selfie_key, izoh, ondevice_score (maslahat),
               -- server_face_score, spoof_score, device_integrity jsonb, verdict(pending|verified|flagged|rejected),
               -- row_hash/prev_hash (v2 hash-zanjir)
face_embeddings -- vector(512), ≤5 faol/xodim, model_ver; btree(org_id), skan doim org-filtrli
location_points -- Timescale hypertable: org_id, ts, user_id, geog, accuracy, speed, battery, is_mock, point_uuid
audit_log, access_log -- append-only, org_id bilan
consents       -- biometrik rozilik: shablon-versiya, imzo vaqti, withdraw oqimi
```

**Append-only qoida (MVP)**: `checkins`, `location_points`, `audit_log`ga app-rol uchun UPDATE/DELETE granti YO'Q (offboarding-purge alohida karve-out). Tuzatishlar — `superseded_by` kompensatsion yozuv + majburiy sabab. Admin ham tarixni "tuzata" olmasligi — anti-korrupsiya yadrosi.

## 6. Yuz tekshiruvi pipeline

**Ro'yxatga olish (HR marosimi — ishonch ildizi):** HR (rol `hr:enroll`) 3–5 foto oladi yoki xodim o'z telefonidan yo'naltirilgan capture qiladi + HR tasdiqlaydi (500 xodim parallel ro'yxatdan o'tadi, ketma-ket emas — onboarding tezligi uchun muhim). Server sifat-nazorati (bitta yuz, ko'zlar-orasi ≥90 px, blur/yorug'lik, anti-spoof) → ArcFace embeddinglar → **tenant-ichi dedup 1:N majburiy** ("bu yuz sizning tashkilotingizda X xodimga tegishli"). Qayta-enrollment — sabab + audit (v2: ikkinchi tasdiqlovchi). Xodim shabloni faqat o'z bog'langan qurilmasiga, shifrlangan.

**Check-in tekshiruvi:**
- *Qurilmada (~1 s, maslahat)*: ML Kit detection + sifat → **tasodifiy 2 liveness-challenge** {ko'z yumish, chapga/o'ngga burilish, tabassum} → MobileFaceNet 1:1 → yashil belgi, izoh ochiladi, holat `PENDING_SERVER`.
- *Litsenziya-eslatma (bepul-vositalar talabi)*: InsightFace kodi ochiq, lekin ba'zi tayyor modellar (`buffalo_l`) notijorat-tadqiqot litsenziyasida — tijorat SaaS uchun MVP'da litsenziyasi tekshirilgan erkin muqobil tanlanadi (masalan, MIT-litsenziyali AdaFace/ochiq og'irliklar) yoki ochiq datasetlarda o'z modeli tayyorlanadi; pipeline model-agnostik (model_ver maydoni shuning uchun).
- *Serverda (majburiy, async ~2–5 s)*: imzo/nonce → SCRFD → passiv anti-spoof → ArcFace 1:1. Boshlang'ich chegaralar (pilotda kalibrlanadi): ≥0.50 VERIFIED · 0.35–0.50 REVIEW (selfie vs enrollment yonma-yon) · <0.35 REJECTED; anti-spoof fail → har qanday holda REJECTED + qizil bayroq. Muvaffaqiyatsiz urinishlar ham saqlanadi — dalil.
- *Fallback zinapoyasi*: 3× lokal fail → to'g'ri server; 5× → 30 daq lock + PIN/SMS OTP bilan `NO_BIOMETRIC` check-in (rahbar tasdig'isiz hisoblanmaydi); doimiy muammo → qayta-enrollment. "Doim PIN'da" xodim — o'zi monitoring metrikasi.

## 7. Aktivatsiya va "login ixtiyoriy"

**Org yuzdan OLDIN aniqlanishi shart** (tenantlar-aro 1:N mumkin emas). Oqim:
1. HR xodimni oldindan yaratadi (ism, telefon, bo'lim) va **invite** beradi: bir-martalik token, 72 h, QR + deep-link `https://app.<domen>/a/{token}` + 8-belgili qo'lda teriladigan kod.
2. Bitta store-binary link orqali ochiladi → `{org_id, nom, logo, rang, maskali-telefon}` → ilova tenant-kontekst oladi va o'zini "kiyintiradi" (per-tenant store-listing/white-label binary MVP'da YO'Q).
3. Invite xodimga bog'langani uchun server **1:1 verify** qiladi (galereya-foto bo'lsa) yoki selfie'ni enrollment-namuna sifatida HR-tasdiqqa yo'naltiradi. 1:N faqat org-wide umumiy kod uchun fallback: top-1 ≥0.55 **VA** (top-1−top-2) ≥0.10 **VA** anti-spoof pass.
4. **Majburiy ikkinchi omil (bir marta)**: HR bazasidagi raqamga SMS OTP (Eskiz.uz) — *yuz yolg'iz hech qachon qurilma bog'lamaydi* (o'xshash odam/foto akkaunt egallamasligi uchun).
5. **Qurilma-bog'lash**: Keystore/Secure Enclave P-256 kalit; **1 faol qurilma/(org, xodim)**; yangi bog'lash eskini bekor qiladi + xodim va bo'lim boshlig'iga xabar (tez almashish — firibgarlik signali).
6. **Kundalik**: token bilan ochiladi (parol yo'q); har check-in'da yuz 1:1. Rate-limit: identify 5/soat/qurilma. Rahbarlar (yuzga ro'yxatga olinmagan bo'lishi mumkin): telefon+OTP yo'li.

## 8. Jonli kuzatuv (background tracking) — bepul stack

**4–6 hafta alohida injiniring byudjeti, alohida egasi bilan**; batareya maqsadi ~5–8%/kun.
- **Android**: foreground service (`foregroundServiceType="location"`, doimiy bildirishnoma — yashirmaymiz: "Ish vaqtida kuzatuv yoniq 09:00–18:00"); ActivityRecognition adaptiv rejim: HARAKATDA distanceFilter 25 m · TURG'UN ≥3 daq → GPS o'chadi, 200 m chiqish-geofence qayta yoqadi; Doze uchun heartbeat (15 daq, batareya % bilan).
- **BYOD + Xiaomi/Vivo/Oppo** (UZ bozorida ustun): onboarding OEM'ni aniqlab autostart+battery-whitelist ekranlariga yetaklaydi; server "smena paytida qurilma jimib qoldi" alerti — qolganini shu ushlaydi (o'zi anti-firibgarlik signali).
- **iOS**: `UIBackgroundModes: location`, Always-ruxsat bosqichma-bosqich; significant-change + region monitoring.
- **Smena-cheklangan kuzatuv** (huquq + batareya + ishonch): smena tashqarisida **nol** lokatsiya; start/stop audit-logda.
- **Upload**: ≤50 nuqta yoki 60 s batch, gzip; offline → SQLite bufer (10k FIFO); idempotent `point_uuid`.
- **Real-time**: INSERT hypertable → **obyekt-rezolyutsiya** (quyida) → `HSET t:{org}:loc:last:{uid}` (ichida `current_site_id`) → PUBLISH `loc.{org}.{dept}` → ws-rol RBAC-doira fan-out. Jonli xarita Postgres'ga tegmaydi. Presence: 120 s nuqtasiz = offline.
- **Obyekt-rezolyutsiya ("kim qaysi obyektda")**: har lokatsiya-batchda server nuqtani tenant obyekt-geofence'lariga solishtiradi (geometriyalar Redis-keshda, point-in-polygon arzon). Flapping'ga qarshi gisterezis: ENTER = 2 ketma-ket ichki fix (yoki aniqligi radius/2 dan yaxshi 1 fix); EXIT = ≥2 daqiqa tashqarida. Natija: `site_presence` yozuvi ochiladi/yopiladi, `site_enter`/`site_exit` hodisalari WS'ga chiqadi, `t:{org}:site:occupants:{site_id}` Redis-set yangilanadi. Shu qatlam bir vaqtning o'zida: (a) rahbarga "X xodim hozir Obyekt №14 da"ni beradi, (b) dwell-talabni hisoblaydi, (c) xodim-timeline'da "Obyekt №14: 09:15–10:40" segmentlarini yaratadi.

## 9. Check-in oqimi (yadro sikl)

```
Trigger: A) geofence ENTER → lokal push "Siz «Obyekt №14» hududidasiz. Check-in?"
         B) qo'lda: yaqin obyektlar (>150 m — ruxsat, lekin oldindan bayroqlanadi)
1 OBYEKT   avtotanlangan obyekt (polygon + mening nuqtam)
2 YUZ      ML Kit + liveness → MobileFaceNet 1:1 (3× fail → baribir yuborishga ruxsat,
           'unverified_on_device' — dalada qattiq bloklanmaydi, server/review hal qiladi)
3 DALIL    selfie (avtomatik) + izoh (matn/ovoz, ixtiyoriy) + obyekt-fotosi (tenant sozlaydi)
4 YUBORISH kanonik JSON qurilma-kaliti bilan imzolanadi → POST /v1/checkins
           online → verdikt 1–2 s · offline → navbat, "signal topilganda yuboriladi"
```

- **Izoh**: yuz tasdiqlangach ochiladi, imzolangan yozuv ichida; keyingi izohlar append-only + audit; imzolangan yozuv o'zgarmaydi.
- **Dwell**: check-in tashrifni *ochadi*; geofence'da `min_dwell_minutes` (tenant sozlaydi, default 15) qolish shart — "mashinadan tushmasdan check-in" o'ladi.
- **Offline (odatiy hol)**: GPS offline ishlaydi; ikki soat (wall-clock + monotonic) yoziladi — soat-orqaga-surish sinxronda fosh (`clock_tampered`); offline check-in **hech qachon avto-tasdiqlanmaydi** — review + trail-korroboratsiya (iz obyekt tomon kelayotganmidi?).
- **Risk-ball (MVP)**: 0–100 kompozit (integrity, mock-bayroqlar, liveness, yuz-ball, dwell, harakat-mantiqiyligi, offline). Yashil avto-o'tadi, sariq → rahbar navbati, qizil → eskalatsiya. **Yumshoq signal hech qachon qattiq bloklamaydi.**

## 10. Mijoz ilovalari

**Flutter (bitta ilova, ikki rejim)** — Riverpod v2, go_router (2 ShellRoute), Drift, dio, flutter_secure_storage, **`maplibre_gl`** (+ offline MBTiles-pak — signal yo'q obyektlarda ham xarita ishlaydi), ML Kit, TFLite (MobileFaceNet), i18n: `uz` (lotin) + `ru`, ARB birinchi kundan.
- *Xodim rejimi*: Bosh sahifa (smena, topshiriqlar, sync-chip, Check-in tugma) · Check-in (§9) · Tarixim (ro'yxat + kun-marshrut playback slayder) · Topshiriqlar · Check-in tafsiloti · Bildirishnomalar · Sozlamalar (til, batareya-yordamchi, maxfiylik-tushuntirish).
- *Rahbar rejimi* (server role-claims hal qiladi): jonli xarita (o'z doirasi, klaster, filter: bo'lim-daraxt + xodim multi-select + **obyekt bo'yicha filter**; xodim-nuqtasida obyekt-yorlig'i: "Obyekt №14 da / yo'lda / obyektdan tashqari") · **obyektlar ro'yxati bandlik bilan** ("Obyekt №14 — 3 xodim ichkarida", tap → kim, qachondan beri) · xodimlar ro'yxati (presence + "hozir qaysi obyektda" ustuni) · xodim tafsiloti (obyekt-segmentli timeline, playback) · review-navbat (selfie vs enrollment, ball, xarita — Approve/Reject, audit bilan) · alertlar · topshiriq berish.

**Web admin (React 18 + TS + Vite)** — TanStack Query/Table (virtualizatsiya), Ant Design 5, ECharts, native WS (uzilsa 10 s polling): W1 jonli xarita (MapLibre GL, GeoJSON-klaster, filter-panel: bo'lim + xodim + **obyekt**; obyekt-polygonlarida **bandlik-badge** ("3" — hozir ichkaridagilar soni, hover → ismlar; bo'sh obyektlar xira); xodim-nuqta rangi: obyektda / yo'lda / obyektdan-tashqari / offline) · W2 xodimlar (+ "hozir qaysi obyektda" ustuni, obyekt bo'yicha saralash) · W3 marshrut-playback (**vaqt-slayder play/1–8×**, tracking-bo'shliqlar qizil — bo'shliq ham dalil; timeline obyekt-segmentlari bilan: "Obyekt №14: 09:15–10:40") · W4 review-navbat (klaviatura-tezkor) · W5 obyektlar + geofence-editor (Terra Draw polygon-chizish, CSV/GeoJSON import) · **W5b obyekt-tafsiloti: hozir ichkaridagilar, kun/hafta tashrif-tarixi (kim, qachon, qancha turdi, check-in'lari), rejalashtirilgan topshiriqlar, "bugun hech kim kelmagan obyektlar" ko'rinishi** · W6 bo'limlar/rollar/qurilmalar + xodim bulk-CSV · W7 hisobotlar (tashrif-bajarilish %, obyekt-qamrov: qaysi obyektlarga necha kun tashrif bo'lmagan, offline-nisbat, XLSX/PDF) · W8 audit-ko'ruvchi · smena-jadvali (roster UI).

**Platforma konsoli** (alohida route-space, alohida auth-realm, o'z MFA): tenant ro'yxati/salomatligi (status, plan, xodim-soni vs cap, face-queue kechikish, storage) · plan/limit boshqaruvi · usage&billing dashboard + oylik hisobot-generatsiya · e'lonlar (banner+push, uz/ru) · support-access oqimi · platforma-metrikalar (MAU, check-in/kun, ball-taqsimotlar — model-drift kuzatuvi).

## 11. Xarita: MapLibre GL + OpenStreetMap (bepul)

**Nega Yandex emas (halol izoh)**: Yandex Maps'ning **bepul tarifi litsenziya bo'yicha monitoring/dispetcherlik tizimlarida va yopiq (ommaviy bo'lmagan) ilovalarda ishlatishni taqiqlaydi** — bu tizim ikkala kategoriyaga kiradi; bepul kalit bilan ishlatish ToS-buzilish (kalit bloklanadi, mijoz oldida obro' xavfi). "Bepul Yandex" varianti huquqiy jihatdan mavjud emas; pullik vosita ishlatilmasligi talabidan kelib chiqib asosiy yechim to'liq bepul stack:

- **Web**: MapLibre GL JS (BSD, bepul) — jonli qatlam WS orqali, `setData` ≤1 Hz.
- **Mobil**: `maplibre_gl` Flutter plagini + **offline MBTiles-pak** (signal yo'q obyektlarda ham xarita ishlaydi — Yandex'da bu pullik full-versiyada edi).
- **Tile'lar**: O'zbekiston OSM-extract'idan **Planetiler** bilan vector-tile generatsiya (bir necha yuz MB) → **Martin** tile-server (Docker'da, o'z LB ortida); kvartalda bir yangilash-job. Hech qanday tashqi so'rov yo'q — inspektorlarning viewport'i ham tashqariga chiqmaydi (maxfiylik bonusi).
- **Geokodlash**: self-hosted **Nominatim/Photon** (UZ extract) — hisobotlarda "eng yaqin manzil" uchun, bepul.
- **Qamrov haqiqati**: OSM Toshkent/viloyat markazlarida yaxshi, chekka hududlarda o'rtacha — lekin bu tizim uchun yetarli (nuqta-xaritada + marshrut-playback'da asosiy ehtiyoj yo'l-tarmog'i, u OSM'da bor); kerak bo'lsa tashkilot o'zi OSM'ni to'ldirishi yoki obyekt-qatlamini ustiga chizishi mumkin.
- **Kelajak yo'li**: xarita-qatlam abstraksiyasi (web'da bitta Map-komponent, mobilda bitta MapView-widget) — agar keyinchalik mijoz Yandex-sifatli basemap talab qilsa va **tijorat shartnoma** tuzilsa, almashtirish 1–2 haftalik ish. Arxitektura bunga bog'lanmaydi.

## 12. RBAC va audit

Bitta amalga oshirish nuqtasi: FastAPI dependency ko'rish doirasini hisoblaydi — `org_admin` → o'z org'i to'liq; `hr` → org yoki grant-yo'llar; `dept_head` → o'z subtree + grantlar; `field_employee` → faqat o'zi. Repositorylar `WHERE d.path <@ ANY(:paths)`. Endpoint'larga tarqoq rol-tekshiruv YO'Q. WS-obunalar subscribe'da doiraga tekshiriladi. Org-chegara esa RLS bilan qo'shimcha qulflangan (§4). **Access-log (MVP)**: har lokatsiya/selfie/tarix ko'rish yoziladi — "kuzatuvchilarni kuzatish"; (v2) xodim o'z ma'lumotini kim ko'rganini iloVada ko'radi. Platforma-support kirishlari tenant access-logida `platform_support` tegi bilan ko'rinadi.

## 13. Anti-korrupsiya choralari

**MVP:** imzolangan+server-timestamp check-in (online: nonce; offline: monotonic+ikki-soat) · mock/root/emulator/Play Integrity+App Attest — **risk-ball signallari** (bloklamaydi) · geofence **dwell-talab** · teleport/tezlik tekshiruvi (>150 km/soat) · **tracking-bo'shliq siyosati** (smena payti >15 daq bo'shliq — hodisa, rahbar-timeline'da, oylik integrity-hisobotda: telefonni o'chirish "ko'rinmas" emas "qimmat") · append-only + admin-audit-triggerlar · risk-ball + review-navbat · 1 qurilma/(org,xodim) + almashtirishda HR-tasdiq · enrollment-dedup.

**V2:** **tasodifiy "hozir isbotlang" pinglari** (faol tashrifda yuz+GPS 5 daqiqada — "telefonni haydovchiga qoldirish"ga qarshi eng kuchli chora) · **obyekt-egasiga SMS** ("Inspektor [ism] tashrif qayd etdi. Bo'lmagan bo'lsa 0 javob bering" — qarshi tomon bepul auditor) · hash-zanjirli audit + tashqi kunlik anchor (DBA ham sezdirmasdan o'zgartira olmaydi) · to'rt-ko'z qoidasi (geofence-o'zgartirish, qayta-enrollment, qo'lda-tasdiqlash — 2 tasdiqlovchi) · kech-ochiladigan topshiriqlar + rotatsiya (kelishuv ildiziga qarshi) · retrospektiv tasodifiy audit (2–5%/hafta) · reviewer-javobgarligi (tasdiqlangan bayroqlilarning 5% yuqori daraja qayta ko'radi).

**V3:** anomaliya-skorekard (geofence-chetida check-in, doim-minimal dwell, juftlik-pattern) · kanareyka-obyektlar (yopiq obyektga check-in = qat'iy dalil) · takroriy-yuz sweep (tenant ichida) · foto perceptual-hash (o'tgan-oygi foto fosh) · oylik immutable integrity-hisobot.

**Halol qoldiq xavflar** (mijozga aytiladi): root+virtual-kamera+deepfake nazariy liveness'ni aldashi mumkin (himoya qatlamli: Integrity STRONG + server anti-spoof + tasodifiy ping + jarayon-nazorat); apparat GNSS-spoofing dasturiy to'liq aniqlanmaydi (cell-tower cross-check + harakat-mantiqiyligi qimmatlashtiradi); eng yuqori darajadagi kelishuv texnik doiradan tashqarida (klapan — tashqariga yuboriladigan hash-anchorli oylik hisobot).

## 14. SaaS-mahsulot qatlami

**Umumiylashtirish**: `inspector` → `field_employee`; "obyekt" → `site` (UI-yorlig'i tenant sozlaydi: "Obyekt"/"Filial"/"Punkt"); `site_types` tenant-belgilaydi; `attributes jsonb` custom-fields (jsonb-sxema tenant-sozlamada, formalar sxemadan render, server validatsiya); chegaralar per-tenant (dwell, radius, yuz-chegara — platforma-minimumdan pastga bo'shatib bo'lmaydi, risk-vaznlar, retention 12–24 oy oralig'ida). **Sanoat-shablonlari**: tenant shablondan yaratiladi (site-types + custom-fields + chegaralar + terminologiya + smena-patternlar + hisobot-to'plami). V1 shablonlar: **Qurilish/Nazoratchi** (hozirgi funksional aynan), Dala-servis/Kommunal, Qo'riqlash, Ritel-merchandayzing. Qurilishga xos narsalar shablon ichida yashaydi — yadroda hardcode qolmaydi.

**Tariflar** (o'lchov birligi: **faol xodim/oy** — arxivlanmagan xodim; rahbar/admin-o'rindiqlar bepul):
| | Basic (≤100 xodim) | Pro (≤1000) | Enterprise (cheksiz) |
|---|---|---|---|
| Check-in (yuz+GPS+liveness), jonli xarita, bo'limlar, obyektlar, smenalar | ✔ | ✔ | ✔ |
| Topshiriqlar, playback, review-navbat, risk-ball, hisobotlar, custom-fields | — | ✔ | ✔ |
| Anti-fraud analitika, REST API+webhooks, OneID SSO, audit-eksport, SLA 99.9, dedicated/on-prem | — | — | ✔ |

Feature-flag arxitektura: `plans` jadval (feature-matritsa+limitlar jsonb) → tenant `feature_overrides` → server-side **entitlements-obyekt** Redis-kesh → FastAPI `require_feature()` (hech qachon faqat client-side emas); limitlar yozish-paytida aniq xato-kodlar bilan. Yillik oldindan to'lovga chegirma (UZ B2B normasi).

**Billing (UZ)**: **MVP = qo'lda hisob-faktura** (shartnoma + schet-faktura, bank o'tkazmasi — davlat/yirik mijozlar normi): `subscriptions` + `usage_snapshots` (tungi faol-xodim soni) + `invoices` (platforma-admin status o'zgartiradi). To'lanmasa: grace (banner) → suspend. **2-bosqich: Payme/Click/Uzum** (har biri ~1–2 dev-hafta, provider-adapter interfeys); qo'lda-faktura davlat mijozlar uchun doim qoladi. **Trial**: 14 kun (sales 30 gacha uzaytiradi), 15 xodim + 2 obyekt cap, Pro-funksiyalar, watermark-hisobotlar.

**Onboarding (MVP = sales-led)**: platforma-admin tenant yaratadi (nomi, STIR, shablon, plan) → owner-invite → **birinchi-ishga-tushirish ustaxonasi**: org-profil (shablondan) → bo'limlar → HR-taklif → xodimlar **bulk-CSV** + yuz-enrollment (xodim o'z telefonidan SMS deep-link orqali parallel, HR faqat tasdiqlaydi) → obyektlar (xarita-editor yoki CSV) → smenalar (shablon-patternlar) → go-live checklist (≥1 obyekt, ≥1 smena, ≥1 enrolled, rozilik-qamrov %). **Birinchi-qiymatgacha <1 kun**: hammasi shablondan, CSV-yo'llar, "pilot-rejim" (5 xodim 1 obyekt — o'sha kuni), demo-data toggle. Keyin: self-service signup (shu API ustida yupqa qatlam).

**SLA/support**: Basic — ish-vaqti (Telegram/email), ≤1 ish-kuni; Pro — 99.5%, ≤4 soat, onboarding-sessiya; Enterprise — 99.9%, 24/7 P1-hotline ≤1 soat, kvartallik-review, kredit. Status-sahifa (self-hosted Uptime-Kuma, alohida infra); insident-kommunikatsiya: banner + email/SMS.

## 15. O'zbekiston: qonunchilik (SaaS-restrukturasi bilan)

- **ЗРУ-547** (2026-mart o'zgarishlari): umumiy lokalizatsiya yumshadi, **biometrika uchun mamlakat-ichi saqlash qoldi**. SaaS-cloud **UZ datacenter'da** (UZCLOUD yoki kolokatsiya); DR-sayt ham UZ ichida. Dedicated/on-prem: mijoz o'zi hosting qiladi.
- **Rollar**: har **tenant = operator/controller** (o'z xodimlari ma'lumotining); **platforma = processor** (tenant ko'rsatmasi bo'yicha). Har shartnomaga **DPA-ilova**: ishlov-doirasi, biometrik kategoriyalar, sub-protsessorlar (UZ-DC, Eskiz), xavfsizlik-choralar, breach-notification, tugatishda o'chirish (eksport→purge, embeddinglar+MinIO bilan), audit-huquq.
- **Registratsiya**: **tenant o'z bazasini operator sifatida** ro'yxatdan o'tkazadi (platforma tayyor yo'riqnoma-paket beradi — bu sotuv-argumenti!); **platforma o'z ishlovini alohida** ro'yxatdan o'tkazadi (akkauntlar, billing, protsessor-rol).
- **Rozilik**: per-tenant biometrik rozilik-shablon (uz-lotin/uz-kirill/ru), platforma-tasdiqlangan skelet ichida tahrir; ilovada enrollment'da imzolanadi, shablon-versiya bilan saqlanadi; withdraw → arxiv + biometrika-purge. BYOD'da ayniqsa kritik.
- **Monitoring-nizom**: har tenant uchun ichki nizom/buyruq shabloni: faqat ish-vaqti, retention, kirish-huquqlari.
- **Retention** (default, tenant qonuniy-oraliqda sozlaydi): selfie 12–24 oy (nizo — yopilguncha+1 yil); embedding — ish-davri+6 oy; xom GPS 90 kun + 5-daq agregat 2 yil; audit 5 yil. O'chirish — loglanadigan job.
- **OneID** — Enterprise-tenantlar web-admini uchun v2 (OAuth2; UZINFOCOM-registratsiya qog'ozbozligini MVP'da boshlash); MVP lokal login+TOTP; break-glass lokal admin doim.
- **SMS: Eskiz.uz** (asosiy) + Play Mobile (failover). **Alpha-name 1–2 oy — arizani darhol.**
- **Push: FCM/APNs faqat bo'sh "uyg'on va sinxronla" payload** — ism/koordinata Google/Apple orqali o'tmaydi; har push'ning in-app oynasi bor.
- Davlat axborot-tizimi mijozlar uchun kiberxavfsizlik ekspertizasi/attestatsiyasiga vaqt (dedicated-deploy paketi ichida).

## 16. Deploy va operatsiyalar

- **SaaS-cloud (UZ DC)**: MVP-pilot 3 server (LB+app · DB · infra) → o'sishda 6: nginx-LB 4c/8GB · app-1/2 8c/16GB (api+ws+celery, bittasida beat) · db-primary 16c/64GB/2TB NVMe (PG16+PostGIS+Timescale+pgvector) · db-replica (hisobotlar) · infra 8c/16GB/8TB (MinIO+KES, Redis AOF, monitoring, Martin tile-server + Nominatim).
- **Dedicated/on-prem tier**: aynan shu Compose, `TENANCY_MODE=dedicated` — bitta tenant, platforma-konsol o'chiq. Divergent kod-yo'l nol.
- Docker Compose + deploy-skript (k8s emas); DB HA: streaming-replication + mashq qilingan qo'lda failover.
- **Backup = anti-korrupsiya infratuzilmasi**: pgBackRest (haftalik full, kunlik diff, WAL, 30 kun) + **boshqa binoda offsite** + **tungi per-tenant logical eksport** (bitta tenantni tiklash uchun); oylik restore-mashq; MinIO object-lock + replikatsiya.
- Monitoring: Prometheus+Alertmanager(Telegram)+Grafana; alertlar: ingestion-tushish, face-queue chuqurlik (per-tenant), replication-lag, disk. Yuk: 5000 tracker/tenant ≈ 85 rps + 5/s check-in + 170 msg/s — ikki app-node <20%.

## 17. Yo'l xaritasi (3–6 dev)

**MVP — 20–24 hafta** (bepul GPS-stack +4–6 hafta, tenancy-delta +4–6 hafta), so'ng **2 hafta / birinchi mijozning 1 bo'limi (~200 kishi) pilot**:
`organizations`+org_id+RLS (bitta migratsiya, birinchi kundan!) → auth+RBAC+JWT org-claim → Redis/WS/Celery namespacing → invite-aktivatsiya → provision-CLI → auth/bo'limlar → qurilma-bog'lash → **smena-modeli + roster-UI** → custom background-tracking (alohida egasi!) → batch-ingestion → Timescale+Redis → **obyekt-rezolyutsiya (site-presence: kim qaysi obyektda)** → jonli web-xarita+filtrlar+obyekt-bandlik → check-in (gibrid yuz, offline-navbat, izoh) → Celery/InsightFace + review-navbat → xodim-tarixi → obyektlar CRUD+geofence-editor+CSV → xodim bulk-CSV → append-only audit+access-log → risk-ball v1 → retention-joblar → suspension-gate → metering → onboarding-ustaxona (minimal) → **o'z tile-pipeline (Planetiler→Martin) + mobil offline-pak** → i18n uz/ru → 3-node UZ-DC deploy.
*Parallel qog'ozbozlik (1-hafta)*: platforma ma'lumot-ishlov registratsiyasi, DPA+rozilik-shablonlar, Eskiz alpha-name, OneID-registratsiya, UZ-DC shartnoma.
*Pilot chiqish-mezonlari*: yuz-chegaralar kalibrlangan (ball-taqsimotlar birinchi kundan loglanadi), batareya <8%/kun Xiaomi/Vivo, geofence yolg'on-bayroq maqbul, iOS Always-ruxsat darajasi.

**V2 — 12–14 hafta** (birinchi mijoz org-wide + 2–3 yangi tenant): mobil rahbar-rejimi → to'liq playback-slayder (web+mobil, bitta kontrakt) → topshiriqlar+push → tasodifiy pinglar → hash-zanjir+tashqi anchor → to'rt-ko'z → OneID SSO (Enterprise) → obyekt-egasiga SMS (pilot) → offline trail-korroboratsiya → "meni kim ko'rdi" → hisobotlar+eksport → platforma-konsol to'liq (billing-dashboard, e'lonlar, support-access) → Payme/Click → 6-node.

**V3 — 8–12 hafta**: anomaliya-skorekardlar+oylik integrity-hisobot → rotatsiya/kech-ochish → takroriy-yuz sweep → foto perceptual-hash → kanareyka-obyektlar → **dalil-paket eksporti** (check-in+selfie+track+hash-isbot, imzolangan PDF, keyin e-imzo) → self-service signup → qo'shimcha sanoat-shablonlar → uz-kirill → offboarding-avtomatizatsiya.

## 18. Asosiy xavflar

1. **Cross-tenant leak** — kompaniyani o'ldiradigan xato-klass. Chora: RLS-backstop + TenantTask + bitta kalit-qurish moduli + izolyatsiya-testlar CI'da (§19).
2. **BYOD**: rozilik yuridik nozik (ish-bosimi ostida); **rad etgan xodim uchun yo'l** tenant-nizomida hal qilinishi kerak. OEM-killer flot — "qurilma jimib qoldi" alertlari asosiy to'r.
3. **Bepul GPS-stack** — jadval-xavfi: motion-detection+Doze+OEM murakkab; bitta dev to'liq egalik qilishi shart; batareya-shikoyat dala-sabotajga aylanadi.
4. **Ilova tarqatish**: Google Play `ACCESS_BACKGROUND_LOCATION` siyosat-tekshiruvi (deklaratsiya+video); SaaS uchun store-tarqatish afzal (private emas) — Play Integrity to'liq ishlaydi. iOS — App Store review'da tracking-asoslash.
5. **Yuz-model demografik xatolari**: soqol/ro'mol/qarish → yolg'on rad → norozilik/sabotaj. FNMR-kohort monitoring + shikoyat-yo'li.
6. **Obyekt-reyestr sifati**: koordinata noaniq bo'lsa ommaviy yolg'on-bayroq — geofence-tuzatish workflow (W5); zich shaharda ustma-ust geofence — disambiguatsiya UX.
7. **Jamoa shakli**: Flutter+FastAPI+PostGIS/Timescale+ML+DevOps — yuz-pipeline va tracking alohida egalik talab qiladi.
8. **Huquqiy kuch**: hash-zanjir mehnat-nizolarida dalil sifatida o'tishini yuristlar MVP'da tasdiqlashi kerak.
9. **OSM-qamrov**: chekka hududlarda xarita-detallar kambag'al bo'lishi mumkin — pilot hududida oldindan tekshiriladi; kerak bo'lsa OSM to'ldiriladi (tashkilot o'zi tahrirlashi mumkin) yoki keyinchalik tijorat-shartnoma bilan Yandex qatlami ulanadi (xarita-abstraksiya tayyor). Yandex'ni bepul kalit bilan ishlatish ToS-buzilish — qilinmaydi.
10. **Bitta-mijoz-tuzog'i**: birinchi (davlat) mijoz talablari mahsulotni o'ziga egib yubormasligi uchun qurilishga-xoslik faqat shablon ichida — yadro generik qoladi.

## 19. Tekshirish (verification)

- **Tenant-izolyatsiya testlari (CI-majburiy)**: ikki test-tenant, har endpoint/WS-kanal/Celery-task boshqa tenant ma'lumotini qaytarmasligi avtomatik tekshiriladi; RLS smoke-test (GUC'siz nol qator); pgvector 1:N faqat org-ichi.
- **Har modul**: pytest (testcontainers'da PG+Redis), Flutter widget/integration, API kontrakt-testlar.
- **Yuz-kalibrlash**: 200-kishilik pilot-kohort FMR/FNMR, chegaralar shundan keyin; ball-taqsimot dashboard birinchi kundan.
- **Tracking dala-testi**: 5–10 real past-narx qurilma (Xiaomi/Vivo/Samsung) 1 hafta: batareya, Doze, OEM-killer, "jimib qoldi" alerti.
- **Yuk-test**: k6/locust 5000-qurilma ingestion (85 rps), WS fan-out 100 mijoz, ko'p-tenant fairness (bitta tenant floodi boshqasining face-verdiktini kechiktirmasligi).
- **Anti-fraud qizil-jamoa**: mock-GPS, root, foto/video-replay, soat-orqaga, offline-backdating — har biri risk-ball/review'ga tushishi E2E.
- **End-to-end**: tenant-provision → onboarding-ustaxona → enrollment → aktivatsiya (invite) → smena → geofence-kirish (**site_enter hodisasi + xaritada "Obyekt №14 da" yorlig'i + obyekt-bandlik badge yangilanishi**) → check-in (online/offline) → verdikt → jonli xarita → chiqish (**site_exit + dwell yozuvi**) → playback (obyekt-segmentlar) → review → audit; suspension→read-only; offboarding→eksport+purge (KES-kalit yo'q qilinishi bilan).
- **Geofence-gisterezis testi**: geofence chetida turgan xodim (GPS-drift) enter/exit hodisalarini "chaqnatmasligi" (flapping) sun'iy trek bilan tekshiriladi.

## 20. Birinchi qadamlar (monorepo)

```
employee-control/
├── backend/    FastAPI (api|ws|worker|beat), alembic (org_id+RLS birinchi migratsiyada), pytest
├── mobile/     Flutter (xodim+rahbar rejimlari, invite-aktivatsiya)
├── web/        React+TS+Vite (tenant-admin + /platform konsol route-space)
├── infra/      docker-compose.{dev,prod}.yml, nginx, monitoring, TENANCY_MODE
└── docs/       ushbu reja, API-kontrakt, DPA/rozilik-shablonlar, sanoat-shablonlar
```

1-sprint: repo-skelet + docker-compose dev (PG+Timescale+pgvector, Redis, MinIO) + **organizations+org_id+RLS migratsiya** + auth/RBAC/tenancy modullari + provision-CLI + Flutter-skelet (invite-oqim mock) + CI (lint+test+izolyatsiya-smoke). Parallel: qog'ozbozlik arizalari (§17).

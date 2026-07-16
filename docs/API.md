# API kontrakti (v1)

Barcha endpointlar `/v1` ostida. Auth: `Authorization: Bearer <access_token>` (JWT,
claim'lar: `org_id`, `sub`=user_id, `role`, ixtiyoriy `device_id`).

Rollar: `org_admin`, `hr`, `dept_head`, `field_employee`.
**RBAC-doira** (`visible_user_ids`): `org_admin`/`hr` → butun org; `dept_head` → o'z
bo'limi subtree'si; `field_employee` → faqat o'zi. Tenant-chegara Postgres RLS bilan
majburlangan — token qaysi org'niki bo'lsa, faqat o'sha org ma'lumoti ko'rinadi.

Xato-formati: `{"detail": "<xabar>"}` (FastAPI standarti), status 400/401/403/404/409.

---

## Auth — `/v1/auth`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| POST | `/invites/resolve` | ochiq | `{token}` → `{org_id, org_name, masked_phone}`. Org yuz/OTP'dan OLDIN aniqlanadi. |
| POST | `/otp/request` | ochiq | `{token}` → `{sent, dev_code}`. `dev_code` faqat DEBUG'da qaytadi. |
| POST | `/activate` | ochiq | `{token, otp_code, device:{platform,fingerprint,model?,pubkey?}}` → `{access_token, refresh_token, user:{id,role,org_id,org_name}}`. Qurilma bog'lanadi (1 faol/xodim). |

`GET /v1/me` (auth) → `{id, org_id, role, full_name}`.

---

## Departments — `/v1/departments` (ltree daraxt)

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| GET | `` | auth | Daraxt: `[{id, name, path, parent_id, head_user_id, created_at}]` (path bo'yicha saralangan). |
| POST | `` | org_admin/hr | `{name, parent_id?}` → 201 `DepartmentOut`. parent_id yo'q → org-ildiz ostiga. |
| PATCH | `/{id}` | org_admin/hr | `{name}` → nom o'zgaradi (path barqaror). |
| DELETE | `/{id}` | org_admin/hr | 204. Bo'sh bo'lmasa (ichki bo'lim/xodim) → 409. |

`parent_id` — UUID yoki null (yo'ldan hisoblanadi, create/list/patch izchil).

---

## Users — `/v1/users`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| GET | `` | auth (doira) | `?department_id&status` → `[UserOut]`. |
| POST | `` | org_admin/hr | `{full_name, phone, role?, department_id?, employee_no?}` → 201. Takror telefon → 409 (telefon tenant-ichi unikal). |
| PATCH | `/{id}` | org_admin/hr | `{full_name?, role?, department_id?, employee_no?, status?}`. |
| POST | `/{id}/invite` | org_admin/hr | → `{token, code, user_id}`. Aktivatsiya-taklifi (token bir marta). |
| POST | `/import` | org_admin/hr | multipart `file` (CSV) → `{total, created, errors, rows:[{row,status,detail,user_id?}]}`. Qismli-muvaffaqiyat: har qator mustaqil. |

CSV ustunlari: `full_name, phone, [role], [department_path], [employee_no]`.

`UserOut`: `{id, full_name, phone, role, department_id, employee_no, status, face_enrolled_at, created_at}`.

---

## Sites — `/v1/sites`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| GET | `` | auth | `[SiteOut]`. |
| POST | `` | org_admin/hr | `{name, lat, lon, radius_m=150, min_dwell_minutes=15, address?}` → 201. |
| GET | `/{id}` | auth | `SiteOut` yoki 404. |
| PATCH | `/{id}` | org_admin/hr | `{name?, lat?, lon?, radius_m?, min_dwell_minutes?, address?, status?}`. |
| GET | `/{id}/occupants` | auth | Hozir ichkaridagilar: `[{user_id, full_name, entered_at}]`. |

`SiteOut`: `{id, name, lat, lon, radius_m, min_dwell_minutes, address, status}`.

---

## Tracking — `/v1/locations`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| POST | `/batch` | auth (xodim) | `{points:[{point_uuid, ts, lat, lon, accuracy_m?, speed_mps?, heading?, battery?, is_mock?, provider?}]}` (≤200) → `{accepted, duplicates, current_site_id}`. `point_uuid` bo'yicha idempotent. |
| GET | `/last` | auth (doira) | `{points:[{user_id, ts, lat, lon, accuracy_m, battery, is_mock, site_id}]}`. Redis'dan, xarita-bootstrap. |

### WS `/v1/live?token=<access_token>`
Ulanishda: `{"type":"snapshot","points":[...]}`. Keyin hodisalar (RBAC-doiraga filtrlangan):
- `{"type":"point", user_id, ts, lat, lon, accuracy_m, battery, is_mock, site_id}`
- `{"type":"site_enter", user_id, site_id, ts, dwell_seconds:null}`
- `{"type":"site_exit", user_id, site_id, ts, dwell_seconds}`
- `{"type":"checkin", user_id, checkin_id, site_id, verdict, risk_score, ts}`
- `{"type":"ping"}` (har ~5 s jimlikda — o'lik-soket aniqlash)

Uzilsa: 10 s polling'ga tushish (`GET /v1/locations/last`).

---

## Check-ins — `/v1/checkins`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| POST | `` | auth (xodim) | `CheckinIn` → `CheckinOut`. Idempotent (`checkin_id`). Yaroqsiz imzo → 400. |
| GET | `` | auth (doira) | `?user_id&site_id&verdict&ts_from&ts_to&limit&offset` → `[CheckinOut]`. |
| GET | `/review-queue` | org_admin/hr/dept_head | Bayroqlangan (`flagged`) check-in'lar. |
| GET | `/{id}` | auth (doira) | `CheckinOut` yoki 404. |
| POST | `/{id}/comment` | auth (doira) | `{text}` → izoh append (audit bilan). |
| POST | `/{id}/review` | org_admin/hr/dept_head | `{action:approve\|reject, reason}` → verdict o'zgaradi (audit bilan). |

`CheckinIn`: `{checkin_id, ts, lat, lon, accuracy_m?, site_id?, comment?, face:{local_match?,local_score?,liveness_passed?}, device_integrity?, signature?}`.
`CheckinOut`: `{id, user_id, site_id, ts, lat, lon, inside_geofence, verdict, verdict_reasons:[], risk_score, comment, duplicate}`.

Verdict: `pending|verified|flagged|rejected`. Risk-ball ≥40 → `flagged`; avto-`verified` YO'Q
(server yuz-worker keyin qo'yadi). Imzo yo'q → yumshoq flag; yaroqsiz imzo → hard 400.

---

## Shifts — `/v1/shifts`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| POST | `/v1/shifts` | org_admin/hr | `{shifts:[{user_id, starts_at, ends_at}]}` (≤500) → 201. Noma'lum xodim → 400. |
| GET | `/v1/shifts` | auth (doira) | `?user_id&ts_from&ts_to&limit&offset`. |
| GET | `/v1/me/shift` | auth | `{current, next}` — mobil tracking-gate. |

---

## History — `/v1/employees/{id}`

| Metod | Yo'l | Kim | Tavsif |
|---|---|---|---|
| GET | `/{id}/track` | auth (doira) | `?ts_from&ts_to&stop_min_seconds=300&stop_radius_m=50` → `{user_id, points, stops, gaps, checkins}`. Maksimum 7 kun. Access-logga yoziladi. |
| GET | `/{id}/timeline` | auth (doira) | `?ts_from&ts_to` → `[{site_id, site_name, entered_at, exited_at, dwell_seconds}]`. |

Doirasiz xodim (boshqa tenant yoki ko'rinmas) → 404. Har ko'rish `access_log`'da
("kuzatuvchilarni kuzatish").

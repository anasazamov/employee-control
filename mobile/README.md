# Employee Control — mobil ilova (Flutter)

Bitta ilova, ikki rejim: **dala xodimi** va **rahbar** (qarang: `docs/PLAN.md` §7, §9, §10).
Bu — qo'lda yozilgan skelet: aktivatsiya va check-in oqimlari hozircha **mock**,
platforma-papkalar (`android/`, `ios/`) repoda saqlanmaydi.

## Talablar

- Flutter SDK 3.22+ (Dart 3.4+) — https://docs.flutter.dev/get-started/install
- Android Studio (Android SDK) va/yoki Xcode (iOS uchun)

## Birinchi ishga tushirish

```bash
cd mobile

# 1. Platforma-papkalarni (android/, ios/) generatsiya qilish:
flutter create . --platforms android,ios --project-name employee_control

# 2. Bog'liqliklarni o'rnatish:
flutter pub get

# 3. Lokalizatsiya fayllarini generatsiya qilish (lib/l10n/generated/):
flutter gen-l10n

# 4. Ishga tushirish:
flutter run
```

Eslatmalar:

- `flutter_secure_storage` va ML Kit uchun `android/app/build.gradle`da
  `minSdk 23` qilib qo'ying.
- Lokatsiya/kamera ruxsatlari (AndroidManifest.xml, Info.plist) hali
  qo'shilmagan — background-tracking bosqichida qo'shiladi (PLAN.md §8).

## Kod-generatsiya (kelgusida)

`riverpod_generator` / `drift_dev` bilan `.g.dart` fayllar kerak bo'lganda:

```bash
dart run build_runner build --delete-conflicting-outputs
```

Hozirgi skelet kodgen'siz kompilyatsiya bo'ladi (oddiy `Notifier`/`Provider`).

## Tuzilma

```
lib/
├── main.dart                  # ProviderScope + MaterialApp.router + i18n (uz default, ru)
├── app/
│   └── router.dart            # go_router: /activation + 2 ShellRoute (xodim, rahbar), sessionProvider
├── core/
│   └── api/api_client.dart    # dio + auth-interceptor (flutter_secure_storage token)
├── l10n/
│   ├── app_uz.arb             # default til (lotin)
│   └── app_ru.arb
└── features/
    ├── activation/            # invite-kod -> telefon -> SMS OTP (mock, PLAN.md §7)
    ├── checkin/               # 4 bosqich: Obyekt -> Yuz -> Izoh -> Yuborish (PLAN.md §9)
    ├── home/  history/  tasks/  settings/    # xodim rejimi
    └── manager/               # jonli xarita (MapLibre), xodimlar, obyektlar
```

## Marshrutlar

- `/activation` — shell'lardan tashqarida; sessiya yo'q bo'lsa hamma yo'l shu yerga redirect
- Xodim shell'i: `/home`, `/checkin`, `/history`, `/tasks`, `/settings`
- Rahbar shell'i: `/m/map`, `/m/employees`, `/m/sites`

Rol (`fieldEmployee` / `manager`) hozircha aktivatsiya ekranidagi demo-tumbler
bilan tanlanadi; real ilovada server role-claim'i belgilaydi.

## Keyingi qadamlar (TODO)

- `POST /v1/auth/invite` + `POST /v1/auth/otp` bilan real aktivatsiya
- ML Kit liveness + MobileFaceNet 1:1 (check-in 2-bosqich)
- Drift sxemasi: oflayn GPS bufer va check-in navbati
- Martin tile-server style URL + oflayn MBTiles-pak
- Til tanlash (uz/ru) sozlamalarda saqlanadigan qilib

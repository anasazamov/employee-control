# Web admin

Tenant-admin panel (`/`) va platforma konsoli (`/platform`) frontend'i.

Stack: React 18 + TypeScript + Vite · Ant Design 5 · TanStack Query · React Router 7 · MapLibre GL · i18next (uz/ru) · axios.

## Ishga tushirish

```bash
npm install
cp .env.example .env   # kerak bo'lsa VITE_API_URL ni o'zgartiring
npm run dev            # http://localhost:5173
```

## Buyruqlar

| Buyruq            | Tavsif                                          |
| ----------------- | ----------------------------------------------- |
| `npm run dev`     | Dev-server                                      |
| `npm run build`   | Type-check (`tsc -b`) + production build        |
| `npm run preview` | Build natijasini lokal ko'rish                  |
| `npm run lint`    | Lint (oxlint)                                   |

## Tuzilma

```
src/
├── app/        router, layoutlar (tenant-admin, platforma), sahifa-stublar
├── features/   live-map — MapLibre GL jonli xarita
└── shared/     api (axios + JWT interceptor), i18n (uz/ru)
```

## Eslatmalar

- Xarita hozircha `demotiles.maplibre.org` placeholder-style bilan ishlaydi;
  productionda self-hosted Martin tile-server ulanadi (docs/PLAN.md §11).
- Login sahifasi stub — haqiqiy OTP-auth backend tayyor bo'lganda ulanadi.

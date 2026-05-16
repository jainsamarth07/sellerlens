# SellerLens Frontend

React 18 + Vite + TypeScript + Tailwind + Recharts + Zustand + React Router.

## Quick start

```bash
cd frontend
cp .env.example .env       # adjust VITE_API_BASE_URL if your backend isn't on :8000
npm install
npm run dev                # http://localhost:3000  (proxies /api -> http://localhost:8000)
```

Backend must be running separately:

```bash
cd backend
uvicorn main:app --reload
```

## Routes

| Path         | Page         | Purpose                                                       |
| ------------ | ------------ | ------------------------------------------------------------- |
| `/upload`    | Upload       | 4-step upload flow: drop → process → success (confetti) → error |
| `/dashboard` | Dashboard    | KPIs, waterfall, charts, SKU table, AI insights               |
| `/products`  | Products     | Standalone SKU performance table                              |
| `/chat`      | Chat         | Natural-language Q&A over your settlement data (Azure OpenAI) |
| `/compare`   | Compare      | Multi-period (2–6 files) trend analysis                       |
| `/settings`  | Settings     | Session info + clear stored data                              |

## Upload flow (`/upload`)

1. **Select** — drag-drop or browse; up to 50 MB; auto-detects period from filename (e.g. `April-2026`)
2. **Process** — kicks off `POST /api/upload/start` and polls `GET /api/upload/status/{id}` every 2 s. Each pipeline stage shows spinner → green check:
   - File uploaded securely
   - Reading report structure
   - Parsing N transactions
   - Calculating profit per SKU
   - Generating AI insights
3. **Success** — canvas-confetti burst, "We found ₹X in unclaimed credits", `View Dashboard` CTA
4. **Error** — friendly message, `Download Sample` button, retry CTA

A sample Flipkart workbook is always downloadable from `GET /api/upload/sample` and the link is shown on both the upload form and the error screen.

## State

Zustand with `persist` middleware in `src/store/useAppStore.ts`:

- `periods[]`: every uploaded report (one per period)
- `activePeriodId`: which period the dashboard/chat is currently focused on
- `sessionId`: sticky chat session for follow-up questions

## API client

`src/lib/api.ts` exposes typed helpers wired to backend endpoints:

- `uploadSettlement(file)` → `POST /api/upload/`
- `fetchInsights(payload)` → `POST /api/analytics/insights`
- `chat(question, sessionId, payload)` → `POST /api/chat`
- `fetchSuggestions(uploadId)` / `postSuggestions(sellerData)`
- `uploadMultiPeriod(files[])` → `POST /api/analytics/multi-period`

## Build

```bash
npm run build              # type-check + Vite build -> dist/
npm run preview            # serve the production build locally
```

## Design tokens (Tailwind)

- `navy.900` `#0F172A` — sidebar
- `brand.green` `#059669` — positive / primary actions
- `brand.red` `#DC2626` — losses / warnings
- `brand.amber` `#D97706` — watch / needs attention
- `brand.blue` `#2563EB` — info / links

Font: **DM Sans** (loaded from Google Fonts in `index.html`).

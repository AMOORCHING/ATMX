# EventShield — Weather-Protected Event Ticketing Demo

A simulated event ticketing app that demonstrates the ATMX Risk API end-to-end. Think Dice or Eventbrite, but every outdoor ticket comes with an option for weather protection — priced in real time by the ATMX pricing engine and settled automatically against NOAA weather station data.

## What it demonstrates

| Page | API Endpoints Used | What You See |
|---|---|---|
| **Event Listing** | `GET /v1/risk_price` × 6 | Six outdoor events across US cities, each with a live weather-risk badge |
| **Ticket Purchase** | `GET /v1/risk_price` | Risk probability, confidence interval, premium pricing, settlement rule |
| **Confirmation** | `POST /v1/contracts` | Contract ID, ticker, settlement rule details, NOAA evidence chain |
| **Dashboard** | `GET /v1/contracts/{id}/status` | Active protections, NEXRAD radar overlay, settlement outcomes with hash proof |

## Quick start

### Demo mode (no backend required)

```bash
npm install
npm run dev
# Opens at http://localhost:3002
```

The app ships with deterministic demo data for all six events, so every page works out of the box without the ATMX stack running. The "Demo Mode" badge in the header indicates mock data is in use.

### Connected to the ATMX Risk API

1. Start the full ATMX stack from the repo root:

```bash
docker compose up -d
```

2. Generate an API key (see `services/risk-api/` docs), then create a `.env` file:

```bash
# demos/event-ticketing/.env
VITE_ATMX_API_KEY=atmx_sk_your_key_here
VITE_MAPBOX_TOKEN=pk.your_mapbox_token_here
```

3. Start the dev server:

```bash
npm run dev
```

The app now makes real API calls to the risk-api service on port 8001. The badge switches to "Live API" and all pricing, contracts, and settlement status come from the running stack.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `VITE_ATMX_API_KEY` | No | ATMX API key. If unset, falls back to demo data. |
| `VITE_MAPBOX_TOKEN` | No | Mapbox GL token for the NEXRAD radar map on the dashboard. |

## User flow

1. **Browse events** — Six outdoor music festivals in NYC, Chicago, Houston, Miami, Nashville, and Seattle. Each card shows a real-time weather risk badge.

2. **Select an event** — See the full risk assessment: probability, confidence interval, data source, pricing model. If the rain probability exceeds 10%, the app offers Weather Protection as a ticket add-on.

3. **Purchase with protection** — The app calls `POST /v1/contracts` to create a settlement contract. The premium is set by the ATMX LMSR pricing engine.

4. **Track on dashboard** — View all active protections with a NEXRAD radar overlay showing live precipitation. When a contract settles, see the outcome (YES/NO), observed precipitation value, and the SHA-256 hash-chained evidence record from NOAA ASOS stations.

## Architecture

```
┌──────────────────────┐        ┌──────────────────────┐
│   EventShield Demo   │──────▶│   ATMX Risk API      │
│   (React, Vite)      │  HTTP  │   (FastAPI, :8001)   │
│   :3002              │◀──────│                      │
└──────────────────────┘        └────────┬─────────────┘
                                         │
                        ┌────────────────┼────────────────┐
                        ▼                ▼                ▼
                 ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
                 │  Settlement  │ │   Market    │ │   Forecast   │
                 │   Oracle     │ │   Engine    │ │   Service    │
                 │  (Python)    │ │   (Go)      │ │              │
                 └──────┬──────┘ └─────────────┘ └──────────────┘
                        │
                        ▼
                 ┌─────────────┐
                 │  NOAA ASOS  │
                 │  Stations   │
                 └─────────────┘
```

## Tech stack

- React 19, TypeScript, Vite
- React Router v7 (client-side routing)
- Mapbox GL + react-map-gl (NEXRAD radar overlay)
- h3-js (venue → H3 cell conversion)
- Pure CSS (no framework)

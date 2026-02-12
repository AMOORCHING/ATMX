# atmx — Design Document

## Overview

**atmx** is a weather derivative trading platform that combines real-time NOAA weather data with prediction market mechanics. Users trade binary contracts on weather outcomes (e.g., "Will precipitation in this area exceed 25mm in the next 24 hours?"), and contracts are settled automatically against official ASOS/AWOS observations.

This document explains *why* the system is built the way it is — the tradeoffs behind each technical decision — not just what it does.

## Architecture

```
                    ┌──────────────┐
                    │   Frontend   │
                    │ React+Mapbox │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
     ┌────────────────┐      ┌──────────────────┐
     │  Market Engine  │      │ Settlement Oracle │
     │   (Go / LMSR)  │      │  (Python / NOAA)  │
     └───────┬────────┘      └────────┬──────────┘
             │     ┌───────┐          │
             ├─────│ Redis │          │
             │     └───────┘          │
             └──────────┬─────────────┘
                        ▼
                ┌───────────────┐
                │  PostgreSQL   │
                │   + PostGIS   │
                └───────────────┘
```

## Services

### Market Engine (Go)

**Purpose:** Automated market maker for binary weather derivative contracts.

- **LMSR (Logarithmic Market Scoring Rule):** Provides continuous pricing with bounded market maker loss. Liquidity parameter `b` controls price sensitivity.
- **Trades:** Accepts buy/sell orders for YES/NO shares. Each trade adjusts the cost function and updates prices.
- **Positions:** Tracks per-trader holdings and P&L.
- **API:** RESTful endpoints for market creation, trading, price queries, and position lookups.
- **Metrics:** Prometheus `/metrics` endpoint exposes trades/sec, latency percentiles, active markets, WebSocket clients.

Key design decisions:
- In-memory market state for low-latency trading (persistent to DB on write-behind)
- Path-independent cost function ensures fair pricing regardless of order arrival
- Maximum market maker loss bounded at `b * ln(2)` per market

### Settlement Oracle (Python)

**Purpose:** Ingest official weather data and resolve contracts.

- **NOAA ingestion:** HRRR GRIB2 forecast files from AWS S3, parsed with cfgrib/xarray.
- **H3 spatial indexing:** Grid points mapped to H3 hexagonal cells (resolution 7, ~5 km²).
- **ASOS/AWOS observations:** Official sensor readings fetched from IEM for settlement.
- **Resolution logic:** Aggregates station readings, detects conflicts, determines YES/NO/DISPUTED outcome.
- **Audit trail:** Immutable, hash-chained settlement records for tamper detection.

Settlement outcomes:
| Outcome | Meaning |
|---------|---------|
| YES | Observed value exceeded the contract threshold |
| NO | Observed value did not exceed the threshold |
| DISPUTED | Conflicting data, sensor outage, or insufficient stations |

### API Gateway (optional)

Thin routing layer for unified auth, rate limiting, and CORS when deploying to production. Not required for development.

## Data Flow

```
1. Contract Creation
   User → Frontend → Market Engine (create market)
                   → Settlement Oracle (register contract spec)

2. Trading
   User → Frontend → Market Engine (buy/sell shares)
                                    LMSR adjusts prices

3. Settlement (at contract expiry)
   Cron/Trigger → Settlement Oracle
                  → Fetch ASOS observations for H3 cell
                  → Aggregate readings, compare to threshold
                  → Write hash-chained settlement record
                  → Notify Market Engine of outcome
                  → Market Engine resolves positions & payouts
```

---

## Why LMSR Over CPMM or a Full Order Book

This is the single most important design decision in the system. Three options were evaluated:

### Option 1: Full Continuous-Double-Auction Order Book
Traditional exchanges (CME, Kalshi) use a limit order book (LOB). Pros: familiar, price discovery is organic, zero liquidity subsidy. Cons: **cold-start problem** — a new weather market on a single H3 cell may see only a handful of traders per day. With thin order books, spreads blow out to 30–40¢ on a $1 contract, making the market unusable. You need an active market-making desk to seed liquidity, which requires capital and a risk engine.

### Option 2: Constant Product Market Maker (CPMM, e.g., Uniswap-style)
CPMM (`x * y = k`) is the DeFi default. Pros: simple, well-understood. Cons: **price slippage scales with trade size / pool depth**, which means small traders pay disproportionate execution costs. More critically, CPMM provides no bounded-loss guarantee — LPs face impermanent loss that is hard to hedge when one side of a binary contract goes to 0 or 1 (which happens in every settled weather market).

### Option 3: LMSR (Hanson's Logarithmic Market Scoring Rule) ✓
LMSR was designed specifically for prediction markets. The key properties that make it right for atmx:

1. **Bounded market maker loss:** Maximum loss is `b × ln(2)` for a binary market. This means we can boot-strap a market with exactly zero external liquidity providers — the platform absorbs a known, bounded loss per market. For `b = 100`, max loss is $69.31 per market.

2. **Path-independent pricing:** The cost of going from state A to state B is the same regardless of the intermediate trades. This eliminates front-running incentives and simplifies the audit trail.

3. **Continuous liquidity at any depth:** Every trade, no matter how large, has a defined cost. There is no spread. This matters for weather markets where a farmer may want to buy 500 shares of coverage at 3 AM with no other participants online.

4. **Price sensitivity scales with `b`:** We derive `b` from NWS ensemble forecast uncertainty (IQR/median), so markets in high-uncertainty regimes naturally have deeper liquidity, and markets where the outcome is near-certain are cheaper to move.

**The tradeoff:** LMSR markets are subsidy-funded. The platform loses up to `b × ln(2)` per market. At `b = 100` with 1,000 active markets, worst-case subsidy is ~$69K. This is acceptable for a demo; in production you'd offset this with a per-trade fee (even 1–2% covers the subsidy at moderate volume).

### Migration Path to Hybrid Order Book

As liquidity grows, pure LMSR becomes suboptimal — informed traders prefer to set their own prices. The migration plan:

1. **Phase 1 (current):** Pure LMSR. Platform is sole market maker. Good for 0–100 daily active traders.
2. **Phase 2:** LMSR + limit orders. Accept resting limit orders that execute when the LMSR price crosses them. The LMSR acts as a guaranteed backstop, while limit orders provide tighter spreads when available. Implementation: add a `resting_orders` table and check pending orders before/after each LMSR trade.
3. **Phase 3:** Full hybrid. LMSR provides a quoted spread; any limit order inside the LMSR spread takes priority. LMSR `b` parameter auto-decays as organic order flow increases. When the order book is deep enough, LMSR contribution approaches zero.

This is the same path Kalshi and Polymarket followed (Polymarket started with an AMM, migrated to a CLOB as volume grew).

---

## Why H3 Resolution 7

H3 resolution 7 gives hexagons of ~5.16 km² (edge length ~1.22 km). This was not arbitrary — it's the Goldilocks zone for weather derivatives.

### What breaks at resolution 6 (~36 km²)

- **Too coarse for localized weather events.** A single res-6 hex covers an area larger than Manhattan. Convective precipitation events (thunderstorms) regularly produce >25mm in one neighborhood while the next neighborhood 3 km away gets nothing. A res-6 market would aggregate too many stations and smooth out the very signal farmers need to hedge against.
- **Station density is fine**, but the contract loses its value proposition: "Will it rain heavily *here*" becomes "Will it rain heavily *somewhere in this 36 km² area*", which is almost always YES during storm season.

### What breaks at resolution 8 (~0.74 km²)

- **Station coverage gaps.** ASOS/AWOS stations are spaced 10–40 km apart in most of the US. A res-8 hex is ~860m across, meaning most hexes have **zero** stations inside them. Settlement would return DISPUTED for >90% of contracts, making the market useless.
- **Market fragmentation.** Splitting the same geographic area into 7× more markets means 7× less liquidity per market and 7× more LMSR subsidy cost.
- **HRRR forecast grid resolution is ~3 km.** At res-8, multiple hexes map to the same single HRRR grid point, so the forecast doesn't even differentiate between neighboring cells.

### Why resolution 7 is right

- ~5 km² matches the effective resolution of HRRR (3 km grid → ~9 km² influence area).
- Most res-7 hexes in metro areas contain 1–3 ASOS/AWOS stations — enough for settlement, sparse enough to still represent localized conditions.
- Farmer/municipal hedging radius is typically 3–10 km, which maps to 1–3 adjacent res-7 hexes — a natural basket size for the hedging tool.
- The correlation limiter uses H3 prefix-5 (~1,200 km²) to group nearby cells, which at res-7 captures the spatial extent of a typical tropical storm or frontal system.

---

## CFTC Event Contract Framework Awareness

Weather derivatives have specific regulatory treatment in the US:

### Current Status
- **Commodity Futures:** Traditional weather derivatives (CME Heating/Cooling Degree Day contracts) are regulated as commodity futures under CEA §1a(19).
- **Event Contracts:** Binary contracts that pay $1-or-$0 on an event outcome can be classified as "event contracts" under CEA §5c(c)(5)(C). The CFTC has authority to approve or deny event contracts on designated contract markets (DCMs).
- **Kalshi Precedent:** Kalshi operates as a CFTC-registered DCM and has successfully listed event contracts on weather events (hurricane landfall, temperature thresholds). Their 2023 approval of hurricane contracts is directly relevant to atmx.

### atmx Regulatory Positioning
- atmx contracts are structurally identical to Kalshi's approved weather event contracts: binary outcomes, settlement against publicly available government data (NOAA), with deterministic resolution criteria.
- The hash-chained settlement audit trail is designed with CFTC rule 17 CFR § 38.1051 in mind (core principle 20: record-keeping and reporting). Every settlement record includes the raw ASOS observations, aggregation methodology, and a cryptographic chain of custody.
- **What we'd need for a DCM application:** A compliance module for position reporting (CFTC Large Trader Reporting), trade practice surveillance (wash trading detection), and financial resource requirements. The current position limiter is a first step but would need extension for regulatory reporting.

### Differences from Traditional Weather Derivatives
- CME weather futures use Degree Day indices (aggregate metrics). atmx uses point-in-time, location-specific thresholds — more granular but also more susceptible to settlement disputes (hence the DISPUTED outcome).
- The H3 spatial model is novel. In a regulatory filing, we'd need to demonstrate that the settlement mechanism is "reasonably certain to be ascertainable" per CFTC standards. The minimum-station requirement and conflict detection threshold (20% spread-to-mean) are designed to ensure this.

---

## Dispute Handling

Settlement can result in DISPUTED when:
1. No ASOS/AWOS stations exist in the H3 cell
2. All station readings are missing (sensor outage)
3. Station readings conflict (>20% spread-to-mean ratio)
4. Fewer valid stations than the configured minimum

Disputed contracts hold funds in escrow until manual resolution or re-settlement with additional data sources.

---

## Security & Audit

- Settlement records are **hash-chained** (SHA-256): each record's hash includes the previous record's hash
- Tampering with any record breaks the chain for all subsequent records
- Full evidence payloads (raw observations, aggregation details) stored with each settlement
- All trades logged with timestamps, trader IDs, and execution prices

---

## Observability

- **Prometheus metrics** exposed at `/metrics` on the market engine: `atmx_trades_total`, `atmx_trade_latency_seconds`, `atmx_active_markets`, `atmx_websocket_clients`, `atmx_http_requests_total`, `atmx_position_limit_rejections_total`.
- **Grafana dashboard** ("Orders/sec vs Active NWS Alerts") auto-provisioned in docker compose.
- Key SLIs: trade p99 latency < 100ms, WebSocket broadcast latency < 50ms, settlement hash-chain integrity (verified on every append).

---

## What I'd Do with 6 More Months

### Months 1–2: Production Hardening
- **Distributed trade execution:** Replace the in-process mutex with a PostgreSQL advisory lock or Redis-based distributed lock. Enables horizontal scaling of market-engine replicas behind a load balancer.
- **Event-driven settlement:** Replace the manual `/settle` endpoint with a cron-triggered pipeline that watches contract expiry times and auto-settles. Add retry logic with exponential backoff for ASOS API failures.
- **Proper auth & identity:** JWT-based auth with API keys for institutional traders. RBAC for admin operations (market creation, manual settlement override).

### Months 2–3: Hybrid Order Book
- Implement the Phase 2 hybrid model (LMSR backstop + resting limit orders).
- Add a matching engine with price-time priority for limit orders.
- Market data feed: L2 order book snapshots over WebSocket.
- Auto-decay `b` parameter based on trailing 24h organic volume.

### Months 3–4: Data Pipeline Robustness
- **Multi-source settlement:** Add MADIS, ASOS ONE-MINUTE data, and private weather stations as fallback data sources. Weighted consensus across sources reduces DISPUTED rate.
- **Forecast-derived priors:** Use HRRR ensemble spread to set initial LMSR prices away from 50/50 when meteorological data clearly favors one outcome. This reduces the subsidy cost.
- **Historical backtesting infrastructure:** Automated nightly backtest of settlement logic against the last 5 years of ASOS data. Track accuracy and dispute rate trends.

### Months 4–5: Regulatory & Compliance
- Position reporting pipeline for CFTC Large Trader Reporting.
- Trade surveillance: wash trading detection, spoofing detection (less relevant for LMSR but required for hybrid order book).
- Financial resource calculation module (net capital requirements for DCM application).
- Formal settlement methodology whitepaper for regulatory review.

### Month 6: Scale & Distribution
- **Geographic expansion:** ECMWF data for European markets, JMA for Pacific Rim.
- **New contract types:** Temperature thresholds, snow accumulation, tropical storm intensity (Saffir-Simpson), wildfire smoke (AQI).
- **API for institutional integration:** FIX protocol adapter for HFT firms; REST/WebSocket API for fintech embeddings.
- **Mobile app:** React Native shell around the existing frontend with push notifications for settlement events and position alerts.

# atmx — Design Document

## Overview

**atmx** is a weather derivative trading platform that combines real-time NOAA weather data with prediction market mechanics. Users trade binary contracts on weather outcomes (e.g., "Will precipitation in this area exceed 25mm in the next 24 hours?"), and contracts are settled automatically against official ASOS/AWOS observations.

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
             │                        │
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

## Spatial Model

We use **Uber's H3 hexagonal grid** at resolution 7:
- Hexagon area: ~5.16 km²
- Edge length: ~1.22 km
- Appropriate for mesoscale weather phenomena

Each weather contract specifies an H3 cell. Observations from ASOS/AWOS stations within that cell are used for settlement.

## Market Mechanics

The **LMSR** automated market maker provides:
- **Continuous liquidity:** Always a price available, no order book needed
- **Bounded loss:** Market maker's maximum loss is `b × ln(n)` where n = number of outcomes
- **Information aggregation:** Prices naturally converge to reflect collective beliefs about weather outcomes

For binary markets (YES/NO):
```
Price(YES) = exp(q_yes / b) / (exp(q_yes / b) + exp(q_no / b))
Cost(trade) = C(q_after) - C(q_before)
where C(q) = b × ln(exp(q_yes/b) + exp(q_no/b))
```

## Dispute Handling

Settlement can result in DISPUTED when:
1. No ASOS/AWOS stations exist in the H3 cell
2. All station readings are missing (sensor outage)
3. Station readings conflict (>20% spread-to-mean ratio)
4. Fewer valid stations than the configured minimum

Disputed contracts hold funds in escrow until manual resolution or re-settlement with additional data sources.

## Security & Audit

- Settlement records are **hash-chained** (SHA-256): each record's hash includes the previous record's hash
- Tampering with any record breaks the chain for all subsequent records
- Full evidence payloads (raw observations, aggregation details) stored with each settlement
- All trades logged with timestamps, trader IDs, and execution prices

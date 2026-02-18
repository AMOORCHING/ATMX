# atmx

Weather derivative trading platform. Trade binary contracts on weather outcomes, settled automatically against official NOAA observations.

![atmx screenshot](docs/screenshot.png)
<!-- TODO: Replace with actual screenshot after first full demo run -->

## Architecture

```
atmx/
├── docker-compose.yml          # Full stack: DB, Redis, services, monitoring
├── .env.example                # Environment variables template
├── .github/workflows/ci.yml   # CI: lint, test, build on every push
├── docs/
│   └── design.md              # Design rationale (LMSR, H3, CFTC, roadmap)
├── monitoring/                 # Prometheus + Grafana config
├── services/
│   ├── market-engine/          # Go — LMSR automated market maker
│   ├── settlement-oracle/      # Python — NOAA ingestion, contract resolution
│   └── api-gateway/            # Optional routing layer
├── frontend/                   # React + Mapbox
├── scripts/                    # Seeding, ingestion, backtesting
└── tests/
    └── integration/            # End-to-end: contract → market → trade → settle
```

## Services

| Service | Language | Port | Description |
|---------|----------|------|-------------|
| **market-engine** | Go | 8080 | LMSR market maker — creates markets, executes trades, tracks positions, Prometheus metrics |
| **settlement-oracle** | Python | 8000 | NOAA data ingestion, ASOS observations, contract settlement with hash-chained audit trail |
| **frontend** | React/TS | 3000 | Mapbox-powered UI for browsing markets, trading, and hedging |
| **redis** | Redis 7 | 6379 | Read-through cache for market engine |
| **prometheus** | Prometheus | 9090 | Metrics collection |
| **grafana** | Grafana | 3001 | Dashboard: Orders/sec vs Active Markets |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Go 1.22+, Python 3.11+, Node 20+ for local development

### Setup

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env and add your MAPBOX_TOKEN

# 2. Start everything
docker compose up -d

# 3. Seed sample contracts and markets
pip install httpx h3
python scripts/seed_contracts.py
```

| URL | Service |
|-----|---------|
| http://localhost:3000 | Frontend |
| http://localhost:8080/health | Market Engine |
| http://localhost:8080/metrics | Prometheus Metrics |
| http://localhost:8000/docs | Settlement Oracle (Swagger) |
| http://localhost:9090 | Prometheus |
| http://localhost:3001 | Grafana (admin/admin) |

### Local Development

**Market Engine (Go):**
```bash
cd services/market-engine
go run ./cmd/server
# Listening on :8080
```

**Settlement Oracle (Python):**
```bash
cd services/settlement-oracle
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db    # Start PostgreSQL
alembic upgrade head
uvicorn app.main:app --reload
# Listening on :8000
```

**Frontend (React):**
```bash
cd frontend
npm install
npm run dev
# Listening on :3000
```

## Trading Flow

1. **Browse** weather cells on the Mapbox map
2. **Select** an H3 cell to see available markets
3. **Trade** YES/NO shares — LMSR adjusts prices automatically
4. **Hedge** — enter an address to get a suggested basket of contracts
5. **Settlement** happens at contract expiry against official ASOS/AWOS observations

## Data Pipeline

```bash
# Ingest HRRR forecast data
python scripts/ingest_forecast.py --date 2025-08-14 --hour 0 --forecast-hour 1

# Seed sample contracts + markets
python scripts/seed_contracts.py

# Run historical backtesting (30 events against real NOAA data)
python scripts/backtest_settlement.py

# Generate case studies (10 retroactive events with real ASOS data)
python scripts/generate_case_studies.py
```

## Testing

```bash
# Settlement Oracle unit tests
cd services/settlement-oracle
pytest -v

# Market Engine unit tests
cd services/market-engine
go test ./...

# Integration tests (requires services running)
pytest tests/integration/ -v -m integration

# Historical backtesting (no services needed, fetches from IEM)
python scripts/backtest_settlement.py
```

## CI/CD

Every push to `main` and every pull request triggers GitHub Actions:
- **market-engine**: golangci-lint, `go test -race`, build
- **settlement-oracle**: ruff lint, pytest
- **frontend**: ESLint, `tsc --noEmit`, Vite build
- **docker**: `docker compose build`
- **integration**: full E2E test suite

## Documentation

- [Design Document](docs/design.md) — Why LMSR over CPMM, why H3 resolution 7, CFTC awareness, hybrid order book migration path, and 6-month roadmap
- [Case Studies](docs/case_studies.md) — 10 retroactive walkthroughs using real NOAA ASOS data from actual outdoor events (concerts, festivals, fireworks)

# atmx

is a Weather derivative trading platform. Trade binary contracts on weather outcomes, settled automatically against official NOAA observations.

## Architecture

```
atmx/
├── docker-compose.yml
├── README.md
├── docs/
│   └── design.md
├── services/
│   ├── market-engine/          # Go — LMSR automated market maker, trades, positions
│   ├── settlement-oracle/      # Python — NOAA ingestion, contract resolution
│   └── api-gateway/            # Optional routing layer
├── frontend/                   # React + Mapbox
├── scripts/                    # Data seeding, forecast ingestion
└── tests/
    └── integration/            # End-to-end: ingest → trade → settle
```

## Services

| Service | Language | Port | Description |
|---------|----------|------|-------------|
| **market-engine** | Go | 8080 | LMSR market maker — creates markets, executes trades, tracks positions |
| **settlement-oracle** | Python | 8000 | NOAA data ingestion, ASOS observations, contract settlement with hash-chained audit trail |
| **frontend** | React/TS | 3000 | Mapbox-powered UI for browsing markets and trading |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Go 1.22+, Python 3.11+, Node 20+ for local development

### Run Everything

```bash
docker compose up -d
```

| URL | Service |
|-----|---------|
| http://localhost:3000 | Frontend |
| http://localhost:8080/health | Market Engine |
| http://localhost:8000/docs | Settlement Oracle (Swagger) |

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
4. **Settlement** happens at contract expiry against official ASOS/AWOS observations

## Data Pipeline

```bash
# Ingest HRRR forecast data
python scripts/ingest_forecast.py --date 2025-08-14 --hour 0 --forecast-hour 1

# Seed sample contracts
python scripts/seed_contracts.py
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
```

## Documentation

- [Design Document](docs/design.md) — Architecture, LMSR mechanics, data flow, settlement logic

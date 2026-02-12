-- Market Engine schema: PostgreSQL with NUMERIC for exact decimal precision.

CREATE TABLE IF NOT EXISTS markets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id TEXT NOT NULL UNIQUE,
    h3_cell_id  TEXT NOT NULL,
    q_yes       NUMERIC NOT NULL DEFAULT 0,
    q_no        NUMERIC NOT NULL DEFAULT 0,
    b           NUMERIC NOT NULL,
    price_yes   NUMERIC NOT NULL DEFAULT 0.5,
    price_no    NUMERIC NOT NULL DEFAULT 0.5,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'settled')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_markets_contract ON markets(contract_id);
CREATE INDEX IF NOT EXISTS idx_markets_h3cell   ON markets(h3_cell_id);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    market_id   UUID NOT NULL REFERENCES markets(id),
    contract_id TEXT NOT NULL,
    side        TEXT NOT NULL CHECK (side IN ('YES', 'NO')),
    quantity    NUMERIC NOT NULL,
    price       NUMERIC NOT NULL,
    cost        NUMERIC NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ledger is append-only: revoke UPDATE and DELETE at the role level.
-- REVOKE UPDATE, DELETE ON ledger_entries FROM market_engine_app;

CREATE INDEX IF NOT EXISTS idx_ledger_user        ON ledger_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_ledger_market       ON ledger_entries(market_id);
CREATE INDEX IF NOT EXISTS idx_ledger_user_market   ON ledger_entries(user_id, market_id);
CREATE INDEX IF NOT EXISTS idx_ledger_timestamp     ON ledger_entries(timestamp);

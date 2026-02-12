// Package model defines the core domain types shared across the market engine.
// All monetary values use shopspring/decimal — never float64 for money.
package model

import (
	"time"

	"github.com/shopspring/decimal"
)

// LedgerEntry is an immutable record of a trade execution.
// Once created, these are never modified or deleted.
// Schema: {user, contract, side, quantity, price, timestamp}
type LedgerEntry struct {
	ID         string          `json:"id" db:"id"`
	UserID     string          `json:"user_id" db:"user_id"`
	MarketID   string          `json:"market_id" db:"market_id"`
	ContractID string          `json:"contract_id" db:"contract_id"`
	Side       string          `json:"side" db:"side"`         // "YES" or "NO"
	Quantity   decimal.Decimal `json:"quantity" db:"quantity"`  // signed: +buy, -sell
	Price      decimal.Decimal `json:"price" db:"price"`       // average fill price
	Cost       decimal.Decimal `json:"cost" db:"cost"`         // total cost (signed)
	Timestamp  time.Time       `json:"timestamp" db:"timestamp"`
}

// Market represents the state of a binary prediction market tied to one
// weather contract on one H3 cell.
type Market struct {
	ID         string          `json:"id" db:"id"`
	ContractID string          `json:"contract_id" db:"contract_id"`
	H3CellID   string          `json:"h3_cell_id" db:"h3_cell_id"`
	QYes       decimal.Decimal `json:"q_yes" db:"q_yes"`
	QNo        decimal.Decimal `json:"q_no" db:"q_no"`
	B          decimal.Decimal `json:"b" db:"b"` // LMSR liquidity parameter
	PriceYes   decimal.Decimal `json:"price_yes" db:"price_yes"`
	PriceNo    decimal.Decimal `json:"price_no" db:"price_no"`
	Status     string          `json:"status" db:"status"` // "open", "settled"
	CreatedAt  time.Time       `json:"created_at" db:"created_at"`
}

// Position represents a trader's aggregate holdings in one market.
type Position struct {
	UserID        string          `json:"user_id"`
	MarketID      string          `json:"market_id"`
	ContractID    string          `json:"contract_id"`
	H3CellID      string          `json:"h3_cell_id"`
	YesQty        decimal.Decimal `json:"yes_qty"`
	NoQty         decimal.Decimal `json:"no_qty"`
	NetQty        decimal.Decimal `json:"net_qty"`          // yes - no
	CostBasis     decimal.Decimal `json:"cost_basis"`       // net cash outflow
	CurrentValue  decimal.Decimal `json:"current_value"`    // mark-to-market
	UnrealizedPnL decimal.Decimal `json:"unrealized_pnl"`   // currentValue - costBasis
}

// Portfolio aggregates all positions for a user with P&L and risk metrics.
type Portfolio struct {
	UserID            string                     `json:"user_id"`
	Positions         []Position                 `json:"positions"`
	TotalPnL          decimal.Decimal            `json:"total_pnl"`
	TotalExposure     decimal.Decimal            `json:"total_exposure"`     // Σ |netQty|
	MarginUtilization decimal.Decimal            `json:"margin_utilization"` // % of margin used
	ExposureByCell    map[string]decimal.Decimal `json:"exposure_by_cell"`   // h3CellID → net
}

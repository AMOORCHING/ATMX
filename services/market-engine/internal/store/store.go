// Package store defines the persistence interface for the market engine.
// Implementations include PostgreSQL (source of truth), Redis (read-through
// cache), and in-memory (for testing).
package store

import (
	"context"

	"github.com/atmx/market-engine/internal/model"
	"github.com/shopspring/decimal"
)

// Store is the persistence interface. PostgreSQL is the source of truth;
// Redis provides a read-through cache layer.
type Store interface {
	// --- Market operations ---

	// CreateMarket persists a new market.
	CreateMarket(ctx context.Context, market *model.Market) error

	// GetMarket retrieves a market by its ID.
	GetMarket(ctx context.Context, id string) (*model.Market, error)

	// GetMarketByContract retrieves a market by its contract ticker.
	GetMarketByContract(ctx context.Context, contractID string) (*model.Market, error)

	// ListMarkets returns all markets.
	ListMarkets(ctx context.Context) ([]model.Market, error)

	// UpdateMarketState updates quantities and prices after a trade.
	UpdateMarketState(ctx context.Context, id string, qYes, qNo, priceYes, priceNo decimal.Decimal) error

	// --- Immutable ledger ---

	// InsertLedgerEntry appends an immutable trade record.
	InsertLedgerEntry(ctx context.Context, entry *model.LedgerEntry) error

	// GetLedgerEntriesByMarket returns all trades for a market.
	GetLedgerEntriesByMarket(ctx context.Context, marketID string) ([]model.LedgerEntry, error)

	// GetLedgerEntriesByUser returns all trades for a user.
	GetLedgerEntriesByUser(ctx context.Context, userID string) ([]model.LedgerEntry, error)

	// --- Position queries ---

	// GetUserPositions computes aggregate positions from the ledger.
	GetUserPositions(ctx context.Context, userID string) ([]model.Position, error)

	// GetUserCellExposures returns net directional exposure per H3 cell.
	GetUserCellExposures(ctx context.Context, userID string) (map[string]decimal.Decimal, error)
}

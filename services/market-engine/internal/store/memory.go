package store

import (
	"context"
	"fmt"
	"sync"

	"github.com/atmx/market-engine/internal/model"
	"github.com/shopspring/decimal"
)

// MemoryStore implements Store with in-memory maps. Used for testing
// and development. Not suitable for production (no persistence).
type MemoryStore struct {
	mu      sync.RWMutex
	markets map[string]*model.Market
	ledger  []model.LedgerEntry
}

// NewMemoryStore creates a new in-memory store.
func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		markets: make(map[string]*model.Market),
	}
}

func (s *MemoryStore) CreateMarket(_ context.Context, m *model.Market) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	for _, existing := range s.markets {
		if existing.ContractID == m.ContractID {
			return fmt.Errorf("market for contract %s already exists", m.ContractID)
		}
	}

	// Store a copy to avoid external mutation.
	copy := *m
	s.markets[m.ID] = &copy
	return nil
}

func (s *MemoryStore) GetMarket(_ context.Context, id string) (*model.Market, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	m, ok := s.markets[id]
	if !ok {
		return nil, fmt.Errorf("market %s not found", id)
	}
	copy := *m
	return &copy, nil
}

func (s *MemoryStore) GetMarketByContract(_ context.Context, contractID string) (*model.Market, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, m := range s.markets {
		if m.ContractID == contractID {
			copy := *m
			return &copy, nil
		}
	}
	return nil, fmt.Errorf("market for contract %s not found", contractID)
}

func (s *MemoryStore) ListMarkets(_ context.Context) ([]model.Market, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	markets := make([]model.Market, 0, len(s.markets))
	for _, m := range s.markets {
		markets = append(markets, *m)
	}
	return markets, nil
}

func (s *MemoryStore) UpdateMarketState(_ context.Context, id string, qYes, qNo, priceYes, priceNo decimal.Decimal) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	m, ok := s.markets[id]
	if !ok {
		return fmt.Errorf("market %s not found", id)
	}
	m.QYes = qYes
	m.QNo = qNo
	m.PriceYes = priceYes
	m.PriceNo = priceNo
	return nil
}

func (s *MemoryStore) InsertLedgerEntry(_ context.Context, entry *model.LedgerEntry) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.ledger = append(s.ledger, *entry)
	return nil
}

func (s *MemoryStore) GetLedgerEntriesByMarket(_ context.Context, marketID string) ([]model.LedgerEntry, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var result []model.LedgerEntry
	for _, e := range s.ledger {
		if e.MarketID == marketID {
			result = append(result, e)
		}
	}
	return result, nil
}

func (s *MemoryStore) GetLedgerEntriesByUser(_ context.Context, userID string) ([]model.LedgerEntry, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var result []model.LedgerEntry
	for _, e := range s.ledger {
		if e.UserID == userID {
			result = append(result, e)
		}
	}
	return result, nil
}

// GetUserPositions aggregates ledger entries into positions per market.
// Computes current value and unrealized P&L using live market prices.
func (s *MemoryStore) GetUserPositions(_ context.Context, userID string) ([]model.Position, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	type posAgg struct {
		marketID   string
		contractID string
		yesQty     decimal.Decimal
		noQty      decimal.Decimal
		costBasis  decimal.Decimal
	}

	agg := make(map[string]*posAgg)

	// Aggregate from ledger (single lock, no re-entrant calls).
	for _, e := range s.ledger {
		if e.UserID != userID {
			continue
		}
		pa, ok := agg[e.MarketID]
		if !ok {
			pa = &posAgg{
				marketID:   e.MarketID,
				contractID: e.ContractID,
			}
			agg[e.MarketID] = pa
		}
		if e.Side == "YES" {
			pa.yesQty = pa.yesQty.Add(e.Quantity)
		} else {
			pa.noQty = pa.noQty.Add(e.Quantity)
		}
		pa.costBasis = pa.costBasis.Add(e.Cost)
	}

	one := decimal.NewFromInt(1)
	var positions []model.Position

	for _, pa := range agg {
		m := s.markets[pa.marketID] // direct access, already under RLock
		priceYes := decimal.NewFromFloat(0.5)
		h3Cell := ""
		if m != nil {
			priceYes = m.PriceYes
			h3Cell = m.H3CellID
		}
		priceNo := one.Sub(priceYes)

		netQty := pa.yesQty.Sub(pa.noQty)
		// Mark-to-market: expected value = priceYes * yesQty + priceNo * noQty
		currentValue := priceYes.Mul(pa.yesQty).Add(priceNo.Mul(pa.noQty))
		pnl := currentValue.Sub(pa.costBasis)

		positions = append(positions, model.Position{
			UserID:        userID,
			MarketID:      pa.marketID,
			ContractID:    pa.contractID,
			H3CellID:      h3Cell,
			YesQty:        pa.yesQty,
			NoQty:         pa.noQty,
			NetQty:        netQty,
			CostBasis:     pa.costBasis,
			CurrentValue:  currentValue,
			UnrealizedPnL: pnl,
		})
	}

	return positions, nil
}

// GetUserCellExposures returns net directional exposure per H3 cell.
func (s *MemoryStore) GetUserCellExposures(ctx context.Context, userID string) (map[string]decimal.Decimal, error) {
	positions, err := s.GetUserPositions(ctx, userID)
	if err != nil {
		return nil, err
	}

	exposures := make(map[string]decimal.Decimal)
	for _, p := range positions {
		if p.H3CellID != "" {
			exposures[p.H3CellID] = exposures[p.H3CellID].Add(p.NetQty)
		}
	}
	return exposures, nil
}

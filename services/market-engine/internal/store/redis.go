package store

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/shopspring/decimal"

	"github.com/atmx/market-engine/internal/model"
)

// CachedStore wraps a primary Store (PostgreSQL) with a Redis read-through
// cache. Writes go to the primary store and invalidate the cache; reads
// check Redis first then fall back to the primary.
type CachedStore struct {
	primary Store
	rdb     *redis.Client
	ttl     time.Duration
}

// NewCachedStore creates a cached wrapper around a primary store.
func NewCachedStore(primary Store, rdb *redis.Client, ttl time.Duration) *CachedStore {
	return &CachedStore{
		primary: primary,
		rdb:     rdb,
		ttl:     ttl,
	}
}

// --- Write-through (write to primary, invalidate cache) ---

func (s *CachedStore) CreateMarket(ctx context.Context, m *model.Market) error {
	if err := s.primary.CreateMarket(ctx, m); err != nil {
		return err
	}
	s.cacheMarket(ctx, m)
	return nil
}

func (s *CachedStore) UpdateMarketState(ctx context.Context, id string, qYes, qNo, priceYes, priceNo decimal.Decimal) error {
	if err := s.primary.UpdateMarketState(ctx, id, qYes, qNo, priceYes, priceNo); err != nil {
		return err
	}
	// Invalidate cache; next read will re-populate.
	s.rdb.Del(ctx, marketKey(id))
	return nil
}

func (s *CachedStore) InsertLedgerEntry(ctx context.Context, entry *model.LedgerEntry) error {
	if err := s.primary.InsertLedgerEntry(ctx, entry); err != nil {
		return err
	}
	// Invalidate position cache for this user.
	s.rdb.Del(ctx, positionsKey(entry.UserID))
	return nil
}

// --- Read-through (check cache first) ---

func (s *CachedStore) GetMarket(ctx context.Context, id string) (*model.Market, error) {
	// Try cache.
	data, err := s.rdb.Get(ctx, marketKey(id)).Bytes()
	if err == nil {
		var m model.Market
		if json.Unmarshal(data, &m) == nil {
			return &m, nil
		}
	}

	// Cache miss: read from primary.
	m, err := s.primary.GetMarket(ctx, id)
	if err != nil {
		return nil, err
	}

	s.cacheMarket(ctx, m)
	return m, nil
}

func (s *CachedStore) GetMarketByContract(ctx context.Context, contractID string) (*model.Market, error) {
	// Try cache via contract→marketID mapping.
	marketID, err := s.rdb.Get(ctx, contractKey(contractID)).Result()
	if err == nil {
		return s.GetMarket(ctx, marketID)
	}

	// Cache miss.
	m, err := s.primary.GetMarketByContract(ctx, contractID)
	if err != nil {
		return nil, err
	}

	// Cache both the market and the contract→ID mapping.
	s.cacheMarket(ctx, m)
	s.rdb.Set(ctx, contractKey(contractID), m.ID, s.ttl)
	return m, nil
}

func (s *CachedStore) GetUserPositions(ctx context.Context, userID string) ([]model.Position, error) {
	// Try cache.
	data, err := s.rdb.Get(ctx, positionsKey(userID)).Bytes()
	if err == nil {
		var positions []model.Position
		if json.Unmarshal(data, &positions) == nil {
			return positions, nil
		}
	}

	// Cache miss.
	positions, err := s.primary.GetUserPositions(ctx, userID)
	if err != nil {
		return nil, err
	}

	if data, err := json.Marshal(positions); err == nil {
		s.rdb.Set(ctx, positionsKey(userID), data, s.ttl)
	}
	return positions, nil
}

// --- Passthrough (not cached) ---

func (s *CachedStore) ListMarkets(ctx context.Context) ([]model.Market, error) {
	return s.primary.ListMarkets(ctx)
}

func (s *CachedStore) GetLedgerEntriesByMarket(ctx context.Context, marketID string) ([]model.LedgerEntry, error) {
	return s.primary.GetLedgerEntriesByMarket(ctx, marketID)
}

func (s *CachedStore) GetLedgerEntriesByUser(ctx context.Context, userID string) ([]model.LedgerEntry, error) {
	return s.primary.GetLedgerEntriesByUser(ctx, userID)
}

func (s *CachedStore) GetUserCellExposures(ctx context.Context, userID string) (map[string]decimal.Decimal, error) {
	return s.primary.GetUserCellExposures(ctx, userID)
}

// --- Cache helpers ---

func (s *CachedStore) cacheMarket(ctx context.Context, m *model.Market) {
	if data, err := json.Marshal(m); err == nil {
		s.rdb.Set(ctx, marketKey(m.ID), data, s.ttl)
	}
}

func marketKey(id string) string      { return fmt.Sprintf("market:%s", id) }
func contractKey(id string) string    { return fmt.Sprintf("contract:%s", id) }
func positionsKey(uid string) string  { return fmt.Sprintf("positions:%s", uid) }

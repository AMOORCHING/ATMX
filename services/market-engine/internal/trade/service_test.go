package trade_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/shopspring/decimal"

	"github.com/atmx/market-engine/internal/correlation"
	"github.com/atmx/market-engine/internal/model"
	"github.com/atmx/market-engine/internal/store"
	"github.com/atmx/market-engine/internal/trade"
)

func d(f float64) decimal.Decimal {
	return decimal.NewFromFloat(f)
}

// newTestEnv creates a test Service with in-memory store and chi router.
func newTestEnv(t *testing.T) (*trade.Service, *store.MemoryStore, chi.Router) {
	t.Helper()
	ms := store.NewMemoryStore()
	limiter := correlation.NewPositionLimiter(d(1000), d(5000), 5)
	svc := trade.NewService(ms, limiter, nil)

	r := chi.NewRouter()
	r.Post("/api/v1/markets", svc.CreateMarket)
	r.Get("/api/v1/markets/{marketID}", svc.GetMarket)
	r.Get("/api/v1/markets/{marketID}/price", svc.GetPrice)
	r.Post("/api/v1/trade", svc.ExecuteTrade)
	r.Get("/api/v1/portfolio/{userID}", svc.GetPortfolio)

	return svc, ms, r
}

// seedMarket creates a test market directly in the store.
func seedMarket(t *testing.T, ms *store.MemoryStore, contractID, h3Cell string, b float64) *model.Market {
	t.Helper()
	market := &model.Market{
		ID:         "test-market-" + contractID,
		ContractID: contractID,
		H3CellID:   h3Cell,
		QYes:       decimal.Zero,
		QNo:        decimal.Zero,
		B:          d(b),
		PriceYes:   d(0.5),
		PriceNo:    d(0.5),
		Status:     "open",
		CreatedAt:  time.Now().UTC(),
	}
	if err := ms.CreateMarket(context.Background(), market); err != nil {
		t.Fatalf("failed to seed market: %v", err)
	}
	return market
}

func doTrade(t *testing.T, router chi.Router, req trade.TradeRequest) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(req)
	httpReq := httptest.NewRequest("POST", "/api/v1/trade", bytes.NewReader(body))
	httpReq.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, httpReq)
	return w
}

// --- Trade execution tests ---

func TestExecuteTrade_BuyYes(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(10),
	})

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp trade.TradeResponse
	json.Unmarshal(w.Body.Bytes(), &resp)

	if resp.TradeID == "" {
		t.Error("expected non-empty trade_id")
	}
	if resp.FillPrice.LessThanOrEqual(decimal.Zero) {
		t.Errorf("fill price should be positive, got %s", resp.FillPrice)
	}
	if resp.Cost.LessThanOrEqual(decimal.Zero) {
		t.Errorf("cost should be positive for buy, got %s", resp.Cost)
	}
	// Fill price should be close to 0.5 for small trade at origin.
	if resp.FillPrice.Sub(d(0.5)).Abs().GreaterThan(d(0.05)) {
		t.Errorf("fill price should be ≈ 0.5, got %s", resp.FillPrice)
	}
	if resp.Position.YesQty.IsZero() {
		t.Error("position should show YES quantity")
	}
}

func TestExecuteTrade_BuyNo(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "NO",
		Quantity:   d(10),
	})

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp trade.TradeResponse
	json.Unmarshal(w.Body.Bytes(), &resp)

	if resp.Cost.LessThanOrEqual(decimal.Zero) {
		t.Errorf("cost should be positive for NO buy, got %s", resp.Cost)
	}
	if resp.Position.NoQty.IsZero() {
		t.Error("position should show NO quantity")
	}
}

func TestExecuteTrade_PriceMovesCorrectly(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	// First trade.
	doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(50),
	})

	// Check that market price increased.
	market, _ := ms.GetMarketByContract(context.Background(), "ATMX-872a1070b-PRECIP-25MM-20250815")
	if market.PriceYes.LessThanOrEqual(d(0.5)) {
		t.Errorf("YES price should be > 0.5 after YES buy, got %s", market.PriceYes)
	}
	one := decimal.NewFromInt(1)
	sum := market.PriceYes.Add(market.PriceNo)
	if sum.Sub(one).Abs().GreaterThan(d(0.0000001)) {
		t.Errorf("prices should sum to 1, got %s", sum)
	}
}

func TestExecuteTrade_InvalidSide(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "MAYBE",
		Quantity:   d(10),
	})

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for invalid side, got %d", w.Code)
	}
}

func TestExecuteTrade_ZeroQuantity(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   decimal.Zero,
	})

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for zero quantity, got %d", w.Code)
	}
}

func TestExecuteTrade_MarketNotFound(t *testing.T) {
	_, _, router := newTestEnv(t)

	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-000000000-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(10),
	})

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

func TestExecuteTrade_PriceBoundExceeded(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	// Massive buy should push price beyond MaxPrice.
	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(100000),
	})

	if w.Code != http.StatusConflict {
		t.Errorf("expected 409 for price bound exceeded, got %d: %s", w.Code, w.Body.String())
	}
}

func TestExecuteTrade_PerCellLimitExceeded(t *testing.T) {
	_, ms, router := newTestEnv(t)
	// Use high b (10000) so price barely moves, allowing us to hit the
	// per-cell position limit (1000) before the price bound (0.999).
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 10000)

	// Buy up to near the per-cell limit (1000) in increments.
	for i := 0; i < 9; i++ {
		w := doTrade(t, router, trade.TradeRequest{
			UserID:     "user1",
			ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
			Side:       "YES",
			Quantity:   d(100),
		})
		if w.Code != http.StatusOK {
			t.Fatalf("trade %d failed: %d %s", i, w.Code, w.Body.String())
		}
	}

	// This should push exposure to 1000, which is exactly at the limit — allowed.
	w := doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(100),
	})
	if w.Code != http.StatusOK {
		t.Fatalf("trade at limit should succeed: %d %s", w.Code, w.Body.String())
	}

	// Now one more should exceed.
	w = doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(1),
	})
	if w.Code != http.StatusConflict {
		t.Errorf("expected 409 for per-cell limit, got %d: %s", w.Code, w.Body.String())
	}
}

func TestExecuteTrade_LedgerEntryCreated(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(10),
	})

	entries, err := ms.GetLedgerEntriesByUser(context.Background(), "user1")
	if err != nil {
		t.Fatalf("failed to get ledger: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 ledger entry, got %d", len(entries))
	}

	e := entries[0]
	if e.UserID != "user1" {
		t.Errorf("expected user_id=user1, got %s", e.UserID)
	}
	if e.Side != "YES" {
		t.Errorf("expected side=YES, got %s", e.Side)
	}
	if !e.Quantity.Equal(d(10)) {
		t.Errorf("expected quantity=10, got %s", e.Quantity)
	}
	if e.Timestamp.IsZero() {
		t.Error("expected non-zero timestamp")
	}
}

func TestExecuteTrade_PathIndependence(t *testing.T) {
	// Sequential trades should cost the same as a single bulk trade.
	_, ms1, router1 := newTestEnv(t)
	seedMarket(t, ms1, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	_, ms2, router2 := newTestEnv(t)
	seedMarket(t, ms2, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	// Path 1: buy 10, then buy 5.
	w1a := doTrade(t, router1, trade.TradeRequest{
		UserID: "user1", ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side: "YES", Quantity: d(10),
	})
	w1b := doTrade(t, router1, trade.TradeRequest{
		UserID: "user1", ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side: "YES", Quantity: d(5),
	})

	// Path 2: buy 15 at once.
	w2 := doTrade(t, router2, trade.TradeRequest{
		UserID: "user1", ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side: "YES", Quantity: d(15),
	})

	var resp1a, resp1b, resp2 trade.TradeResponse
	json.Unmarshal(w1a.Body.Bytes(), &resp1a)
	json.Unmarshal(w1b.Body.Bytes(), &resp1b)
	json.Unmarshal(w2.Body.Bytes(), &resp2)

	sequentialCost := resp1a.Cost.Add(resp1b.Cost)
	directCost := resp2.Cost

	tolerance := d(0.0000001)
	if sequentialCost.Sub(directCost).Abs().GreaterThan(tolerance) {
		t.Errorf("path independence violated: sequential=%s direct=%s",
			sequentialCost, directCost)
	}
}

// --- Portfolio tests ---

func TestGetPortfolio_WithPositions(t *testing.T) {
	_, ms, router := newTestEnv(t)
	seedMarket(t, ms, "ATMX-872a1070b-PRECIP-25MM-20250815", "872a1070b", 100)

	// Execute a trade.
	doTrade(t, router, trade.TradeRequest{
		UserID:     "user1",
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		Side:       "YES",
		Quantity:   d(10),
	})

	// Get portfolio.
	req := httptest.NewRequest("GET", "/api/v1/portfolio/user1", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var portfolio model.Portfolio
	json.Unmarshal(w.Body.Bytes(), &portfolio)

	if portfolio.UserID != "user1" {
		t.Errorf("expected user_id=user1, got %s", portfolio.UserID)
	}
	if len(portfolio.Positions) != 1 {
		t.Fatalf("expected 1 position, got %d", len(portfolio.Positions))
	}
	if portfolio.ExposureByCell == nil {
		t.Error("expected exposure_by_cell to be set")
	}
	if _, ok := portfolio.ExposureByCell["872a1070b"]; !ok {
		t.Error("expected exposure for cell 872a1070b")
	}
}

func TestGetPortfolio_Empty(t *testing.T) {
	_, _, router := newTestEnv(t)

	req := httptest.NewRequest("GET", "/api/v1/portfolio/nobody", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var portfolio model.Portfolio
	json.Unmarshal(w.Body.Bytes(), &portfolio)

	if len(portfolio.Positions) != 0 {
		t.Errorf("expected 0 positions, got %d", len(portfolio.Positions))
	}
}

// --- Market creation via API ---

func TestCreateMarket_Valid(t *testing.T) {
	_, _, router := newTestEnv(t)

	body, _ := json.Marshal(trade.CreateMarketRequest{
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		B:          d(150),
	})

	req := httptest.NewRequest("POST", "/api/v1/markets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var market model.Market
	json.Unmarshal(w.Body.Bytes(), &market)

	if market.ContractID != "ATMX-872a1070b-PRECIP-25MM-20250815" {
		t.Errorf("unexpected contract_id: %s", market.ContractID)
	}
	if market.H3CellID != "872a1070b" {
		t.Errorf("expected h3_cell_id=872a1070b, got %s", market.H3CellID)
	}
	if !market.B.Equal(d(150)) {
		t.Errorf("expected b=150, got %s", market.B)
	}
}

func TestCreateMarket_InvalidTicker(t *testing.T) {
	_, _, router := newTestEnv(t)

	body, _ := json.Marshal(trade.CreateMarketRequest{
		ContractID: "INVALID-TICKER",
	})

	req := httptest.NewRequest("POST", "/api/v1/markets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400 for invalid ticker, got %d", w.Code)
	}
}

func TestCreateMarket_DefaultB(t *testing.T) {
	_, _, router := newTestEnv(t)

	body, _ := json.Marshal(trade.CreateMarketRequest{
		ContractID: "ATMX-872a1070b-PRECIP-25MM-20250815",
		// B not specified → default 100
	})

	req := httptest.NewRequest("POST", "/api/v1/markets", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var market model.Market
	json.Unmarshal(w.Body.Bytes(), &market)

	if !market.B.Equal(d(100)) {
		t.Errorf("expected default b=100, got %s", market.B)
	}
}

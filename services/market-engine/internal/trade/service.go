// Package trade provides the HTTP handlers and business logic for
// creating markets, executing trades, and querying positions/portfolios.
//
// All monetary values use shopspring/decimal — never float64 for money.
package trade

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	"github.com/shopspring/decimal"

	"github.com/atmx/market-engine/internal/contract"
	"github.com/atmx/market-engine/internal/correlation"
	"github.com/atmx/market-engine/internal/lmsr"
	"github.com/atmx/market-engine/internal/model"
	"github.com/atmx/market-engine/internal/store"
)

// Service handles market operations. Uses a mutex for serialized trade
// execution (single-instance). For horizontal scaling, replace with
// distributed locking or database-level optimistic concurrency.
type Service struct {
	store       store.Store
	limiter     *correlation.PositionLimiter
	marginLimit decimal.Decimal
	mu          sync.Mutex
	wsHub       *WSHub // optional WebSocket hub for real-time broadcasts
}

// NewService creates a new trade service.
// Pass nil for hub if WebSocket broadcasting is not needed.
func NewService(st store.Store, limiter *correlation.PositionLimiter, hub *WSHub) *Service {
	return &Service{
		store:       st,
		limiter:     limiter,
		marginLimit: decimal.NewFromInt(10000), // default margin limit
		wsHub:       hub,
	}
}

// --- Request/Response types ---

// CreateMarketRequest is the JSON body for market creation.
type CreateMarketRequest struct {
	ContractID string          `json:"contract_id"` // ATMX-{h3}-{type}-{threshold}-{date}
	B          decimal.Decimal `json:"b"`           // liquidity parameter; 0 → default 100
}

// TradeRequest is the JSON body for POST /trade.
type TradeRequest struct {
	UserID     string          `json:"user_id"`
	ContractID string          `json:"contract_id"` // ticker symbol
	Side       string          `json:"side"`         // "YES" or "NO"
	Quantity   decimal.Decimal `json:"quantity"`      // positive = buy, negative = sell
}

// TradeResponse is the JSON body returned from POST /trade.
type TradeResponse struct {
	TradeID    string          `json:"trade_id"`
	UserID     string          `json:"user_id"`
	ContractID string          `json:"contract_id"`
	Side       string          `json:"side"`
	Quantity   decimal.Decimal `json:"quantity"`
	FillPrice  decimal.Decimal `json:"fill_price"`
	Cost       decimal.Decimal `json:"cost"`
	Position   PositionSummary `json:"position"`
}

// PositionSummary is the position snapshot included in trade responses.
type PositionSummary struct {
	YesQty        decimal.Decimal `json:"yes_qty"`
	NoQty         decimal.Decimal `json:"no_qty"`
	CostBasis     decimal.Decimal `json:"cost_basis"`
	UnrealizedPnL decimal.Decimal `json:"unrealized_pnl"`
}

// --- HTTP Handlers ---

// CreateMarket handles POST /api/v1/markets
func (s *Service) CreateMarket(w http.ResponseWriter, r *http.Request) {
	var req CreateMarketRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	// Validate ticker format.
	parsed, err := contract.ParseTicker(req.ContractID)
	if err != nil {
		writeError(w, err.Error(), http.StatusBadRequest)
		return
	}

	b := req.B
	if b.LessThanOrEqual(decimal.Zero) {
		b = decimal.NewFromInt(100) // default liquidity
	}

	// Validate b can construct a market maker.
	if _, err := lmsr.NewMarketMaker(b); err != nil {
		writeError(w, err.Error(), http.StatusBadRequest)
		return
	}

	half := decimal.NewFromFloat(0.5)
	market := &model.Market{
		ID:         uuid.New().String(),
		ContractID: req.ContractID,
		H3CellID:   parsed.H3CellID,
		QYes:       decimal.Zero,
		QNo:        decimal.Zero,
		B:          b,
		PriceYes:   half,
		PriceNo:    half,
		Status:     "open",
		CreatedAt:  time.Now().UTC(),
	}

	ctx := r.Context()
	if err := s.store.CreateMarket(ctx, market); err != nil {
		writeError(w, err.Error(), http.StatusConflict)
		return
	}

	slog.Info("market created",
		"id", market.ID,
		"contract", req.ContractID,
		"h3_cell", parsed.H3CellID,
		"b", b.String(),
	)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(market)
}

// GetMarket handles GET /api/v1/markets/{marketID}
func (s *Service) GetMarket(w http.ResponseWriter, r *http.Request) {
	marketID := chi.URLParam(r, "marketID")

	market, err := s.store.GetMarket(r.Context(), marketID)
	if err != nil {
		writeError(w, "market not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(market)
}

// GetPrice handles GET /api/v1/markets/{marketID}/price
func (s *Service) GetPrice(w http.ResponseWriter, r *http.Request) {
	marketID := chi.URLParam(r, "marketID")

	market, err := s.store.GetMarket(r.Context(), marketID)
	if err != nil {
		writeError(w, "market not found", http.StatusNotFound)
		return
	}

	resp := map[string]decimal.Decimal{
		"yes": market.PriceYes,
		"no":  market.PriceNo,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// ExecuteTrade handles POST /api/v1/trade
// Executes against LMSR, returns fill price and updated position.
func (s *Service) ExecuteTrade(w http.ResponseWriter, r *http.Request) {
	var req TradeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	// --- Input validation ---
	if req.UserID == "" {
		writeError(w, "user_id is required", http.StatusBadRequest)
		return
	}
	if req.Side != "YES" && req.Side != "NO" {
		writeError(w, "side must be YES or NO", http.StatusBadRequest)
		return
	}
	if req.Quantity.IsZero() {
		writeError(w, "quantity must be non-zero", http.StatusBadRequest)
		return
	}

	ctx := r.Context()

	// Serialize trade execution.
	s.mu.Lock()
	defer s.mu.Unlock()

	// Find market by contract ticker.
	market, err := s.store.GetMarketByContract(ctx, req.ContractID)
	if err != nil {
		writeError(w, "market not found for contract: "+req.ContractID, http.StatusNotFound)
		return
	}

	if market.Status != "open" {
		writeError(w, "market is not open for trading", http.StatusConflict)
		return
	}

	// Create LMSR market maker for this market's b parameter.
	mm, err := lmsr.NewMarketMaker(market.B)
	if err != nil {
		writeError(w, "internal error: invalid market configuration", http.StatusInternalServerError)
		return
	}

	// --- Position limit check ---
	// Compute exposure delta: YES increases exposure, NO decreases it.
	exposureDelta := req.Quantity
	if req.Side == "NO" {
		exposureDelta = req.Quantity.Neg()
	}

	exposures, err := s.store.GetUserCellExposures(ctx, req.UserID)
	if err != nil {
		writeError(w, "failed to check position limits", http.StatusInternalServerError)
		return
	}

	if err := s.limiter.CheckLimit(market.H3CellID, exposureDelta, exposures); err != nil {
		writeError(w, err.Error(), http.StatusConflict)
		return
	}

	// --- Price bounds validation + cost computation ---
	var cost, fillPrice decimal.Decimal
	var newQYes, newQNo decimal.Decimal

	if req.Side == "YES" {
		if err := mm.ValidateTrade(market.QYes, market.QNo, req.Quantity); err != nil {
			writeError(w, err.Error(), http.StatusConflict)
			return
		}
		cost = mm.TradeCost(market.QYes, market.QNo, req.Quantity)
		fillPrice = mm.FillPrice(market.QYes, market.QNo, req.Quantity)
		newQYes = market.QYes.Add(req.Quantity)
		newQNo = market.QNo
	} else {
		if err := mm.ValidateTradeNo(market.QYes, market.QNo, req.Quantity); err != nil {
			writeError(w, err.Error(), http.StatusConflict)
			return
		}
		cost = mm.TradeCostNo(market.QYes, market.QNo, req.Quantity)
		fillPrice = mm.FillPrice(market.QNo, market.QYes, req.Quantity) // swap for NO
		newQYes = market.QYes
		newQNo = market.QNo.Add(req.Quantity)
	}

	// Update market state.
	newPriceYes := mm.Price(newQYes, newQNo)
	newPriceNo := mm.PriceNo(newQYes, newQNo)

	if err := s.store.UpdateMarketState(ctx, market.ID, newQYes, newQNo, newPriceYes, newPriceNo); err != nil {
		writeError(w, "failed to update market state", http.StatusInternalServerError)
		return
	}

	// Create immutable ledger entry.
	entry := &model.LedgerEntry{
		ID:         uuid.New().String(),
		UserID:     req.UserID,
		MarketID:   market.ID,
		ContractID: req.ContractID,
		Side:       req.Side,
		Quantity:   req.Quantity,
		Price:      fillPrice,
		Cost:       cost,
		Timestamp:  time.Now().UTC(),
	}

	if err := s.store.InsertLedgerEntry(ctx, entry); err != nil {
		writeError(w, "failed to record trade", http.StatusInternalServerError)
		return
	}

	// Get updated position for response.
	positions, _ := s.store.GetUserPositions(ctx, req.UserID)
	var posSummary PositionSummary
	for _, p := range positions {
		if p.MarketID == market.ID {
			posSummary = PositionSummary{
				YesQty:        p.YesQty,
				NoQty:         p.NoQty,
				CostBasis:     p.CostBasis,
				UnrealizedPnL: p.UnrealizedPnL,
			}
			break
		}
	}

	resp := TradeResponse{
		TradeID:    entry.ID,
		UserID:     req.UserID,
		ContractID: req.ContractID,
		Side:       req.Side,
		Quantity:   req.Quantity,
		FillPrice:  fillPrice,
		Cost:       cost,
		Position:   posSummary,
	}

	slog.Info("trade executed",
		"trade_id", entry.ID,
		"user", req.UserID,
		"contract", req.ContractID,
		"side", req.Side,
		"qty", req.Quantity.String(),
		"cost", cost.String(),
		"fill_price", fillPrice.String(),
		"new_price_yes", newPriceYes.String(),
	)

	// Broadcast price update via WebSocket.
	if s.wsHub != nil {
		s.wsHub.Broadcast(WSMessage{
			Type:       "trade_executed",
			MarketID:   market.ID,
			ContractID: req.ContractID,
			H3CellID:   market.H3CellID,
			PriceYes:   newPriceYes.String(),
			PriceNo:    newPriceNo.String(),
			Side:       req.Side,
			Quantity:   req.Quantity.String(),
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// ListMarkets handles GET /api/v1/markets
// Returns all markets, optionally filtered by ?h3_cell=<cellID>.
func (s *Service) ListMarkets(w http.ResponseWriter, r *http.Request) {
	markets, err := s.store.ListMarkets(r.Context())
	if err != nil {
		writeError(w, "failed to list markets", http.StatusInternalServerError)
		return
	}
	if markets == nil {
		markets = []model.Market{}
	}

	// Optional filter by h3_cell query parameter.
	if cell := r.URL.Query().Get("h3_cell"); cell != "" {
		var filtered []model.Market
		for _, m := range markets {
			if m.H3CellID == cell {
				filtered = append(filtered, m)
			}
		}
		if filtered == nil {
			filtered = []model.Market{}
		}
		markets = filtered
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(markets)
}

// GetMarketHistory handles GET /api/v1/markets/{marketID}/history
// Returns ledger entries to reconstruct price history.
func (s *Service) GetMarketHistory(w http.ResponseWriter, r *http.Request) {
	marketID := chi.URLParam(r, "marketID")

	entries, err := s.store.GetLedgerEntriesByMarket(r.Context(), marketID)
	if err != nil {
		writeError(w, "failed to get market history", http.StatusInternalServerError)
		return
	}
	if entries == nil {
		entries = []model.LedgerEntry{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(entries)
}

// GetPortfolio handles GET /api/v1/portfolio/{userID}
// Returns P&L, exposure per cell, and margin utilization.
func (s *Service) GetPortfolio(w http.ResponseWriter, r *http.Request) {
	userID := chi.URLParam(r, "userID")
	ctx := r.Context()

	positions, err := s.store.GetUserPositions(ctx, userID)
	if err != nil {
		writeError(w, "failed to load positions", http.StatusInternalServerError)
		return
	}

	totalPnL := decimal.Zero
	totalExposure := decimal.Zero
	totalMargin := decimal.Zero
	exposureByCell := make(map[string]decimal.Decimal)

	for _, p := range positions {
		totalPnL = totalPnL.Add(p.UnrealizedPnL)
		totalExposure = totalExposure.Add(p.NetQty.Abs())

		if p.H3CellID != "" {
			exposureByCell[p.H3CellID] = exposureByCell[p.H3CellID].Add(p.NetQty)
		}

		// Margin = maximum potential loss per position.
		// For binary contracts: max loss = max(costBasis - yesQty, costBasis - noQty)
		lossIfYes := p.CostBasis.Sub(p.YesQty)
		lossIfNo := p.CostBasis.Sub(p.NoQty)
		maxLoss := lossIfYes
		if lossIfNo.GreaterThan(maxLoss) {
			maxLoss = lossIfNo
		}
		if maxLoss.IsPositive() {
			totalMargin = totalMargin.Add(maxLoss)
		}
	}

	marginUtilization := decimal.Zero
	if s.marginLimit.IsPositive() {
		marginUtilization = totalMargin.Div(s.marginLimit).Mul(decimal.NewFromInt(100)).Round(2)
	}

	portfolio := model.Portfolio{
		UserID:            userID,
		Positions:         positions,
		TotalPnL:          totalPnL,
		TotalExposure:     totalExposure,
		MarginUtilization: marginUtilization,
		ExposureByCell:    exposureByCell,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(portfolio)
}

// writeError writes a JSON error response.
func writeError(w http.ResponseWriter, message string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}

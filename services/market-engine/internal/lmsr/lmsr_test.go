package lmsr

import (
	"math"
	"testing"

	"github.com/shopspring/decimal"
)

// d is a test helper for creating decimals from float64.
func d(f float64) decimal.Decimal {
	return decimal.NewFromFloat(f)
}

// --- Constructor tests ---

func TestNewMarketMaker_Valid(t *testing.T) {
	mm, err := NewMarketMaker(d(100))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !mm.B().Equal(d(100)) {
		t.Errorf("expected b=100, got %s", mm.B())
	}
}

func TestNewMarketMaker_ZeroB(t *testing.T) {
	_, err := NewMarketMaker(d(0))
	if err != ErrInvalidLiquidity {
		t.Errorf("expected ErrInvalidLiquidity for b=0, got %v", err)
	}
}

func TestNewMarketMaker_NegativeB(t *testing.T) {
	_, err := NewMarketMaker(d(-50))
	if err != ErrInvalidLiquidity {
		t.Errorf("expected ErrInvalidLiquidity for b=-50, got %v", err)
	}
}

// --- Price function tests ---

func TestPrice_InitiallyFiftyFifty(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	price := mm.Price(d(0), d(0))
	if !price.Equal(d(0.5)) {
		t.Errorf("expected initial price 0.5, got %s", price)
	}
}

func TestPrice_BuyingYesIncreasesPrice(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	priceBefore := mm.Price(d(0), d(0))
	priceAfter := mm.Price(d(10), d(0))
	if priceAfter.LessThanOrEqual(priceBefore) {
		t.Errorf("buying YES should increase price: before=%s after=%s",
			priceBefore, priceAfter)
	}
}

func TestPrice_BuyingNoDecreasesYesPrice(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	priceBefore := mm.Price(d(0), d(0))
	priceAfter := mm.Price(d(0), d(10))
	if priceAfter.GreaterThanOrEqual(priceBefore) {
		t.Errorf("buying NO should decrease YES price: before=%s after=%s",
			priceBefore, priceAfter)
	}
}

func TestPrice_SumsToOne(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	one := decimal.NewFromInt(1)
	tolerance := d(0.0000001)

	tests := []struct {
		qYes, qNo float64
	}{
		{0, 0},
		{10, 0},
		{0, 10},
		{30, 10},
		{100, 200},
		{500, 100},
		{-50, 30},
	}
	for _, tt := range tests {
		pYes := mm.Price(d(tt.qYes), d(tt.qNo))
		pNo := mm.PriceNo(d(tt.qYes), d(tt.qNo))
		sum := pYes.Add(pNo)
		if sum.Sub(one).Abs().GreaterThan(tolerance) {
			t.Errorf("prices should sum to 1: pYes=%s pNo=%s sum=%s (q=%.0f,%.0f)",
				pYes, pNo, sum, tt.qYes, tt.qNo)
		}
	}
}

// --- Trade cost tests ---

func TestTradeCost_BuyPositive(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	cost := mm.TradeCost(d(0), d(0), d(10))
	if cost.LessThanOrEqual(decimal.Zero) {
		t.Errorf("buying YES should cost positive amount, got %s", cost)
	}
}

func TestTradeCost_SellNegative(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	cost := mm.TradeCost(d(10), d(0), d(-10))
	if cost.GreaterThanOrEqual(decimal.Zero) {
		t.Errorf("selling YES should return money (negative cost), got %s", cost)
	}
}

func TestTradeCostNo_MatchesSymmetry(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	// Buying 10 NO from (0,0) should cost the same as buying 10 YES from (0,0)
	// because LMSR is symmetric at the origin.
	costYes := mm.TradeCost(d(0), d(0), d(10))
	costNo := mm.TradeCostNo(d(0), d(0), d(10))
	if !costYes.Equal(costNo) {
		t.Errorf("expected symmetric cost at origin: YES=%s NO=%s", costYes, costNo)
	}
}

func TestCost_PathIndependence(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	tolerance := d(0.0000001)

	// Buy 10, then buy 5 more should cost the same as buying 15 at once.
	cost1 := mm.TradeCost(d(0), d(0), d(10))
	cost2 := mm.TradeCost(d(10), d(0), d(5))
	sequential := cost1.Add(cost2)

	direct := mm.TradeCost(d(0), d(0), d(15))

	if sequential.Sub(direct).Abs().GreaterThan(tolerance) {
		t.Errorf("LMSR should be path-independent: sequential=%s direct=%s",
			sequential, direct)
	}
}

func TestCost_Convexity(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	// Second 10 shares should cost more than the first 10 (convex cost).
	cost1 := mm.TradeCost(d(0), d(0), d(10))
	cost2 := mm.TradeCost(d(10), d(0), d(10))
	if cost2.LessThanOrEqual(cost1) {
		t.Errorf("second batch should cost more (convexity): first=%s second=%s",
			cost1, cost2)
	}
}

// --- Bounded loss test ---

func TestMaxLoss_Bounded(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	maxLoss := mm.MaxLoss()

	// After many traders push qYes very high, the market maker's loss is bounded.
	// Scenario: trader buys 10000 YES shares, event happens (payout = 10000).
	initialCost := mm.Cost(d(0), d(0))
	highQCost := mm.Cost(d(10000), d(0))

	// Traders paid this much total:
	traderPaid := highQCost.Sub(initialCost)
	// Market maker must pay out 10000 (YES wins), so MM loss:
	mmLoss := decimal.NewFromInt(10000).Sub(traderPaid)

	if mmLoss.GreaterThan(maxLoss) {
		t.Errorf("market maker loss %s exceeds theoretical bound %s", mmLoss, maxLoss)
	}
}

// --- Boundary condition tests (edge cases / interview questions) ---

func TestPrice_ExtremeQuantities_NoPanic(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))

	tests := []struct {
		name      string
		qYes, qNo float64
	}{
		{"very large YES", 100000, 0},
		{"very large NO", 0, 100000},
		{"both large equal", 100000, 100000},
		{"large asymmetric", 100000, 50000},
		{"very negative YES", -100000, 0},
		{"very negative NO", 0, -100000},
		{"both very negative", -100000, -100000},
		{"overflow-scale values", 1e15, 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Should not panic.
			price := mm.Price(d(tt.qYes), d(tt.qNo))
			if price.LessThan(decimal.Zero) || price.GreaterThan(decimal.NewFromInt(1)) {
				t.Errorf("price out of [0,1]: %s", price)
			}
		})
	}
}

func TestPrice_ClampedToBounds(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))

	// Price approaching 1 (huge qYes relative to qNo).
	price := mm.Price(d(100000), d(0))
	if price.GreaterThan(MaxPrice) {
		t.Errorf("price %s exceeds MaxPrice %s", price, MaxPrice)
	}
	if price.LessThan(MaxPrice) {
		t.Errorf("expected price to be clamped to MaxPrice %s, got %s", MaxPrice, price)
	}

	// Price approaching 0 (huge qNo relative to qYes).
	price = mm.Price(d(0), d(100000))
	if price.LessThan(MinPrice) {
		t.Errorf("price %s below MinPrice %s", price, MinPrice)
	}
	if price.GreaterThan(MinPrice) {
		t.Errorf("expected price to be clamped to MinPrice %s, got %s", MinPrice, price)
	}
}

func TestValidateTrade_RejectsBeyondBounds(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))

	// Massive buy pushes YES price near 1.
	err := mm.ValidateTrade(d(0), d(0), d(100000))
	if err != ErrPriceBoundExceeded {
		t.Errorf("expected ErrPriceBoundExceeded for massive buy, got %v", err)
	}

	// Massive sell pushes YES price near 0.
	err = mm.ValidateTrade(d(0), d(0), d(-100000))
	if err != ErrPriceBoundExceeded {
		t.Errorf("expected ErrPriceBoundExceeded for massive sell, got %v", err)
	}
}

func TestValidateTradeNo_RejectsBeyondBounds(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))

	// Massive NO buy pushes YES price near 0.
	err := mm.ValidateTradeNo(d(0), d(0), d(100000))
	if err != ErrPriceBoundExceeded {
		t.Errorf("expected ErrPriceBoundExceeded for massive NO buy, got %v", err)
	}
}

func TestValidateTrade_AcceptsModerate(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	err := mm.ValidateTrade(d(0), d(0), d(10))
	if err != nil {
		t.Errorf("moderate trade should be accepted, got %v", err)
	}
}

// --- Fill price tests ---

func TestFillPrice_SmallTrade(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	// For a tiny trade at equal quantities, fill price ≈ 0.5.
	fill := mm.FillPrice(d(0), d(0), d(0.001))
	if fill.Sub(d(0.5)).Abs().GreaterThan(d(0.01)) {
		t.Errorf("small trade fill price should be ≈ 0.5, got %s", fill)
	}
}

func TestFillPrice_ZeroDelta(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))
	fill := mm.FillPrice(d(0), d(0), d(0))
	if !fill.Equal(d(0.5)) {
		t.Errorf("zero-delta fill price should equal current price 0.5, got %s", fill)
	}
}

func TestFillPrice_PositiveForBothBuyAndSell(t *testing.T) {
	mm, _ := NewMarketMaker(d(100))

	buyFill := mm.FillPrice(d(0), d(0), d(10))
	if buyFill.LessThanOrEqual(decimal.Zero) {
		t.Errorf("buy fill price should be positive, got %s", buyFill)
	}

	sellFill := mm.FillPrice(d(10), d(0), d(-10))
	if sellFill.LessThanOrEqual(decimal.Zero) {
		t.Errorf("sell fill price should be positive, got %s", sellFill)
	}
}

// --- NWS confidence interval tests ---

func TestNewMarketMakerFromNWSConfidence_WiderCIHigherB(t *testing.T) {
	// Wider confidence interval → more uncertainty → higher b.
	mmWide, err := NewMarketMakerFromNWSConfidence(
		d(10), d(40), d(25), d(100),
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	mmNarrow, err := NewMarketMakerFromNWSConfidence(
		d(20), d(30), d(25), d(100),
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if mmWide.B().LessThanOrEqual(mmNarrow.B()) {
		t.Errorf("wider CI should produce higher b: wide=%s narrow=%s",
			mmWide.B(), mmNarrow.B())
	}
}

func TestNewMarketMakerFromNWSConfidence_InvalidInputs(t *testing.T) {
	// Zero median.
	_, err := NewMarketMakerFromNWSConfidence(d(10), d(40), d(0), d(100))
	if err == nil {
		t.Error("expected error for zero median")
	}

	// Inverted percentiles.
	_, err = NewMarketMakerFromNWSConfidence(d(40), d(10), d(25), d(100))
	if err == nil {
		t.Error("expected error for inverted percentiles")
	}
}

func TestNewMarketMakerFromNWSConfidence_MinimumB(t *testing.T) {
	// Very narrow CI with small base volume should still get minimum b.
	mm, err := NewMarketMakerFromNWSConfidence(d(24), d(26), d(25), d(1))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	minB := decimal.NewFromInt(10)
	if mm.B().LessThan(minB) {
		t.Errorf("b should be at least %s, got %s", minB, mm.B())
	}
}

// --- Internal logSumExp tests ---

func TestLogSumExp_NoOverflow(t *testing.T) {
	// Values that would overflow naive exp().
	result := logSumExp([]float64{1000, 1001})
	if math.IsNaN(result) || math.IsInf(result, 1) {
		t.Errorf("logSumExp should not overflow: got %f", result)
	}
	if result < 1000 || result > 1002 {
		t.Errorf("logSumExp(1000,1001) should be in [1000,1002], got %f", result)
	}
}

func TestLogSumExp_Empty(t *testing.T) {
	result := logSumExp(nil)
	if !math.IsInf(result, -1) {
		t.Errorf("expected -Inf for empty input, got %f", result)
	}
}

func TestLogSumExp_SingleValue(t *testing.T) {
	result := logSumExp([]float64{5.0})
	if math.Abs(result-5.0) > 1e-10 {
		t.Errorf("logSumExp([5]) should be 5, got %f", result)
	}
}

func TestLogSumExp_EqualValues(t *testing.T) {
	// ln(n * exp(x)) = x + ln(n)
	result := logSumExp([]float64{3, 3})
	expected := 3.0 + math.Log(2)
	if math.Abs(result-expected) > 1e-10 {
		t.Errorf("logSumExp([3,3]) should be %f, got %f", expected, result)
	}
}

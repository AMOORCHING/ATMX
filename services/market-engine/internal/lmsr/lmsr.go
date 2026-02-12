// Package lmsr implements the Logarithmic Market Scoring Rule (LMSR)
// automated market maker for binary weather derivative markets.
//
// The LMSR was proposed by Robin Hanson and provides:
//   - Bounded loss for the market maker (capped at b * ln(n))
//   - Continuous pricing with infinite liquidity
//   - Path-independent cost function
//
// All monetary values use shopspring/decimal — never float64 for money.
// Internal transcendental math uses the log-sum-exp trick for numerical
// stability, with results immediately converted to decimal.
//
// Reference: Hanson, R. (2003) "Combinatorial Information Market Design"
package lmsr

import (
	"errors"
	"math"

	"github.com/shopspring/decimal"
)

var (
	// ErrInvalidLiquidity is returned when b <= 0.
	ErrInvalidLiquidity = errors.New("lmsr: liquidity parameter b must be positive")

	// ErrPriceBoundExceeded is returned when a trade would push prices
	// beyond the allowed bounds [MinPrice, MaxPrice].
	ErrPriceBoundExceeded = errors.New("lmsr: trade would push price beyond allowed bounds")

	// MinPrice is the lowest allowed price (probability floor).
	// Prevents degenerate markets where shares become worthless.
	MinPrice = decimal.NewFromFloat(0.001)

	// MaxPrice is the highest allowed price (probability ceiling).
	// Prevents degenerate markets where outcome appears "certain".
	MaxPrice = decimal.NewFromFloat(0.999)

	// PriceScale is the number of decimal places for price/cost rounding.
	PriceScale int32 = 8
)

// MarketMaker implements the LMSR cost function for binary outcome markets.
// It is stateless — market quantities are passed as arguments, not stored.
type MarketMaker struct {
	b decimal.Decimal
}

// NewMarketMaker creates a new LMSR market maker with the given liquidity
// parameter b. Higher b → more liquidity, lower price impact per trade.
// Maximum market-maker loss is bounded by b * ln(2) for binary markets.
func NewMarketMaker(b decimal.Decimal) (*MarketMaker, error) {
	if b.LessThanOrEqual(decimal.Zero) {
		return nil, ErrInvalidLiquidity
	}
	return &MarketMaker{b: b}, nil
}

// B returns the liquidity parameter.
func (m *MarketMaker) B() decimal.Decimal {
	return m.b
}

// logSumExp computes ln(Σ exp(x_i)) using the log-sum-exp trick to prevent
// floating-point overflow. Without this trick, exp(x) overflows float64
// when x > ~709.
//
// Algorithm: LSE(x) = max(x) + ln(Σ exp(x_i - max(x)))
// Since (x_i - max(x)) <= 0, all exp arguments are in [0, 1].
func logSumExp(xs []float64) float64 {
	if len(xs) == 0 {
		return math.Inf(-1)
	}

	maxVal := xs[0]
	for _, x := range xs[1:] {
		if x > maxVal {
			maxVal = x
		}
	}

	if math.IsInf(maxVal, -1) {
		return math.Inf(-1)
	}

	var sum float64
	for _, x := range xs {
		sum += math.Exp(x - maxVal)
	}
	return maxVal + math.Log(sum)
}

// Cost computes the LMSR cost function:
//
//	C(q) = b * ln(Σ exp(q_i / b))
//
// For binary markets, q = [qYes, qNo].
// Uses logSumExp internally for numerical stability.
func (m *MarketMaker) Cost(qYes, qNo decimal.Decimal) decimal.Decimal {
	bf := m.b.InexactFloat64()
	qy := qYes.InexactFloat64()
	qn := qNo.InexactFloat64()

	lse := logSumExp([]float64{qy / bf, qn / bf})
	cost := bf * lse

	return decimal.NewFromFloat(cost).Round(PriceScale)
}

// Price computes the instantaneous price (probability) for the YES outcome:
//
//	p_yes = exp(qYes / b) / (exp(qYes / b) + exp(qNo / b))
//
// This is the softmax function. Uses max-subtraction for numerical stability.
// Result is clamped to [MinPrice, MaxPrice] to prevent degenerate pricing.
func (m *MarketMaker) Price(qYes, qNo decimal.Decimal) decimal.Decimal {
	bf := m.b.InexactFloat64()
	qy := qYes.InexactFloat64()
	qn := qNo.InexactFloat64()

	// Softmax with numerical stability: subtract max to avoid overflow.
	yOverB := qy / bf
	nOverB := qn / bf
	maxVal := math.Max(yOverB, nOverB)

	expYes := math.Exp(yOverB - maxVal)
	expNo := math.Exp(nOverB - maxVal)

	price := expYes / (expYes + expNo)
	result := decimal.NewFromFloat(price).Round(PriceScale)

	// Clamp to bounds.
	if result.LessThan(MinPrice) {
		return MinPrice
	}
	if result.GreaterThan(MaxPrice) {
		return MaxPrice
	}
	return result
}

// PriceNo returns the instantaneous price for the NO outcome: 1 - p_yes.
func (m *MarketMaker) PriceNo(qYes, qNo decimal.Decimal) decimal.Decimal {
	return decimal.NewFromInt(1).Sub(m.Price(qYes, qNo))
}

// TradeCost computes the cost to change the YES quantity by deltaYes shares:
//
//	cost = C(qYes + deltaYes, qNo) - C(qYes, qNo)
//
// Positive deltaYes = buying YES (positive cost to trader).
// Negative deltaYes = selling YES (negative cost = payout to trader).
func (m *MarketMaker) TradeCost(qYes, qNo, deltaYes decimal.Decimal) decimal.Decimal {
	costBefore := m.Cost(qYes, qNo)
	costAfter := m.Cost(qYes.Add(deltaYes), qNo)
	return costAfter.Sub(costBefore)
}

// TradeCostNo computes the cost to change the NO quantity by deltaNo shares.
// Uses the symmetry property: C(a, b) = C(b, a).
//
//	cost = C(qYes, qNo + deltaNo) - C(qYes, qNo)
func (m *MarketMaker) TradeCostNo(qYes, qNo, deltaNo decimal.Decimal) decimal.Decimal {
	// By LMSR symmetry, C(qYes, qNo + d) - C(qYes, qNo)
	// = C(qNo + d, qYes) - C(qNo, qYes)
	return m.TradeCost(qNo, qYes, deltaNo)
}

// FillPrice returns the average execution price per share for a trade.
//
//	fillPrice = cost / delta
//
// Positive for both buys (cost>0, delta>0) and sells (cost<0, delta<0).
func (m *MarketMaker) FillPrice(qFirst, qSecond, delta decimal.Decimal) decimal.Decimal {
	if delta.IsZero() {
		return m.Price(qFirst, qSecond)
	}
	cost := m.TradeCost(qFirst, qSecond, delta)
	return cost.Div(delta).Round(PriceScale)
}

// validatePriceAfterTrade checks whether the resulting YES price is within
// the allowed bounds after updating quantities.
func (m *MarketMaker) validatePriceAfterTrade(newQYes, newQNo decimal.Decimal) error {
	bf := m.b.InexactFloat64()
	qy := newQYes.InexactFloat64()
	qn := newQNo.InexactFloat64()

	maxVal := math.Max(qy/bf, qn/bf)
	expYes := math.Exp(qy/bf - maxVal)
	expNo := math.Exp(qn/bf - maxVal)
	price := expYes / (expYes + expNo)

	minF := MinPrice.InexactFloat64()
	maxF := MaxPrice.InexactFloat64()
	if price < minF || price > maxF {
		return ErrPriceBoundExceeded
	}
	return nil
}

// ValidateTrade checks if a YES-side trade would push prices beyond bounds.
func (m *MarketMaker) ValidateTrade(qYes, qNo, deltaYes decimal.Decimal) error {
	return m.validatePriceAfterTrade(qYes.Add(deltaYes), qNo)
}

// ValidateTradeNo checks if a NO-side trade would push prices beyond bounds.
func (m *MarketMaker) ValidateTradeNo(qYes, qNo, deltaNo decimal.Decimal) error {
	return m.validatePriceAfterTrade(qYes, qNo.Add(deltaNo))
}

// MaxLoss returns the maximum possible loss for the market maker: b * ln(n),
// where n = 2 for binary markets.
func (m *MarketMaker) MaxLoss() decimal.Decimal {
	bf := m.b.InexactFloat64()
	loss := bf * math.Log(2)
	return decimal.NewFromFloat(loss).Round(PriceScale)
}

// NewMarketMakerFromNWSConfidence derives the liquidity parameter b from
// NWS probabilistic forecast confidence intervals.
//
// The NWS publishes ensemble-based percentile forecasts (e.g., 10th, 25th,
// 50th, 75th, 90th percentiles for QPF) in machine-readable formats:
//   - NDFD GRIB2 files via NOAA NOMADS
//   - weather.gov API /gridpoints/{office}/{x},{y}
//   - HREF (High-Resolution Ensemble Forecast) products
//
// The interquartile range (IQR = P75 - P25) measures forecast uncertainty.
// Wider IQR → higher b → more liquidity → encourages price discovery.
// Narrower IQR → lower b → less subsidy → market converges quickly.
//
// Formula: b = baseVolume × (IQR / median)
func NewMarketMakerFromNWSConfidence(
	percentile25, percentile75, median, baseVolume decimal.Decimal,
) (*MarketMaker, error) {
	if median.LessThanOrEqual(decimal.Zero) {
		return nil, errors.New("lmsr: median must be positive")
	}

	iqr := percentile75.Sub(percentile25)
	if iqr.LessThanOrEqual(decimal.Zero) {
		return nil, errors.New("lmsr: 75th percentile must exceed 25th percentile")
	}

	b := baseVolume.Mul(iqr).Div(median)

	// Enforce minimum b to prevent degenerate markets.
	minB := decimal.NewFromInt(10)
	if b.LessThan(minB) {
		b = minB
	}

	return &MarketMaker{b: b}, nil
}

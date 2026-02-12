package correlation

import (
	"testing"

	"github.com/shopspring/decimal"
)

func d(f float64) decimal.Decimal {
	return decimal.NewFromFloat(f)
}

func TestCheckLimit_WithinLimits(t *testing.T) {
	limiter := NewPositionLimiter(d(1000), d(5000), 5)

	err := limiter.CheckLimit("872a1070b", d(100), nil)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestCheckLimit_PerCellExceeded(t *testing.T) {
	limiter := NewPositionLimiter(d(1000), d(5000), 5)

	// Existing position of 950 + new 100 = 1050 > 1000.
	existing := map[string]decimal.Decimal{
		"872a1070b": d(950),
	}

	err := limiter.CheckLimit("872a1070b", d(100), existing)
	if err != ErrPerCellLimitExceeded {
		t.Errorf("expected ErrPerCellLimitExceeded, got %v", err)
	}
}

func TestCheckLimit_PerCellNotExceeded(t *testing.T) {
	limiter := NewPositionLimiter(d(1000), d(5000), 5)

	existing := map[string]decimal.Decimal{
		"872a1070b": d(500),
	}

	err := limiter.CheckLimit("872a1070b", d(100), existing)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestCheckLimit_CorrelatedExceeded(t *testing.T) {
	// PrefixLen=5: cells "872a1070b" and "872a1070c" share prefix "872a1"
	// and are considered correlated.
	limiter := NewPositionLimiter(d(1000), d(2000), 5)

	existing := map[string]decimal.Decimal{
		"872a1070b": d(800),  // correlated (prefix "872a1")
		"872a1070c": d(800),  // correlated (prefix "872a1")
		"872a1070d": d(300),  // correlated (prefix "872a1")
	}

	// New trade of 200 in another correlated cell:
	// total = 200 + 800 + 800 + 300 = 2100 > 2000
	err := limiter.CheckLimit("872a1070e", d(200), existing)
	if err != ErrCorrelatedLimitExceeded {
		t.Errorf("expected ErrCorrelatedLimitExceeded, got %v", err)
	}
}

func TestCheckLimit_NonCorrelatedCellsIgnored(t *testing.T) {
	limiter := NewPositionLimiter(d(1000), d(2000), 5)

	existing := map[string]decimal.Decimal{
		"872a1070b": d(800),  // correlated with target (prefix "872a1")
		"882b2070a": d(900),  // NOT correlated (prefix "882b2")
	}

	// Correlated total = 500 + 800 = 1300 < 2000 (882b2 cell excluded).
	err := limiter.CheckLimit("872a1070c", d(500), existing)
	if err != nil {
		t.Errorf("non-correlated cells should be ignored, got %v", err)
	}
}

func TestCheckLimit_SellReducesExposure(t *testing.T) {
	limiter := NewPositionLimiter(d(1000), d(5000), 5)

	existing := map[string]decimal.Decimal{
		"872a1070b": d(800),
	}

	// Selling (negative delta) reduces exposure: 800 - 200 = 600 < 1000.
	err := limiter.CheckLimit("872a1070b", d(-200), existing)
	if err != nil {
		t.Errorf("sell should reduce exposure, got %v", err)
	}
}

func TestCheckLimit_HurricaneScenario(t *testing.T) {
	// Simulate a hurricane path: 20 correlated cells, each with position 200.
	// MaxCorrelated = 3000 means a user can't have more than 3000 total
	// across the hurricane path.
	limiter := NewPositionLimiter(d(500), d(3000), 5)

	existing := make(map[string]decimal.Decimal)
	// 15 cells along the hurricane path (all share prefix "872a1").
	for i := 0; i < 15; i++ {
		cellID := "872a1070" + string(rune('a'+i))
		existing[cellID] = d(200)
	}

	// Total existing = 15 × 200 = 3000. Adding 100 more → 3100 > 3000.
	err := limiter.CheckLimit("872a1070z", d(100), existing)
	if err != ErrCorrelatedLimitExceeded {
		t.Errorf("expected correlated limit exceeded for hurricane path, got %v", err)
	}
}

func TestCheckLimit_NilExposures(t *testing.T) {
	limiter := NewPositionLimiter(d(1000), d(5000), 5)

	err := limiter.CheckLimit("872a1070b", d(500), nil)
	if err != nil {
		t.Errorf("nil exposures should be treated as empty, got %v", err)
	}
}

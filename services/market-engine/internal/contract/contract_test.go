package contract

import (
	"testing"
	"time"

	"github.com/shopspring/decimal"
)

func d(f float64) decimal.Decimal {
	return decimal.NewFromFloat(f)
}

func TestParseTicker_Valid(t *testing.T) {
	c, err := ParseTicker("ATMX-872a1070b-PRECIP-25MM-20250815")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if c.H3CellID != "872a1070b" {
		t.Errorf("expected h3_cell_id=872a1070b, got %s", c.H3CellID)
	}
	if c.Type != TypePrecip {
		t.Errorf("expected type=PRECIP, got %s", c.Type)
	}
	if c.Threshold != "25MM" {
		t.Errorf("expected threshold=25MM, got %s", c.Threshold)
	}
	expected := time.Date(2025, 8, 15, 0, 0, 0, 0, time.UTC)
	if !c.ExpiryDate.Equal(expected) {
		t.Errorf("expected expiry=%v, got %v", expected, c.ExpiryDate)
	}
}

func TestParseTicker_InvalidFormat(t *testing.T) {
	tests := []string{
		"",
		"INVALID",
		"ATMX-872a1070b",
		"ATMX-872a1070b-PRECIP",
		"ATMX-872a1070b-PRECIP-25MM",
		"ATMX-872a1070b-PRECIP-25MM-notadate",
		"BTC-872a1070b-PRECIP-25MM-20250815", // wrong prefix
		"ATMX-ZZZZ-PRECIP-25MM-20250815",     // non-hex H3 cell
	}
	for _, ticker := range tests {
		_, err := ParseTicker(ticker)
		if err == nil {
			t.Errorf("expected error for ticker %q", ticker)
		}
	}
}

func TestParseTicker_InvalidType(t *testing.T) {
	_, err := ParseTicker("ATMX-872a1070b-INVALID-25MM-20250815")
	if err == nil {
		t.Error("expected error for invalid contract type")
	}
}

func TestParseTicker_AllTypes(t *testing.T) {
	types := []string{"PRECIP", "TEMP", "WIND", "SNOW"}
	for _, typ := range types {
		ticker := "ATMX-872a1070b-" + typ + "-25MM-20250815"
		c, err := ParseTicker(ticker)
		if err != nil {
			t.Errorf("unexpected error for type %s: %v", typ, err)
		}
		if c.Type != typ {
			t.Errorf("expected type=%s, got %s", typ, c.Type)
		}
	}
}

func TestDeriveLiquidity_WiderCIHigherB(t *testing.T) {
	base := d(100)

	wide := NWSForecastData{
		Percentile25: d(10),
		Percentile50: d(25),
		Percentile75: d(40),
	}
	narrow := NWSForecastData{
		Percentile25: d(20),
		Percentile50: d(25),
		Percentile75: d(30),
	}

	bWide, err := DeriveLiquidity(wide, base)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	bNarrow, err := DeriveLiquidity(narrow, base)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if bWide.LessThanOrEqual(bNarrow) {
		t.Errorf("wider CI should give higher b: wide=%s narrow=%s", bWide, bNarrow)
	}
}

func TestDeriveLiquidity_ZeroMedian(t *testing.T) {
	// Dry conditions: median = 0, but some ensemble members show rain.
	nws := NWSForecastData{
		Percentile25: d(0),
		Percentile50: d(0),
		Percentile75: d(5),
	}
	b, err := DeriveLiquidity(nws, d(100))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if b.LessThanOrEqual(decimal.Zero) {
		t.Errorf("b should be positive, got %s", b)
	}
}

func TestDeriveLiquidity_MinimumB(t *testing.T) {
	// Very narrow CI should still produce at least minB.
	nws := NWSForecastData{
		Percentile25: d(24.9),
		Percentile50: d(25),
		Percentile75: d(25.1),
	}
	b, err := DeriveLiquidity(nws, d(1))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if b.LessThan(d(10)) {
		t.Errorf("b should be at least 10, got %s", b)
	}
}

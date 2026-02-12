// Package contract handles weather derivative contract ticker parsing,
// validation, and derivation of LMSR parameters from NWS forecast data.
package contract

import (
	"errors"
	"fmt"
	"regexp"
	"time"

	"github.com/shopspring/decimal"
)

// Supported contract types.
const (
	TypePrecip = "PRECIP"
	TypeTemp   = "TEMP"
	TypeWind   = "WIND"
	TypeSnow   = "SNOW"
)

var validTypes = map[string]bool{
	TypePrecip: true,
	TypeTemp:   true,
	TypeWind:   true,
	TypeSnow:   true,
}

// tickerRegex matches: ATMX-{h3CellID}-{type}-{threshold}-{YYYYMMDD}
// Example: ATMX-872a1070b-PRECIP-25MM-20250815
var tickerRegex = regexp.MustCompile(
	`^ATMX-([0-9a-f]+)-([A-Z]+)-([0-9]+[A-Z]*)-(\d{8})$`,
)

var (
	ErrInvalidTicker = errors.New("contract: invalid ticker format")
	ErrInvalidType   = errors.New("contract: unsupported contract type")
)

// Contract represents a parsed weather derivative contract.
type Contract struct {
	Ticker     string    `json:"ticker"`
	H3CellID   string    `json:"h3_cell_id"`
	Type       string    `json:"type"`
	Threshold  string    `json:"threshold"`
	ExpiryDate time.Time `json:"expiry_date"`
}

// ParseTicker parses and validates a contract ticker string.
// Format: ATMX-{h3CellID}-{type}-{threshold}-{YYYYMMDD}
func ParseTicker(ticker string) (*Contract, error) {
	matches := tickerRegex.FindStringSubmatch(ticker)
	if matches == nil {
		return nil, fmt.Errorf("%w: %s (expected ATMX-{h3cell}-{type}-{threshold}-{YYYYMMDD})",
			ErrInvalidTicker, ticker)
	}

	h3Cell := matches[1]
	contractType := matches[2]
	threshold := matches[3]
	dateStr := matches[4]

	if !validTypes[contractType] {
		return nil, fmt.Errorf("%w: %s", ErrInvalidType, contractType)
	}

	expiry, err := time.Parse("20060102", dateStr)
	if err != nil {
		return nil, fmt.Errorf("%w: invalid date %s", ErrInvalidTicker, dateStr)
	}

	return &Contract{
		Ticker:     ticker,
		H3CellID:   h3Cell,
		Type:       contractType,
		Threshold:  threshold,
		ExpiryDate: expiry,
	}, nil
}

// NWSForecastData holds machine-readable NWS probabilistic forecast data.
// These values are published by the NWS NDFD (National Digital Forecast
// Database) in GRIB2 format and via the weather.gov API.
type NWSForecastData struct {
	// Percentile values from NWS ensemble forecasts (HREF, NAEFS, etc.)
	Percentile10 decimal.Decimal `json:"percentile_10"`
	Percentile25 decimal.Decimal `json:"percentile_25"`
	Percentile50 decimal.Decimal `json:"percentile_50"` // median
	Percentile75 decimal.Decimal `json:"percentile_75"`
	Percentile90 decimal.Decimal `json:"percentile_90"`
}

// DeriveLiquidity computes the LMSR b parameter from NWS forecast data.
// Uses the interquartile range (IQR = P75 - P25) relative to the median
// as a measure of forecast uncertainty, scaled by baseVolume.
//
// Data sources (all machine-readable, no LLM needed):
//   - NDFD GRIB2 files via NOAA NOMADS
//   - weather.gov API /gridpoints/{office}/{x},{y}
//   - HREF ensemble products
//   - Probabilistic QPF exceedance probabilities
func DeriveLiquidity(nws NWSForecastData, baseVolume decimal.Decimal) (decimal.Decimal, error) {
	iqr := nws.Percentile75.Sub(nws.Percentile25)
	median := nws.Percentile50

	if median.LessThanOrEqual(decimal.Zero) {
		// For dry conditions (median = 0), use absolute IQR.
		if iqr.LessThanOrEqual(decimal.Zero) {
			return decimal.NewFromInt(10), nil // minimum b
		}
		b := baseVolume.Mul(iqr)
		minB := decimal.NewFromInt(10)
		if b.LessThan(minB) {
			return minB, nil
		}
		return b.Round(2), nil
	}

	// Coefficient of variation: IQR / median.
	cv := iqr.Div(median)
	b := baseVolume.Mul(cv)

	// Enforce minimum b to prevent degenerate markets.
	minB := decimal.NewFromInt(10)
	if b.LessThan(minB) {
		return minB, nil
	}
	return b.Round(2), nil
}

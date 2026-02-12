// Package correlation implements position limits that account for geographic
// correlation between H3 hexagonal cells.
//
// When a hurricane path spans 20 hexagons, a user buying YES on all of them
// has correlated risk. This package detects geographic proximity between H3
// cells using index prefix matching and enforces aggregate position limits.
package correlation

import (
	"errors"

	"github.com/shopspring/decimal"
)

var (
	// ErrPerCellLimitExceeded is returned when a trade would push a single
	// cell's position beyond the per-cell maximum.
	ErrPerCellLimitExceeded = errors.New("correlation: per-cell position limit exceeded")

	// ErrCorrelatedLimitExceeded is returned when a trade would push the
	// aggregate exposure across geographically correlated cells beyond the
	// correlated maximum.
	ErrCorrelatedLimitExceeded = errors.New("correlation: correlated exposure limit exceeded")
)

// PositionLimiter enforces position limits with correlation awareness.
//
// Correlation detection uses H3 index prefix matching:
//   - H3 indices encode spatial hierarchy in their hex digits
//   - Cells sharing a longer prefix tend to be geographically closer
//   - PrefixLen controls the correlation radius:
//     For resolution-7 cells (9-char index):
//     PrefixLen=7 → close neighbors (k-ring ~1-2)
//     PrefixLen=6 → moderate area (k-ring ~3-5)
//     PrefixLen=5 → wide area, hurricane scale (k-ring ~10+)
//
// For production use with exact spatial queries, this can be backed by
// the H3 C library (uber/h3-go) for precise k-ring computation.
type PositionLimiter struct {
	// MaxPerCell is the maximum absolute net position in any single cell.
	MaxPerCell decimal.Decimal

	// MaxCorrelated is the maximum aggregate absolute exposure across
	// all cells that share the same H3 prefix (correlated group).
	MaxCorrelated decimal.Decimal

	// PrefixLen determines how many leading hex characters of the H3
	// index must match for two cells to be considered correlated.
	PrefixLen int
}

// NewPositionLimiter creates a limiter with the given per-cell and
// correlated exposure limits.
func NewPositionLimiter(maxPerCell, maxCorrelated decimal.Decimal, prefixLen int) *PositionLimiter {
	if prefixLen < 1 {
		prefixLen = 1
	}
	return &PositionLimiter{
		MaxPerCell:    maxPerCell,
		MaxCorrelated: maxCorrelated,
		PrefixLen:     prefixLen,
	}
}

// CheckLimit validates whether a trade respects position limits.
//
// Parameters:
//   - targetCell: H3 cell ID of the contract being traded
//   - exposureDelta: signed change in exposure (+YES / -NO direction)
//   - existingExposures: map of H3 cell ID → current net exposure for this user
//
// Returns nil if the trade is within limits, or an error describing the violation.
func (l *PositionLimiter) CheckLimit(
	targetCell string,
	exposureDelta decimal.Decimal,
	existingExposures map[string]decimal.Decimal,
) error {
	// 1. Per-cell limit.
	currentInCell := existingExposures[targetCell]
	newPosition := currentInCell.Add(exposureDelta)

	if newPosition.Abs().GreaterThan(l.MaxPerCell) {
		return ErrPerCellLimitExceeded
	}

	// 2. Correlated exposure: sum |exposure| across cells sharing prefix.
	targetPrefix := cellPrefix(targetCell, l.PrefixLen)
	totalCorrelated := newPosition.Abs()

	for cellID, exposure := range existingExposures {
		if cellID == targetCell {
			continue // already counted via newPosition above
		}
		if cellPrefix(cellID, l.PrefixLen) == targetPrefix {
			totalCorrelated = totalCorrelated.Add(exposure.Abs())
		}
	}

	if totalCorrelated.GreaterThan(l.MaxCorrelated) {
		return ErrCorrelatedLimitExceeded
	}

	return nil
}

// cellPrefix returns the first `length` characters of an H3 cell ID.
func cellPrefix(cellID string, length int) string {
	if length >= len(cellID) {
		return cellID
	}
	return cellID[:length]
}

package store

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/shopspring/decimal"

	"github.com/atmx/market-engine/internal/model"
)

// PostgresStore implements Store using PostgreSQL as the source of truth.
// All monetary values are stored as NUMERIC for exact decimal precision.
type PostgresStore struct {
	pool *pgxpool.Pool
}

// NewPostgresStore creates a new PostgreSQL-backed store.
func NewPostgresStore(pool *pgxpool.Pool) *PostgresStore {
	return &PostgresStore{pool: pool}
}

func (s *PostgresStore) CreateMarket(ctx context.Context, m *model.Market) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO markets (id, contract_id, h3_cell_id, q_yes, q_no, b, price_yes, price_no, status, created_at)
		 VALUES ($1, $2, $3, $4::NUMERIC, $5::NUMERIC, $6::NUMERIC, $7::NUMERIC, $8::NUMERIC, $9, $10)`,
		m.ID, m.ContractID, m.H3CellID,
		m.QYes.String(), m.QNo.String(), m.B.String(),
		m.PriceYes.String(), m.PriceNo.String(),
		m.Status, m.CreatedAt,
	)
	return err
}

func (s *PostgresStore) GetMarket(ctx context.Context, id string) (*model.Market, error) {
	var m model.Market
	var qYes, qNo, b, priceYes, priceNo string

	err := s.pool.QueryRow(ctx,
		`SELECT id, contract_id, h3_cell_id,
		        q_yes::TEXT, q_no::TEXT, b::TEXT,
		        price_yes::TEXT, price_no::TEXT,
		        status, created_at
		 FROM markets WHERE id = $1`, id).
		Scan(&m.ID, &m.ContractID, &m.H3CellID,
			&qYes, &qNo, &b,
			&priceYes, &priceNo,
			&m.Status, &m.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("get market %s: %w", id, err)
	}

	m.QYes, _ = decimal.NewFromString(qYes)
	m.QNo, _ = decimal.NewFromString(qNo)
	m.B, _ = decimal.NewFromString(b)
	m.PriceYes, _ = decimal.NewFromString(priceYes)
	m.PriceNo, _ = decimal.NewFromString(priceNo)

	return &m, nil
}

func (s *PostgresStore) GetMarketByContract(ctx context.Context, contractID string) (*model.Market, error) {
	var m model.Market
	var qYes, qNo, b, priceYes, priceNo string

	err := s.pool.QueryRow(ctx,
		`SELECT id, contract_id, h3_cell_id,
		        q_yes::TEXT, q_no::TEXT, b::TEXT,
		        price_yes::TEXT, price_no::TEXT,
		        status, created_at
		 FROM markets WHERE contract_id = $1`, contractID).
		Scan(&m.ID, &m.ContractID, &m.H3CellID,
			&qYes, &qNo, &b,
			&priceYes, &priceNo,
			&m.Status, &m.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("get market by contract %s: %w", contractID, err)
	}

	m.QYes, _ = decimal.NewFromString(qYes)
	m.QNo, _ = decimal.NewFromString(qNo)
	m.B, _ = decimal.NewFromString(b)
	m.PriceYes, _ = decimal.NewFromString(priceYes)
	m.PriceNo, _ = decimal.NewFromString(priceNo)

	return &m, nil
}

func (s *PostgresStore) ListMarkets(ctx context.Context) ([]model.Market, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, contract_id, h3_cell_id,
		        q_yes::TEXT, q_no::TEXT, b::TEXT,
		        price_yes::TEXT, price_no::TEXT,
		        status, created_at
		 FROM markets ORDER BY created_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var markets []model.Market
	for rows.Next() {
		var m model.Market
		var qYes, qNo, b, priceYes, priceNo string
		if err := rows.Scan(&m.ID, &m.ContractID, &m.H3CellID,
			&qYes, &qNo, &b,
			&priceYes, &priceNo,
			&m.Status, &m.CreatedAt); err != nil {
			return nil, err
		}
		m.QYes, _ = decimal.NewFromString(qYes)
		m.QNo, _ = decimal.NewFromString(qNo)
		m.B, _ = decimal.NewFromString(b)
		m.PriceYes, _ = decimal.NewFromString(priceYes)
		m.PriceNo, _ = decimal.NewFromString(priceNo)
		markets = append(markets, m)
	}
	return markets, rows.Err()
}

func (s *PostgresStore) UpdateMarketState(ctx context.Context, id string, qYes, qNo, priceYes, priceNo decimal.Decimal) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE markets
		 SET q_yes = $2::NUMERIC, q_no = $3::NUMERIC,
		     price_yes = $4::NUMERIC, price_no = $5::NUMERIC
		 WHERE id = $1`,
		id, qYes.String(), qNo.String(), priceYes.String(), priceNo.String(),
	)
	return err
}

func (s *PostgresStore) InsertLedgerEntry(ctx context.Context, e *model.LedgerEntry) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO ledger_entries (id, user_id, market_id, contract_id, side, quantity, price, cost, timestamp)
		 VALUES ($1, $2, $3, $4, $5, $6::NUMERIC, $7::NUMERIC, $8::NUMERIC, $9)`,
		e.ID, e.UserID, e.MarketID, e.ContractID, e.Side,
		e.Quantity.String(), e.Price.String(), e.Cost.String(),
		e.Timestamp,
	)
	return err
}

func (s *PostgresStore) GetLedgerEntriesByMarket(ctx context.Context, marketID string) ([]model.LedgerEntry, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, user_id, market_id, contract_id, side,
		        quantity::TEXT, price::TEXT, cost::TEXT, timestamp
		 FROM ledger_entries WHERE market_id = $1 ORDER BY timestamp`, marketID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return scanLedgerEntries(rows)
}

func (s *PostgresStore) GetLedgerEntriesByUser(ctx context.Context, userID string) ([]model.LedgerEntry, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, user_id, market_id, contract_id, side,
		        quantity::TEXT, price::TEXT, cost::TEXT, timestamp
		 FROM ledger_entries WHERE user_id = $1 ORDER BY timestamp`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return scanLedgerEntries(rows)
}

func (s *PostgresStore) GetUserPositions(ctx context.Context, userID string) ([]model.Position, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT
			le.market_id,
			m.contract_id,
			m.h3_cell_id,
			COALESCE(SUM(CASE WHEN le.side = 'YES' THEN le.quantity ELSE 0 END), 0)::TEXT AS yes_qty,
			COALESCE(SUM(CASE WHEN le.side = 'NO'  THEN le.quantity ELSE 0 END), 0)::TEXT AS no_qty,
			COALESCE(SUM(le.cost), 0)::TEXT AS cost_basis,
			m.price_yes::TEXT AS price_yes
		 FROM ledger_entries le
		 JOIN markets m ON m.id = le.market_id
		 WHERE le.user_id = $1
		 GROUP BY le.market_id, m.contract_id, m.h3_cell_id, m.price_yes`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	one := decimal.NewFromInt(1)
	var positions []model.Position

	for rows.Next() {
		var p model.Position
		var yesQtyS, noQtyS, costBasisS, priceYesS string

		if err := rows.Scan(&p.MarketID, &p.ContractID, &p.H3CellID,
			&yesQtyS, &noQtyS, &costBasisS, &priceYesS); err != nil {
			return nil, err
		}

		p.UserID = userID
		p.YesQty, _ = decimal.NewFromString(yesQtyS)
		p.NoQty, _ = decimal.NewFromString(noQtyS)
		p.CostBasis, _ = decimal.NewFromString(costBasisS)
		priceYes, _ := decimal.NewFromString(priceYesS)
		priceNo := one.Sub(priceYes)

		p.NetQty = p.YesQty.Sub(p.NoQty)
		p.CurrentValue = priceYes.Mul(p.YesQty).Add(priceNo.Mul(p.NoQty))
		p.UnrealizedPnL = p.CurrentValue.Sub(p.CostBasis)

		positions = append(positions, p)
	}

	return positions, rows.Err()
}

func (s *PostgresStore) GetUserCellExposures(ctx context.Context, userID string) (map[string]decimal.Decimal, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT m.h3_cell_id,
		        COALESCE(SUM(CASE WHEN le.side = 'YES' THEN le.quantity
		                          WHEN le.side = 'NO'  THEN -le.quantity
		                          ELSE 0 END), 0)::TEXT AS net_exposure
		 FROM ledger_entries le
		 JOIN markets m ON m.id = le.market_id
		 WHERE le.user_id = $1
		 GROUP BY m.h3_cell_id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	exposures := make(map[string]decimal.Decimal)
	for rows.Next() {
		var cellID, expStr string
		if err := rows.Scan(&cellID, &expStr); err != nil {
			return nil, err
		}
		exp, _ := decimal.NewFromString(expStr)
		exposures[cellID] = exp
	}

	return exposures, rows.Err()
}

// scanLedgerEntries reads pgx rows into LedgerEntry slices.
type pgxRows interface {
	Next() bool
	Scan(dest ...interface{}) error
	Err() error
}

func scanLedgerEntries(rows pgxRows) ([]model.LedgerEntry, error) {
	var entries []model.LedgerEntry
	for rows.Next() {
		var e model.LedgerEntry
		var qtyS, priceS, costS string

		if err := rows.Scan(&e.ID, &e.UserID, &e.MarketID, &e.ContractID, &e.Side,
			&qtyS, &priceS, &costS, &e.Timestamp); err != nil {
			return nil, err
		}

		e.Quantity, _ = decimal.NewFromString(qtyS)
		e.Price, _ = decimal.NewFromString(priceS)
		e.Cost, _ = decimal.NewFromString(costS)

		entries = append(entries, e)
	}
	return entries, nil
}

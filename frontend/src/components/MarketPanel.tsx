import { useState, useMemo, useEffect, useCallback } from "react";
import type { Market, LedgerEntry, TradeResponse } from "../types";
import {
  parseTicker,
  contractTypeLabel,
  formatThreshold,
  formatExpiry,
} from "../types";
import PriceChart from "./PriceChart";
import TradeTicket from "./TradeTicket";
import { api } from "../api/client";

interface MarketPanelProps {
  markets: Market[];
  selectedCell: string | null;
  onTradeComplete: (res: TradeResponse) => void;
}

export default function MarketPanel({
  markets,
  selectedCell,
  onTradeComplete,
}: MarketPanelProps) {
  const [tradingMarket, setTradingMarket] = useState<Market | null>(null);
  const [histories, setHistories] = useState<Record<string, LedgerEntry[]>>({});

  // Filter markets for the selected H3 cell.
  const cellMarkets = useMemo(
    () =>
      selectedCell
        ? markets.filter((m) => m.h3_cell_id === selectedCell)
        : [],
    [markets, selectedCell]
  );

  // Fetch trade history for visible markets.
  useEffect(() => {
    if (cellMarkets.length === 0) return;
    let cancelled = false;

    async function fetchHistories() {
      for (const m of cellMarkets) {
        if (histories[m.id]) continue;
        try {
          const entries = await api.getMarketHistory(m.id);
          if (!cancelled) {
            setHistories((prev) => ({ ...prev, [m.id]: entries }));
          }
        } catch {
          // Non-critical; chart will show flat line.
        }
      }
    }

    fetchHistories();
    return () => {
      cancelled = true;
    };
  }, [cellMarkets, histories]);

  const handleTradeComplete = useCallback(
    (res: TradeResponse) => {
      setTradingMarket(null);
      onTradeComplete(res);
    },
    [onTradeComplete]
  );

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!selectedCell) {
    return (
      <aside className="market-panel">
        <div className="panel-empty">
          <div className="empty-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <path
                d="M24 4L42.5 14V34L24 44L5.5 34V14L24 4Z"
                stroke="var(--text-muted)"
                strokeWidth="1.5"
                fill="none"
              />
              <circle cx="24" cy="24" r="4" fill="var(--text-muted)" opacity="0.4" />
            </svg>
          </div>
          <p className="empty-title">Select a Cell</p>
          <p className="empty-subtitle">
            Click a hexagon on the map to view markets and trade weather
            derivatives.
          </p>
        </div>
      </aside>
    );
  }

  // ── Trade ticket mode ─────────────────────────────────────────────────────
  if (tradingMarket) {
    return (
      <aside className="market-panel">
        <TradeTicket
          market={tradingMarket}
          onClose={() => setTradingMarket(null)}
          onTradeComplete={handleTradeComplete}
        />
      </aside>
    );
  }

  // ── Market list ───────────────────────────────────────────────────────────
  return (
    <aside className="market-panel">
      <div className="panel-header">
        <h2 className="cell-id">
          <span className="cell-icon">⬡</span>
          {selectedCell.slice(0, 9)}...
        </h2>
        <span className="market-count">
          {cellMarkets.length} market{cellMarkets.length !== 1 ? "s" : ""}
        </span>
      </div>

      {cellMarkets.length === 0 && (
        <div className="no-markets">
          <p>No active markets for this cell.</p>
        </div>
      )}

      {cellMarkets.map((market) => {
        const parsed = parseTicker(market.contract_id);
        const priceYes = parseFloat(market.price_yes) || 0.5;
        const priceNo = parseFloat(market.price_no) || 0.5;
        const history = histories[market.id] || [];

        return (
          <div key={market.id} className="market-card">
            {/* Card header */}
            <div className="card-header">
              <h3 className="card-title">
                {parsed
                  ? `${contractTypeLabel(parsed.type)} ${formatThreshold(
                      parsed.threshold
                    )}`
                  : market.contract_id}
              </h3>
              {parsed && (
                <span className="card-expiry">
                  {formatExpiry(parsed.expiryDate)}
                </span>
              )}
            </div>

            {/* Price display */}
            <div className="market-prices">
              <div className="price-side yes-side">
                <div className="price-label">YES</div>
                <div className="price-amount">
                  {(priceYes * 100).toFixed(1)}
                  <span className="price-unit">%</span>
                </div>
                <div
                  className="price-bar"
                  style={{
                    width: `${priceYes * 100}%`,
                    background: "var(--yes)",
                  }}
                />
              </div>
              <div className="price-side no-side">
                <div className="price-label">NO</div>
                <div className="price-amount">
                  {(priceNo * 100).toFixed(1)}
                  <span className="price-unit">%</span>
                </div>
                <div
                  className="price-bar"
                  style={{
                    width: `${priceNo * 100}%`,
                    background: "var(--no)",
                  }}
                />
              </div>
            </div>

            {/* 24h price chart */}
            <PriceChart history={history} currentPrice={priceYes} />

            {/* Contract details */}
            <div className="card-details">
              <span className="detail-item">
                Liquidity: {parseFloat(market.b).toFixed(0)}
              </span>
              <span className="detail-item">
                Status: {market.status}
              </span>
            </div>

            {/* Trade button */}
            <button
              className="trade-btn"
              onClick={() => setTradingMarket(market)}
            >
              Trade
            </button>
          </div>
        );
      })}
    </aside>
  );
}

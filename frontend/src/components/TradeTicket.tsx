import { useState, useMemo, useCallback } from "react";
import { tradeCost, fillPrice } from "../lib/lmsr";
import { api } from "../api/client";
import type { Market, TradeResponse } from "../types";
import {
  parseTicker,
  contractTypeLabel,
  formatThreshold,
  formatExpiry,
} from "../types";

interface TradeTicketProps {
  market: Market;
  onClose: () => void;
  onTradeComplete: (res: TradeResponse) => void;
}

const DEMO_USER = "demo-user";

export default function TradeTicket({
  market,
  onClose,
  onTradeComplete,
}: TradeTicketProps) {
  const [side, setSide] = useState<"YES" | "NO">("YES");
  const [quantity, setQuantity] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TradeResponse | null>(null);

  const parsed = useMemo(() => parseTicker(market.contract_id), [market.contract_id]);

  // LMSR cost estimation (client-side preview).
  const estimate = useMemo(() => {
    const qYes = parseFloat(market.q_yes) || 0;
    const qNo = parseFloat(market.q_no) || 0;
    const b = parseFloat(market.b) || 100;

    const estCost = tradeCost(qYes, qNo, b, quantity, side);
    const estFillPrice = fillPrice(qYes, qNo, b, quantity, side);

    return {
      cost: estCost,
      fillPrice: estFillPrice,
    };
  }, [market, quantity, side]);

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.executeTrade({
        user_id: DEMO_USER,
        contract_id: market.contract_id,
        side,
        quantity: String(quantity),
      });
      setResult(res);
      onTradeComplete(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Trade failed");
    } finally {
      setSubmitting(false);
    }
  }, [market.contract_id, side, quantity, onTradeComplete]);

  const priceYes = parseFloat(market.price_yes) || 0.5;
  const priceNo = parseFloat(market.price_no) || 0.5;

  if (result) {
    return (
      <div className="trade-ticket">
        <div className="ticket-header">
          <h3>Trade Confirmed</h3>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="trade-result">
          <div className="result-row">
            <span className="result-label">Side</span>
            <span className={`result-value side-${result.side.toLowerCase()}`}>
              {result.side}
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Quantity</span>
            <span className="result-value">{result.quantity} shares</span>
          </div>
          <div className="result-row">
            <span className="result-label">Fill Price</span>
            <span className="result-value">
              {(parseFloat(result.fill_price) * 100).toFixed(2)}%
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Total Cost</span>
            <span className="result-value">
              ${parseFloat(result.cost).toFixed(4)}
            </span>
          </div>
          <button className="trade-btn" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="trade-ticket">
      <div className="ticket-header">
        <h3>Trade Ticket</h3>
        <button className="close-btn" onClick={onClose}>
          &times;
        </button>
      </div>

      {/* Contract info */}
      {parsed && (
        <div className="contract-spec">
          <div className="spec-row">
            <span className="spec-label">Contract</span>
            <span className="spec-value">{contractTypeLabel(parsed.type)}</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Threshold</span>
            <span className="spec-value">{formatThreshold(parsed.threshold)}</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Expiry</span>
            <span className="spec-value">{formatExpiry(parsed.expiryDate)}</span>
          </div>
          <div className="spec-row">
            <span className="spec-label">Settlement</span>
            <span className="spec-value">NOAA ASOS/AWOS</span>
          </div>
        </div>
      )}

      {/* Current prices */}
      <div className="current-prices">
        <div className="price-block yes-block">
          <div className="price-label">YES</div>
          <div className="price-value">{(priceYes * 100).toFixed(1)}%</div>
        </div>
        <div className="price-block no-block">
          <div className="price-label">NO</div>
          <div className="price-value">{(priceNo * 100).toFixed(1)}%</div>
        </div>
      </div>

      {/* Side selector */}
      <div className="side-selector">
        <button
          className={`side-btn side-yes ${side === "YES" ? "active" : ""}`}
          onClick={() => setSide("YES")}
        >
          Buy YES
        </button>
        <button
          className={`side-btn side-no ${side === "NO" ? "active" : ""}`}
          onClick={() => setSide("NO")}
        >
          Buy NO
        </button>
      </div>

      {/* Quantity selector */}
      <div className="quantity-selector">
        <label className="qty-label">Quantity (shares)</label>
        <div className="qty-controls">
          <button
            className="qty-btn"
            onClick={() => setQuantity(Math.max(1, quantity - 5))}
          >
            -5
          </button>
          <button
            className="qty-btn"
            onClick={() => setQuantity(Math.max(1, quantity - 1))}
          >
            -1
          </button>
          <input
            type="number"
            className="qty-input"
            value={quantity}
            min={1}
            max={500}
            onChange={(e) =>
              setQuantity(Math.max(1, parseInt(e.target.value) || 1))
            }
          />
          <button
            className="qty-btn"
            onClick={() => setQuantity(Math.min(500, quantity + 1))}
          >
            +1
          </button>
          <button
            className="qty-btn"
            onClick={() => setQuantity(Math.min(500, quantity + 5))}
          >
            +5
          </button>
        </div>
      </div>

      {/* Cost estimate */}
      <div className="cost-estimate">
        <div className="estimate-row">
          <span>Avg Fill Price</span>
          <span>{(estimate.fillPrice * 100).toFixed(2)}%</span>
        </div>
        <div className="estimate-row total">
          <span>Estimated Cost</span>
          <span>${estimate.cost.toFixed(4)}</span>
        </div>
      </div>

      {error && <div className="trade-error">{error}</div>}

      <button
        className={`trade-btn confirm-btn ${
          side === "YES" ? "btn-yes" : "btn-no"
        }`}
        onClick={handleSubmit}
        disabled={submitting}
      >
        {submitting
          ? "Submitting..."
          : `Buy ${quantity} ${side} @ ${(estimate.fillPrice * 100).toFixed(1)}%`}
      </button>
    </div>
  );
}

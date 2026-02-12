import { useState, useMemo, useCallback } from "react";
import { latLngToCell, gridDisk, cellToLatLng } from "h3-js";
import { api } from "../api/client";
import { tradeCost } from "../lib/lmsr";
import type { Market } from "../types";
import {
  parseTicker,
  contractTypeLabel,
  formatThreshold,
} from "../types";

interface HedgingToolProps {
  markets: Market[];
  mapboxToken: string;
  onHighlightCells: (cells: string[]) => void;
  onClose: () => void;
}

interface HedgeSuggestion {
  market: Market;
  h3Cell: string;
  distance: number; // Ring distance from center.
  estimatedCost: number;
  label: string;
}

const H3_RESOLUTION = 7;

/**
 * HedgingTool: enter an address → geocode to H3 cells → suggest a basket
 * of 3–5 contracts covering the area with estimated costs.
 */
export default function HedgingTool({
  markets,
  mapboxToken,
  onHighlightCells,
  onClose,
}: HedgingToolProps) {
  const [address, setAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [geocodeResult, setGeocodeResult] = useState<{
    placeName: string;
    center: [number, number];
    centerCell: string;
  } | null>(null);
  const [suggestions, setSuggestions] = useState<HedgeSuggestion[]>([]);

  // Index markets by H3 cell for fast lookup.
  const marketsByCell = useMemo(() => {
    const map = new Map<string, Market[]>();
    for (const m of markets) {
      if (!m.h3_cell_id) continue;
      const existing = map.get(m.h3_cell_id);
      if (existing) {
        existing.push(m);
      } else {
        map.set(m.h3_cell_id, [m]);
      }
    }
    return map;
  }, [markets]);

  const handleGeocode = useCallback(async () => {
    if (!address.trim()) return;
    setLoading(true);
    setError(null);
    setSuggestions([]);

    try {
      const result = await api.geocode(address, mapboxToken);
      if (!result) {
        setError("Address not found. Try a more specific location.");
        setLoading(false);
        return;
      }

      const [lng, lat] = result.center;
      const centerCell = latLngToCell(lat, lng, H3_RESOLUTION);

      setGeocodeResult({
        placeName: result.placeName,
        center: result.center,
        centerCell,
      });

      // Get disk of cells around the center (k=2 gives ~19 cells).
      const disk = gridDisk(centerCell, 2);
      onHighlightCells(disk);

      // Find markets in these cells.
      const found: HedgeSuggestion[] = [];
      for (const cell of disk) {
        const cellMarkets = marketsByCell.get(cell);
        if (!cellMarkets) continue;

        // Compute ring distance from center.
        const [centerLat, centerLng] = cellToLatLng(centerCell);
        const [cellLat, cellLng] = cellToLatLng(cell);
        const distance = Math.sqrt(
          (centerLat - cellLat) ** 2 + (centerLng - cellLng) ** 2
        );

        for (const market of cellMarkets) {
          const parsed = parseTicker(market.contract_id);
          // Prefer precipitation markets for hedging demo.
          const qYes = parseFloat(market.q_yes) || 0;
          const qNo = parseFloat(market.q_no) || 0;
          const b = parseFloat(market.b) || 100;
          const qty = 10; // Suggest 10-share hedge.
          const estCost = tradeCost(qYes, qNo, b, qty, "YES");

          found.push({
            market,
            h3Cell: cell,
            distance,
            estimatedCost: estCost,
            label: parsed
              ? `${contractTypeLabel(parsed.type)} ${formatThreshold(parsed.threshold)}`
              : market.contract_id,
          });
        }
      }

      // Sort by distance from center, take top 5.
      found.sort((a, b) => a.distance - b.distance);
      setSuggestions(found.slice(0, 5));

      if (found.length === 0) {
        setError(
          "No active markets found near this location. Markets exist in select US metro areas."
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Geocoding failed");
    } finally {
      setLoading(false);
    }
  }, [address, mapboxToken, marketsByCell, onHighlightCells]);

  const totalCost = useMemo(
    () => suggestions.reduce((sum, s) => sum + s.estimatedCost, 0),
    [suggestions]
  );

  return (
    <div className="hedging-tool">
      <div className="hedge-header">
        <h2>Hedging Tool</h2>
        <button className="close-btn" onClick={onClose}>
          &times;
        </button>
      </div>

      <p className="hedge-description">
        Enter an address to find weather derivative contracts that cover your
        area. We'll suggest a basket of contracts to hedge against severe weather.
      </p>

      {/* Address input */}
      <div className="hedge-input-row">
        <input
          type="text"
          className="hedge-input"
          placeholder="Enter address, city, or ZIP code..."
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleGeocode()}
        />
        <button
          className="hedge-search-btn"
          onClick={handleGeocode}
          disabled={loading || !address.trim()}
        >
          {loading ? "..." : "Search"}
        </button>
      </div>

      {error && <div className="hedge-error">{error}</div>}

      {/* Geocode result */}
      {geocodeResult && (
        <div className="hedge-location">
          <div className="location-name">{geocodeResult.placeName}</div>
          <div className="location-cell">
            H3 Cell: {geocodeResult.centerCell.slice(0, 9)}...
          </div>
        </div>
      )}

      {/* Suggested contracts */}
      {suggestions.length > 0 && (
        <div className="hedge-suggestions">
          <h3 className="suggestions-title">
            Suggested Hedge ({suggestions.length} contracts, 10 shares each)
          </h3>

          {suggestions.map((s, i) => {
            const priceYes = parseFloat(s.market.price_yes) || 0.5;
            return (
              <div key={`${s.market.id}-${i}`} className="hedge-contract">
                <div className="hedge-contract-header">
                  <span className="hedge-contract-label">{s.label}</span>
                  <span className="hedge-contract-cell">
                    {s.h3Cell.slice(0, 7)}...
                  </span>
                </div>
                <div className="hedge-contract-details">
                  <span>
                    Price: <strong>{(priceYes * 100).toFixed(1)}%</strong>
                  </span>
                  <span>
                    Cost: <strong>${s.estimatedCost.toFixed(2)}</strong>
                  </span>
                </div>
              </div>
            );
          })}

          {/* Total */}
          <div className="hedge-total">
            <span className="total-label">Total Estimated Hedge Cost</span>
            <span className="total-value">${totalCost.toFixed(2)}</span>
          </div>

          <p className="hedge-note">
            This basket covers{" "}
            {new Set(suggestions.map((s) => s.h3Cell)).size} H3 cells around
            your location. Each contract settles against official NOAA ASOS/AWOS
            observations.
          </p>
        </div>
      )}
    </div>
  );
}

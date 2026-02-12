import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { Market } from "../types";

// Demo markets used when the backend is unavailable.
// Covers major US metro areas with H3 resolution-4 cells (~22 km edge, visible at zoom 4).
const DEMO_MARKETS: Market[] = [
  // ── New York City ─────────────────────────────────────────────────────────
  {
    id: "demo-1",
    contract_id: "ATMX-842a107-PRECIP-25MM-20260301",
    h3_cell_id: "842a107ffffffff",
    q_yes: "15", q_no: "5", b: "100",
    price_yes: "0.65", price_no: "0.35",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-2",
    contract_id: "ATMX-842a107-WIND-60MPH-20260301",
    h3_cell_id: "842a107ffffffff",
    q_yes: "3", q_no: "12", b: "100",
    price_yes: "0.28", price_no: "0.72",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Chicago ───────────────────────────────────────────────────────────────
  {
    id: "demo-3",
    contract_id: "ATMX-842664d-PRECIP-25MM-20260301",
    h3_cell_id: "842664dffffffff",
    q_yes: "20", q_no: "8", b: "100",
    price_yes: "0.72", price_no: "0.28",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-4",
    contract_id: "ATMX-842664d-TEMP-35C-20260301",
    h3_cell_id: "842664dffffffff",
    q_yes: "1", q_no: "18", b: "100",
    price_yes: "0.15", price_no: "0.85",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Houston ───────────────────────────────────────────────────────────────
  {
    id: "demo-5",
    contract_id: "ATMX-84446cb-PRECIP-50MM-20260301",
    h3_cell_id: "84446cbffffffff",
    q_yes: "30", q_no: "2", b: "100",
    price_yes: "0.85", price_no: "0.15",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Los Angeles ───────────────────────────────────────────────────────────
  {
    id: "demo-6",
    contract_id: "ATMX-8429a1d-WIND-60MPH-20260301",
    h3_cell_id: "8429a1dffffffff",
    q_yes: "8", q_no: "10", b: "100",
    price_yes: "0.45", price_no: "0.55",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Miami ─────────────────────────────────────────────────────────────────
  {
    id: "demo-7",
    contract_id: "ATMX-8444a11-PRECIP-25MM-20260301",
    h3_cell_id: "8444a11ffffffff",
    q_yes: "6", q_no: "14", b: "100",
    price_yes: "0.32", price_no: "0.68",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Denver ────────────────────────────────────────────────────────────────
  {
    id: "demo-8",
    contract_id: "ATMX-84268cd-SNOW-15IN-20260301",
    h3_cell_id: "84268cdffffffff",
    q_yes: "10", q_no: "10", b: "100",
    price_yes: "0.50", price_no: "0.50",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Boston ────────────────────────────────────────────────────────────────
  {
    id: "demo-9",
    contract_id: "ATMX-842a307-SNOW-15IN-20260301",
    h3_cell_id: "842a307ffffffff",
    q_yes: "18", q_no: "6", b: "100",
    price_yes: "0.70", price_no: "0.30",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Atlanta ───────────────────────────────────────────────────────────────
  {
    id: "demo-10",
    contract_id: "ATMX-8444c1b-PRECIP-25MM-20260301",
    h3_cell_id: "8444c1bffffffff",
    q_yes: "25", q_no: "4", b: "100",
    price_yes: "0.80", price_no: "0.20",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Dallas ────────────────────────────────────────────────────────────────
  {
    id: "demo-11",
    contract_id: "ATMX-8426cb9-WIND-60MPH-20260301",
    h3_cell_id: "8426cb9ffffffff",
    q_yes: "12", q_no: "7", b: "100",
    price_yes: "0.62", price_no: "0.38",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Washington DC ─────────────────────────────────────────────────────────
  {
    id: "demo-12",
    contract_id: "ATMX-842aa85-PRECIP-25MM-20260301",
    h3_cell_id: "842aa85ffffffff",
    q_yes: "14", q_no: "9", b: "100",
    price_yes: "0.58", price_no: "0.42",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Minneapolis ───────────────────────────────────────────────────────────
  {
    id: "demo-13",
    contract_id: "ATMX-8427527-SNOW-15IN-20260301",
    h3_cell_id: "8427527ffffffff",
    q_yes: "22", q_no: "3", b: "100",
    price_yes: "0.78", price_no: "0.22",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Nashville ─────────────────────────────────────────────────────────────
  {
    id: "demo-14",
    contract_id: "ATMX-84264d1-PRECIP-50MM-20260301",
    h3_cell_id: "84264d1ffffffff",
    q_yes: "16", q_no: "8", b: "100",
    price_yes: "0.67", price_no: "0.33",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Seattle ───────────────────────────────────────────────────────────────
  {
    id: "demo-15",
    contract_id: "ATMX-8428d55-PRECIP-25MM-20260301",
    h3_cell_id: "8428d55ffffffff",
    q_yes: "20", q_no: "5", b: "100",
    price_yes: "0.75", price_no: "0.25",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Milwaukee ──────────────────────────────────────────────────────────────
  {
    id: "demo-16",
    contract_id: "ATMX-84275d3-PRECIP-25MM-20260301",
    h3_cell_id: "84275d3ffffffff",
    q_yes: "17", q_no: "7", b: "100",
    price_yes: "0.68", price_no: "0.32",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-17",
    contract_id: "ATMX-84275d3-SNOW-15IN-20260301",
    h3_cell_id: "84275d3ffffffff",
    q_yes: "22", q_no: "4", b: "100",
    price_yes: "0.78", price_no: "0.22",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Brookfield / Waukesha WI (adjacent cell to Milwaukee) ────────────────
  {
    id: "demo-18",
    contract_id: "ATMX-84275d7-WIND-60MPH-20260301",
    h3_cell_id: "84275d7ffffffff",
    q_yes: "5", q_no: "15", b: "100",
    price_yes: "0.25", price_no: "0.75",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Madison WI ─────────────────────────────────────────────────────────────
  {
    id: "demo-19",
    contract_id: "ATMX-8427581-PRECIP-50MM-20260301",
    h3_cell_id: "8427581ffffffff",
    q_yes: "12", q_no: "8", b: "100",
    price_yes: "0.60", price_no: "0.40",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Green Bay WI ───────────────────────────────────────────────────────────
  {
    id: "demo-20",
    contract_id: "ATMX-8427435-SNOW-15IN-20260301",
    h3_cell_id: "8427435ffffffff",
    q_yes: "24", q_no: "3", b: "100",
    price_yes: "0.82", price_no: "0.18",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Detroit ────────────────────────────────────────────────────────────────
  {
    id: "demo-21",
    contract_id: "ATMX-842ab2d-PRECIP-25MM-20260301",
    h3_cell_id: "842ab2dffffffff",
    q_yes: "15", q_no: "10", b: "100",
    price_yes: "0.60", price_no: "0.40",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Philadelphia ───────────────────────────────────────────────────────────
  {
    id: "demo-22",
    contract_id: "ATMX-842a135-PRECIP-25MM-20260301",
    h3_cell_id: "842a135ffffffff",
    q_yes: "13", q_no: "9", b: "100",
    price_yes: "0.57", price_no: "0.43",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── San Francisco ──────────────────────────────────────────────────────────
  {
    id: "demo-23",
    contract_id: "ATMX-8428309-WIND-60MPH-20260301",
    h3_cell_id: "8428309ffffffff",
    q_yes: "9", q_no: "11", b: "100",
    price_yes: "0.42", price_no: "0.58",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Phoenix ────────────────────────────────────────────────────────────────
  {
    id: "demo-24",
    contract_id: "ATMX-8429b6d-TEMP-35C-20260301",
    h3_cell_id: "8429b6dffffffff",
    q_yes: "28", q_no: "2", b: "100",
    price_yes: "0.88", price_no: "0.12",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Portland ───────────────────────────────────────────────────────────────
  {
    id: "demo-25",
    contract_id: "ATMX-8428f01-PRECIP-25MM-20260301",
    h3_cell_id: "8428f01ffffffff",
    q_yes: "19", q_no: "6", b: "100",
    price_yes: "0.73", price_no: "0.27",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── St. Louis ──────────────────────────────────────────────────────────────
  {
    id: "demo-26",
    contract_id: "ATMX-842640d-PRECIP-50MM-20260301",
    h3_cell_id: "842640dffffffff",
    q_yes: "16", q_no: "7", b: "100",
    price_yes: "0.66", price_no: "0.34",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  // ── Kansas City ────────────────────────────────────────────────────────────
  {
    id: "demo-27",
    contract_id: "ATMX-8426561-WIND-60MPH-20260301",
    h3_cell_id: "8426561ffffffff",
    q_yes: "11", q_no: "9", b: "100",
    price_yes: "0.55", price_no: "0.45",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
];

/**
 * Normalize a potentially truncated H3 cell ID to a full 15-character index.
 * The backend stores truncated IDs (e.g. "872a1070b") from ticker parsing;
 * h3-js needs the full form (e.g. "872a1070bffffff").
 */
function normalizeH3Cell(cellId: string): string {
  if (cellId.length >= 15) return cellId;
  return cellId.padEnd(15, "f");
}

/** Normalize h3_cell_id on all markets so downstream components get full IDs. */
function normalizeMarkets(markets: Market[]): Market[] {
  return markets.map((m) => ({
    ...m,
    h3_cell_id: m.h3_cell_id ? normalizeH3Cell(m.h3_cell_id) : m.h3_cell_id,
  }));
}

/**
 * Hook for fetching and managing market data.
 * Falls back to demo data when the backend is unreachable.
 */
export function useMarkets() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState(false);

  const fetchMarkets = useCallback(async () => {
    try {
      const data = await api.listMarkets();
      setMarkets(normalizeMarkets(data.length > 0 ? data : DEMO_MARKETS));
      setIsDemo(data.length === 0);
      setError(null);
    } catch {
      // Backend unavailable — use demo data.
      if (markets.length === 0) {
        setMarkets(normalizeMarkets(DEMO_MARKETS));
        setIsDemo(true);
      }
      setError("Backend unavailable — showing demo data");
    } finally {
      setLoading(false);
    }
  }, [markets.length]);

  useEffect(() => {
    fetchMarkets();
    // Poll every 15s as backup to WebSocket.
    const interval = setInterval(fetchMarkets, 15000);
    return () => clearInterval(interval);
  }, [fetchMarkets]);

  /** Update a single market's price (called from WebSocket handler). */
  const updateMarketPrice = useCallback(
    (marketId: string, priceYes: string, priceNo: string) => {
      setMarkets((prev) =>
        prev.map((m) =>
          m.id === marketId ? { ...m, price_yes: priceYes, price_no: priceNo } : m
        )
      );
    },
    []
  );

  return { markets, loading, error, isDemo, refetch: fetchMarkets, updateMarketPrice };
}

import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { Market } from "../types";

// Demo markets used when the backend is unavailable.
// Covers major US metro areas with realistic H3 resolution-7 cells.
const DEMO_MARKETS: Market[] = [
  {
    id: "demo-1",
    contract_id: "ATMX-872a1070b-PRECIP-25MM-20260301",
    h3_cell_id: "872a1070bffffff",
    q_yes: "15", q_no: "5", b: "100",
    price_yes: "0.65", price_no: "0.35",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-2",
    contract_id: "ATMX-872a1070b-WIND-60MPH-20260301",
    h3_cell_id: "872a1070bffffff",
    q_yes: "3", q_no: "12", b: "100",
    price_yes: "0.28", price_no: "0.72",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-3",
    contract_id: "ATMX-8726d9521-PRECIP-25MM-20260301",
    h3_cell_id: "8726d9521ffffff",
    q_yes: "20", q_no: "8", b: "100",
    price_yes: "0.72", price_no: "0.28",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-4",
    contract_id: "ATMX-8726d9521-TEMP-35C-20260301",
    h3_cell_id: "8726d9521ffffff",
    q_yes: "1", q_no: "18", b: "100",
    price_yes: "0.15", price_no: "0.85",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-5",
    contract_id: "ATMX-87264ac53-PRECIP-50MM-20260301",
    h3_cell_id: "87264ac53ffffff",
    q_yes: "30", q_no: "2", b: "100",
    price_yes: "0.85", price_no: "0.15",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-6",
    contract_id: "ATMX-87283472d-WIND-60MPH-20260301",
    h3_cell_id: "87283472dffffff",
    q_yes: "8", q_no: "10", b: "100",
    price_yes: "0.45", price_no: "0.55",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-7",
    contract_id: "ATMX-8729a069b-PRECIP-25MM-20260301",
    h3_cell_id: "8729a069bffffff",
    q_yes: "6", q_no: "14", b: "100",
    price_yes: "0.32", price_no: "0.68",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-8",
    contract_id: "ATMX-8726928c3-PRECIP-25MM-20260301",
    h3_cell_id: "8726928c3ffffff",
    q_yes: "10", q_no: "10", b: "100",
    price_yes: "0.50", price_no: "0.50",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-9",
    contract_id: "ATMX-872a100e9-SNOW-15IN-20260301",
    h3_cell_id: "872a100e9ffffff",
    q_yes: "18", q_no: "6", b: "100",
    price_yes: "0.70", price_no: "0.30",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
  {
    id: "demo-10",
    contract_id: "ATMX-87264a5a7-PRECIP-25MM-20260301",
    h3_cell_id: "87264a5a7ffffff",
    q_yes: "25", q_no: "4", b: "100",
    price_yes: "0.80", price_no: "0.20",
    status: "open", created_at: "2026-02-10T00:00:00Z",
  },
];

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
      setMarkets(data.length > 0 ? data : DEMO_MARKETS);
      setIsDemo(data.length === 0);
      setError(null);
    } catch {
      // Backend unavailable — use demo data.
      if (markets.length === 0) {
        setMarkets(DEMO_MARKETS);
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

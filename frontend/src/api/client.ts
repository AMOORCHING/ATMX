/**
 * HTTP API client for the market-engine Go backend.
 * All endpoints are proxied through Vite during development (/api → localhost:8080).
 */

import type { Market, TradeRequest, TradeResponse, Portfolio, LedgerEntry } from "../types";

const API_BASE = "/api/v1";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export const api = {
  /** List all markets, optionally filtered by H3 cell. */
  listMarkets(h3Cell?: string): Promise<Market[]> {
    const params = h3Cell ? `?h3_cell=${encodeURIComponent(h3Cell)}` : "";
    return fetchJSON<Market[]>(`${API_BASE}/markets${params}`);
  },

  /** Get a single market by ID. */
  getMarket(marketID: string): Promise<Market> {
    return fetchJSON<Market>(`${API_BASE}/markets/${marketID}`);
  },

  /** Get current YES/NO prices for a market. */
  getPrice(marketID: string): Promise<{ yes: string; no: string }> {
    return fetchJSON(`${API_BASE}/markets/${marketID}/price`);
  },

  /** Get trade history (ledger entries) for a market. */
  getMarketHistory(marketID: string): Promise<LedgerEntry[]> {
    return fetchJSON<LedgerEntry[]>(`${API_BASE}/markets/${marketID}/history`);
  },

  /** Create a new market for a contract ticker. */
  createMarket(contractID: string, b?: number): Promise<Market> {
    return fetchJSON<Market>(`${API_BASE}/markets`, {
      method: "POST",
      body: JSON.stringify({ contract_id: contractID, b: b || 100 }),
    });
  },

  /** Execute a trade against the LMSR market maker. */
  executeTrade(req: TradeRequest): Promise<TradeResponse> {
    return fetchJSON<TradeResponse>(`${API_BASE}/trade`, {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /** Get portfolio (positions, P&L, exposure) for a user. */
  getPortfolio(userID: string): Promise<Portfolio> {
    return fetchJSON<Portfolio>(`${API_BASE}/portfolio/${userID}`);
  },

  /** Geocode an address via Mapbox API → [lng, lat]. */
  async geocode(
    address: string,
    mapboxToken: string
  ): Promise<{ center: [number, number]; placeName: string } | null> {
    const encoded = encodeURIComponent(address);
    const res = await fetch(
      `https://api.mapbox.com/geocoding/v5/mapbox.places/${encoded}.json?access_token=${mapboxToken}&limit=1`
    );
    const data = await res.json();
    if (data.features?.length > 0) {
      const feature = data.features[0];
      return {
        center: feature.center as [number, number],
        placeName: feature.place_name,
      };
    }
    return null;
  },
};

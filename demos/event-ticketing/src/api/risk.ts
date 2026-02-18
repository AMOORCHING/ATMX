import { latLngToCell } from "h3-js";
import type {
  RiskPriceResponse,
  ContractCreateRequest,
  ContractCreateResponse,
  ContractStatusResponse,
  SettlementRule,
} from "../types";

const API_KEY = import.meta.env.VITE_ATMX_API_KEY || "";
const H3_RESOLUTION = 7;

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;
  return headers;
}

export function venueToH3(lat: number, lng: number): string {
  return latLngToCell(lat, lng, H3_RESOLUTION);
}

// ── Deterministic demo data seeded by H3 cell ─────────────────────────────

function hashSeed(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

const DEMO_PROBABILITIES: Record<string, number> = {
  "nyc-summer-sounds": 0.22,
  "chi-lakefront": 0.18,
  "hou-bayou-beats": 0.35,
  "mia-neon-nights": 0.28,
  "nash-honkytonk": 0.15,
  "sea-emerald": 0.08,
};

function demoSettlementRule(): SettlementRule {
  return {
    version: "v1.3",
    oracle_source: "NOAA_ASOS",
    threshold_mm: 12.7,
    aggregation: "sum",
    min_stations: 1,
    dispute_spread_ratio: 0.2,
  };
}

function buildDemoRiskPrice(
  h3Index: string,
  eventId?: string,
): RiskPriceResponse {
  const seed = hashSeed(h3Index);
  const baseProbability =
    eventId && DEMO_PROBABILITIES[eventId]
      ? DEMO_PROBABILITIES[eventId]
      : 0.1 + seededRandom(seed) * 0.35;

  const spread = 0.03 + seededRandom(seed + 1) * 0.04;
  const premium = Math.round(baseProbability * 12.5 * 100) / 100;

  return {
    h3_index: h3Index,
    risk_type: "precip_heavy",
    risk_probability: baseProbability,
    confidence_interval: [
      Math.max(0, Math.round((baseProbability - spread) * 1000) / 1000),
      Math.min(1, Math.round((baseProbability + spread) * 1000) / 1000),
    ],
    suggested_premium_usd: premium,
    settlement_rule: demoSettlementRule(),
    pricing_model: "ensemble_baseline_v1",
    valid_until: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
  };
}

function buildDemoContract(
  req: ContractCreateRequest,
  premium: number,
): ContractCreateResponse {
  const id = crypto.randomUUID();
  const datePart = req.end_time.slice(0, 10).replace(/-/g, "");
  return {
    contract_id: id,
    h3_index: req.h3_index,
    risk_type: req.risk_type,
    start_time: req.start_time,
    end_time: req.end_time,
    notional_usd: req.notional_usd,
    premium_usd: premium,
    settlement_rule: demoSettlementRule(),
    status: "active",
    created_at: new Date().toISOString(),
    ticker: `ATMX-${req.h3_index.slice(0, 11)}-PRECIP-13MM-${datePart}`,
  };
}

function buildDemoContractStatus(
  contractId: string,
  contract: ContractCreateResponse,
): ContractStatusResponse {
  const endTime = new Date(contract.end_time);
  const now = new Date();

  if (now > endTime) {
    const seed = hashSeed(contractId);
    const triggered = seededRandom(seed + 42) > 0.55;
    return {
      contract_id: contractId,
      status: triggered ? "settled_yes" : "settled_no",
      h3_index: contract.h3_index,
      risk_type: contract.risk_type,
      start_time: contract.start_time,
      end_time: contract.end_time,
      outcome: triggered ? "YES" : "NO",
      observed_value: triggered
        ? 14.2 + seededRandom(seed + 99) * 20
        : 2.1 + seededRandom(seed + 99) * 8,
      settled_at: new Date(endTime.getTime() + 3600_000).toISOString(),
      record_hash: Array.from({ length: 64 }, (_, i) =>
        "0123456789abcdef"[Math.floor(seededRandom(seed + i) * 16)],
      ).join(""),
    };
  }

  return {
    contract_id: contractId,
    status: "active",
    h3_index: contract.h3_index,
    risk_type: contract.risk_type,
    start_time: contract.start_time,
    end_time: contract.end_time,
  };
}

// ── API client with automatic demo fallback ────────────────────────────────

export async function fetchRiskPrice(
  lat: number,
  lng: number,
  startTime: string,
  endTime: string,
  eventId?: string,
): Promise<RiskPriceResponse> {
  const h3Index = venueToH3(lat, lng);

  if (!API_KEY) return buildDemoRiskPrice(h3Index, eventId);

  try {
    const params = new URLSearchParams({
      h3_index: h3Index,
      risk_type: "precip_heavy",
      start_time: startTime,
      end_time: endTime,
    });
    const res = await fetch(`/v1/risk_price?${params}`, {
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return await res.json();
  } catch {
    console.warn("Risk API unavailable — using demo pricing");
    return buildDemoRiskPrice(h3Index, eventId);
  }
}

export async function createContract(
  req: ContractCreateRequest,
  fallbackPremium: number,
): Promise<ContractCreateResponse> {
  if (!API_KEY) return buildDemoContract(req, fallbackPremium);

  try {
    const res = await fetch("/v1/contracts", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return await res.json();
  } catch {
    console.warn("Risk API unavailable — using demo contract");
    return buildDemoContract(req, fallbackPremium);
  }
}

export async function fetchContractStatus(
  contractId: string,
  contract: ContractCreateResponse,
): Promise<ContractStatusResponse> {
  if (!API_KEY) return buildDemoContractStatus(contractId, contract);

  try {
    const res = await fetch(`/v1/contracts/${contractId}/status`, {
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return await res.json();
  } catch {
    console.warn("Risk API unavailable — using demo status");
    return buildDemoContractStatus(contractId, contract);
  }
}

// ── LocalStorage helpers for purchased protections ─────────────────────────

const STORAGE_KEY = "atmx-demo-protections";

export function loadProtections(): import("../types").PurchasedProtection[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveProtection(p: import("../types").PurchasedProtection): void {
  const all = loadProtections();
  all.push(p);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}

export function clearProtections(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export interface EventData {
  id: string;
  name: string;
  tagline: string;
  description: string;
  date: string;
  dateDisplay: string;
  time: string;
  venue: string;
  city: string;
  state: string;
  lat: number;
  lng: number;
  ticketPrice: number;
  genre: string;
  emoji: string;
  gradient: string;
}

export interface SettlementRule {
  version: string;
  oracle_source: string;
  threshold_mm?: number | null;
  threshold_ms?: number | null;
  threshold_c?: number | null;
  threshold_cm?: number | null;
  aggregation: string;
  min_stations: number;
  dispute_spread_ratio: number;
}

export interface RiskPriceResponse {
  h3_index: string;
  risk_type: string;
  risk_probability: number;
  confidence_interval: [number, number];
  suggested_premium_usd: number;
  settlement_rule: SettlementRule;
  pricing_model: string;
  valid_until: string;
}

export interface ContractCreateRequest {
  h3_index: string;
  risk_type: string;
  start_time: string;
  end_time: string;
  notional_usd: number;
}

export interface ContractCreateResponse {
  contract_id: string;
  h3_index: string;
  risk_type: string;
  start_time: string;
  end_time: string;
  notional_usd: number;
  premium_usd: number;
  settlement_rule: SettlementRule;
  status: string;
  created_at: string;
  ticker: string;
}

export interface ContractStatusResponse {
  contract_id: string;
  status: string;
  h3_index: string;
  risk_type: string;
  start_time: string;
  end_time: string;
  outcome?: string | null;
  observed_value?: number | null;
  settled_at?: string | null;
  record_hash?: string | null;
}

export interface PurchasedProtection {
  event: EventData;
  contract: ContractCreateResponse;
  riskPrice: RiskPriceResponse;
  purchasedAt: string;
}

export type RiskLevel = "low" | "moderate" | "high";

export function getRiskLevel(probability: number): RiskLevel {
  if (probability < 0.1) return "low";
  if (probability < 0.3) return "moderate";
  return "high";
}

export function getRiskLabel(level: RiskLevel): string {
  switch (level) {
    case "low":
      return "Low Risk";
    case "moderate":
      return "Moderate Risk";
    case "high":
      return "High Risk";
  }
}

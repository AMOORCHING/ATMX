// TypeScript types matching the Go backend models.
// All decimal values are strings to preserve precision (shopspring/decimal).

export interface Market {
  id: string;
  contract_id: string;
  h3_cell_id: string;
  q_yes: string;
  q_no: string;
  b: string;
  price_yes: string;
  price_no: string;
  status: string; // "open" | "settled"
  created_at: string;
}

export interface TradeRequest {
  user_id: string;
  contract_id: string;
  side: "YES" | "NO";
  quantity: string;
}

export interface TradeResponse {
  trade_id: string;
  user_id: string;
  contract_id: string;
  side: string;
  quantity: string;
  fill_price: string;
  cost: string;
  position: PositionSummary;
}

export interface PositionSummary {
  yes_qty: string;
  no_qty: string;
  cost_basis: string;
  unrealized_pnl: string;
}

export interface LedgerEntry {
  id: string;
  user_id: string;
  market_id: string;
  contract_id: string;
  side: string;
  quantity: string;
  price: string;
  cost: string;
  timestamp: string;
}

export interface Position {
  user_id: string;
  market_id: string;
  contract_id: string;
  h3_cell_id: string;
  yes_qty: string;
  no_qty: string;
  net_qty: string;
  cost_basis: string;
  current_value: string;
  unrealized_pnl: string;
}

export interface Portfolio {
  user_id: string;
  positions: Position[];
  total_pnl: string;
  total_exposure: string;
  margin_utilization: string;
  exposure_by_cell: Record<string, string>;
}

export interface WSMessage {
  type: "trade_executed" | "price_update";
  market_id: string;
  contract_id: string;
  h3_cell_id: string;
  price_yes?: string;
  price_no?: string;
  side?: string;
  quantity?: string;
}

/** Parsed fields from an ATMX contract ticker. */
export interface ParsedContract {
  ticker: string;
  h3CellID: string;
  type: string; // PRECIP, TEMP, WIND, SNOW
  threshold: string;
  expiryDate: string; // YYYYMMDD
}

export interface PricePoint {
  time: string;
  price: number;
}

/** Parses ATMX-{h3cell}-{type}-{threshold}-{YYYYMMDD} into structured data. */
export function parseTicker(ticker: string): ParsedContract | null {
  const match = ticker.match(
    /^ATMX-([0-9a-f]+)-([A-Z]+)-([0-9]+[A-Z]*)-(\d{8})$/
  );
  if (!match) return null;
  return {
    ticker,
    h3CellID: match[1],
    type: match[2],
    threshold: match[3],
    expiryDate: match[4],
  };
}

/** Human-readable label for a contract type. */
export function contractTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    PRECIP: "Precipitation",
    TEMP: "Temperature",
    WIND: "Wind Speed",
    SNOW: "Snowfall",
  };
  return labels[type] || type;
}

/** Human-readable threshold (e.g., "25MM" → "> 25 mm"). */
export function formatThreshold(threshold: string): string {
  const match = threshold.match(/^(\d+)([A-Z]*)$/);
  if (!match) return `> ${threshold}`;
  const value = match[1];
  const unit = match[2]?.toLowerCase() || "";
  const unitMap: Record<string, string> = {
    mm: "mm",
    c: "°C",
    f: "°F",
    mph: "mph",
    kph: "km/h",
    in: "in",
  };
  return `> ${value} ${unitMap[unit] || unit}`;
}

/** Format expiry date string YYYYMMDD → "Mon DD, YYYY". */
export function formatExpiry(dateStr: string): string {
  const y = dateStr.slice(0, 4);
  const m = dateStr.slice(4, 6);
  const d = dateStr.slice(6, 8);
  const date = new Date(`${y}-${m}-${d}`);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

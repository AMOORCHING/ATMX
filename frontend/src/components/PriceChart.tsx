import { useMemo } from "react";
import type { LedgerEntry } from "../types";

interface PriceChartProps {
  history: LedgerEntry[];
  currentPrice: number;
  width?: number;
  height?: number;
}

/**
 * Minimal SVG price chart — no dependencies.
 * Draws a 24h YES price line from trade history.
 */
export default function PriceChart({
  history,
  currentPrice,
  width = 280,
  height = 80,
}: PriceChartProps) {
  const { points, minP, maxP } = useMemo(() => {
    // Build price points from ledger entries.
    const now = Date.now();
    const dayAgo = now - 24 * 60 * 60 * 1000;

    // Start with initial price at 0.5 (market creation default).
    const pts: { t: number; p: number }[] = [{ t: dayAgo, p: 0.5 }];

    // Add trade prices.
    for (const entry of history) {
      const t = new Date(entry.timestamp).getTime();
      if (t >= dayAgo) {
        pts.push({ t, p: parseFloat(entry.price) || 0.5 });
      }
    }

    // End with current price.
    pts.push({ t: now, p: currentPrice });

    let minP = 0;
    let maxP = 1;
    // Add some padding if all values are close.
    const prices = pts.map((pt) => pt.p);
    const actualMin = Math.min(...prices);
    const actualMax = Math.max(...prices);
    if (actualMax - actualMin > 0.1) {
      minP = Math.max(0, actualMin - 0.05);
      maxP = Math.min(1, actualMax + 0.05);
    }

    return { points: pts, minP, maxP };
  }, [history, currentPrice]);

  const padding = { top: 8, right: 8, bottom: 8, left: 8 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const now = Date.now();
  const dayAgo = now - 24 * 60 * 60 * 1000;

  // Scale functions.
  const scaleX = (t: number) =>
    padding.left + ((t - dayAgo) / (now - dayAgo)) * chartW;
  const scaleY = (p: number) =>
    padding.top + (1 - (p - minP) / (maxP - minP || 1)) * chartH;

  // Build SVG path.
  const pathD = points
    .map((pt, i) => {
      const x = scaleX(pt.t);
      const y = scaleY(pt.p);
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  // Area fill path (closed at bottom).
  const areaD = `${pathD} L ${scaleX(now).toFixed(1)} ${(
    padding.top + chartH
  ).toFixed(1)} L ${padding.left.toFixed(1)} ${(padding.top + chartH).toFixed(
    1
  )} Z`;

  // Color based on direction.
  const isUp = currentPrice >= 0.5;
  const color = isUp ? "var(--yes)" : "var(--no)";

  return (
    <div className="price-chart">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {/* 50% baseline */}
        <line
          x1={padding.left}
          y1={scaleY(0.5)}
          x2={padding.left + chartW}
          y2={scaleY(0.5)}
          stroke="var(--border)"
          strokeWidth={1}
          strokeDasharray="4 3"
        />

        {/* Area fill */}
        <path d={areaD} fill={color} opacity={0.12} />

        {/* Price line */}
        <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} />

        {/* Current price dot */}
        <circle
          cx={scaleX(now)}
          cy={scaleY(currentPrice)}
          r={3}
          fill={color}
        />
      </svg>
      <div className="chart-labels">
        <span className="chart-label-time">24h</span>
        <span className="chart-label-price" style={{ color }}>
          {(currentPrice * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

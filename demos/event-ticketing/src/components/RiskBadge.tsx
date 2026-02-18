import { getRiskLevel, getRiskLabel } from "../types";

interface RiskBadgeProps {
  probability: number | null;
  size?: "sm" | "md" | "lg";
}

export default function RiskBadge({ probability, size = "md" }: RiskBadgeProps) {
  if (probability === null) {
    return <span className={`risk-badge risk-badge--loading risk-badge--${size}`}>—</span>;
  }

  const level = getRiskLevel(probability);
  const label = getRiskLabel(level);
  const pct = Math.round(probability * 100);

  return (
    <span
      className={`risk-badge risk-badge--${level} risk-badge--${size}`}
      title={`${label}: ${pct}% chance of heavy precipitation`}
    >
      <span className="risk-badge__icon">
        {level === "low" ? "☀️" : level === "moderate" ? "🌦️" : "⛈️"}
      </span>
      <span className="risk-badge__pct">{pct}%</span>
    </span>
  );
}

import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { loadProtections, clearProtections, fetchContractStatus } from "../api/risk";
import type { PurchasedProtection, ContractStatusResponse } from "../types";
import RadarMap from "../components/RadarMap";

export default function Dashboard() {
  const [protections, setProtections] = useState<PurchasedProtection[]>([]);
  const [statuses, setStatuses] = useState<Record<string, ContractStatusResponse>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setProtections(loadProtections());
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (protections.length === 0) return;
    let cancelled = false;

    async function poll() {
      const results = await Promise.allSettled(
        protections.map(async (p) => {
          const status = await fetchContractStatus(
            p.contract.contract_id,
            p.contract,
          );
          return { id: p.contract.contract_id, status };
        }),
      );

      if (cancelled) return;

      const map: Record<string, ContractStatusResponse> = {};
      for (const r of results) {
        if (r.status === "fulfilled") map[r.value.id] = r.value.status;
      }
      setStatuses(map);
    }

    poll();
    const interval = setInterval(poll, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [protections]);

  function handleClear() {
    if (confirm("Clear all protections? This cannot be undone.")) {
      clearProtections();
      setProtections([]);
      setStatuses({});
      setSelectedId(null);
    }
  }

  if (protections.length === 0) {
    return (
      <div className="dashboard">
        <div className="dashboard__empty">
          <span className="dashboard__empty-icon">🛡️</span>
          <h2>No Active Protections</h2>
          <p>Purchase tickets with weather protection to see them here.</p>
          <Link to="/" className="btn btn--primary">Browse Events</Link>
        </div>
      </div>
    );
  }

  const selected = protections.find(
    (p) => p.contract.contract_id === selectedId,
  );
  const selectedStatus = selectedId ? statuses[selectedId] : null;

  return (
    <div className="dashboard">
      <div className="dashboard__header">
        <div>
          <h1 className="dashboard__title">My Weather Protections</h1>
          <p className="dashboard__subtitle">
            {protections.length} active protection{protections.length !== 1 ? "s" : ""} •
            Real-time NEXRAD radar overlay
          </p>
        </div>
        <button className="btn btn--ghost btn--sm" onClick={handleClear}>
          Clear All
        </button>
      </div>

      <div className="dashboard__map-section">
        <RadarMap
          protections={protections}
          selectedId={selectedId}
          onSelect={setSelectedId}
          height={420}
        />
      </div>

      <div className="dashboard__grid">
        {protections.map((p) => {
          const s = statuses[p.contract.contract_id];
          const isSelected = p.contract.contract_id === selectedId;
          const isSettled = s?.status?.startsWith("settled");

          return (
            <button
              key={p.contract.contract_id}
              className={`protection-card ${isSelected ? "protection-card--selected" : ""}`}
              onClick={() => setSelectedId(p.contract.contract_id)}
            >
              <div className="protection-card__header">
                <span
                  className="protection-card__emoji"
                  style={{ background: p.event.gradient }}
                >
                  {p.event.emoji}
                </span>
                <div className="protection-card__info">
                  <h3 className="protection-card__name">{p.event.name}</h3>
                  <span className="protection-card__venue">
                    {p.event.venue}, {p.event.city}
                  </span>
                </div>
                <StatusBadge status={s?.status ?? p.contract.status} />
              </div>

              <div className="protection-card__details">
                <div className="protection-card__stat">
                  <span className="protection-card__stat-label">Event Date</span>
                  <span className="protection-card__stat-value">
                    {p.event.dateDisplay}
                  </span>
                </div>
                <div className="protection-card__stat">
                  <span className="protection-card__stat-label">Premium</span>
                  <span className="protection-card__stat-value">
                    ${p.contract.premium_usd.toFixed(2)}
                  </span>
                </div>
                <div className="protection-card__stat">
                  <span className="protection-card__stat-label">Payout</span>
                  <span className="protection-card__stat-value text-green">
                    ${p.contract.notional_usd.toFixed(2)}
                  </span>
                </div>
                <div className="protection-card__stat">
                  <span className="protection-card__stat-label">Trigger</span>
                  <span className="protection-card__stat-value">
                    ≥ {p.riskPrice.settlement_rule.threshold_mm}mm rain
                  </span>
                </div>
              </div>

              {isSettled && s && (
                <div className="protection-card__settlement">
                  <div className="protection-card__settlement-header">
                    {s.outcome === "YES" ? "🎉 Payout Triggered" : "✅ No Payout"}
                  </div>
                  <div className="protection-card__settlement-details">
                    <div className="protection-card__stat">
                      <span className="protection-card__stat-label">Observed</span>
                      <span className="protection-card__stat-value">
                        {s.observed_value?.toFixed(1)}mm
                      </span>
                    </div>
                    <div className="protection-card__stat">
                      <span className="protection-card__stat-label">Settled</span>
                      <span className="protection-card__stat-value">
                        {s.settled_at
                          ? new Date(s.settled_at).toLocaleString()
                          : "—"}
                      </span>
                    </div>
                    {s.record_hash && (
                      <div className="protection-card__stat protection-card__stat--full">
                        <span className="protection-card__stat-label">
                          Evidence Hash
                        </span>
                        <code className="protection-card__hash">
                          {s.record_hash}
                        </code>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="protection-card__footer">
                <code className="protection-card__ticker">{p.contract.ticker}</code>
              </div>
            </button>
          );
        })}
      </div>

      {selected && selectedStatus && (
        <div className="dashboard__detail-panel">
          <h3>Contract Detail</h3>
          <div className="dashboard__detail-grid">
            <div>
              <span className="dashboard__detail-label">Contract ID</span>
              <code>{selected.contract.contract_id}</code>
            </div>
            <div>
              <span className="dashboard__detail-label">H3 Cell</span>
              <code>{selected.contract.h3_index}</code>
            </div>
            <div>
              <span className="dashboard__detail-label">Risk Type</span>
              <span>{selected.contract.risk_type}</span>
            </div>
            <div>
              <span className="dashboard__detail-label">Settlement Window</span>
              <span>
                {new Date(selected.contract.start_time).toLocaleDateString()} –{" "}
                {new Date(selected.contract.end_time).toLocaleDateString()}
              </span>
            </div>
            <div>
              <span className="dashboard__detail-label">Oracle Source</span>
              <span>{selected.riskPrice.settlement_rule.oracle_source}</span>
            </div>
            <div>
              <span className="dashboard__detail-label">Pricing Model</span>
              <span>{selected.riskPrice.pricing_model}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label =
    status === "active"
      ? "Active"
      : status === "settled_yes"
        ? "Paid Out"
        : status === "settled_no"
          ? "No Payout"
          : status === "disputed"
            ? "Disputed"
            : status === "expired"
              ? "Expired"
              : status;

  const variant =
    status === "active"
      ? "active"
      : status === "settled_yes"
        ? "paid"
        : status === "settled_no"
          ? "settled"
          : status === "disputed"
            ? "disputed"
            : "default";

  return <span className={`status-badge status-badge--${variant}`}>{label}</span>;
}

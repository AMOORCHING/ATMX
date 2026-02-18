import { Link, useLocation, Navigate } from "react-router-dom";
import type { EventData, RiskPriceResponse, ContractCreateResponse } from "../types";

interface ConfirmationState {
  event: EventData;
  contract: ContractCreateResponse | null;
  risk: RiskPriceResponse;
  ticketQty: number;
  protectionOn: boolean;
  total: number;
}

export default function Confirmation() {
  const location = useLocation();
  const state = location.state as ConfirmationState | null;

  if (!state?.event) return <Navigate to="/" replace />;

  const { event, contract, risk, ticketQty, protectionOn, total } = state;

  return (
    <div className="confirmation">
      <div className="confirmation__card">
        <div className="confirmation__check">
          <svg viewBox="0 0 52 52" className="confirmation__check-svg">
            <circle cx="26" cy="26" r="25" fill="none" stroke="currentColor" strokeWidth="2" />
            <path fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" d="M14.1 27.2l7.1 7.2 16.7-16.8" />
          </svg>
        </div>

        <h1 className="confirmation__title">Purchase Confirmed!</h1>
        <p className="confirmation__subtitle">
          Your tickets for <strong>{event.name}</strong> are secured.
        </p>

        <div className="confirmation__summary">
          <div className="confirmation__row">
            <span>Event</span>
            <span>{event.name}</span>
          </div>
          <div className="confirmation__row">
            <span>Date</span>
            <span>{event.dateDisplay}</span>
          </div>
          <div className="confirmation__row">
            <span>Venue</span>
            <span>{event.venue}, {event.city}</span>
          </div>
          <div className="confirmation__row">
            <span>Tickets</span>
            <span>{ticketQty}× General Admission</span>
          </div>
          <div className="confirmation__row confirmation__row--total">
            <span>Total Charged</span>
            <span>${total.toFixed(2)}</span>
          </div>
        </div>

        {protectionOn && contract && (
          <>
            <div className="confirmation__divider" />

            <div className="confirmation__protection">
              <h2 className="confirmation__section-title">
                🛡️ Weather Protection Active
              </h2>

              <div className="confirmation__contract">
                <div className="confirmation__row">
                  <span>Contract ID</span>
                  <code className="confirmation__code">{contract.contract_id}</code>
                </div>
                <div className="confirmation__row">
                  <span>Ticker</span>
                  <code className="confirmation__code">{contract.ticker}</code>
                </div>
                <div className="confirmation__row">
                  <span>Status</span>
                  <span className="status-badge status-badge--active">{contract.status}</span>
                </div>
                <div className="confirmation__row">
                  <span>Premium Paid</span>
                  <span>${contract.premium_usd.toFixed(2)}</span>
                </div>
                <div className="confirmation__row">
                  <span>Payout if Triggered</span>
                  <span className="text-green">${contract.notional_usd.toFixed(2)}</span>
                </div>
              </div>

              <div className="confirmation__rule">
                <h3 className="confirmation__rule-title">Settlement Rule</h3>
                <div className="confirmation__rule-grid">
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">What triggers payout</span>
                    <span className="confirmation__rule-value">
                      Cumulative precipitation ≥ {risk.settlement_rule.threshold_mm}mm
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Measurement period</span>
                    <span className="confirmation__rule-value">
                      {new Date(contract.start_time).toLocaleDateString()} —{" "}
                      {new Date(contract.end_time).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Data source</span>
                    <span className="confirmation__rule-value">
                      {risk.settlement_rule.oracle_source} weather stations
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Aggregation</span>
                    <span className="confirmation__rule-value">
                      {risk.settlement_rule.aggregation} of station readings
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Min. stations</span>
                    <span className="confirmation__rule-value">
                      {risk.settlement_rule.min_stations} ASOS station(s) required
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Expected resolution</span>
                    <span className="confirmation__rule-value">
                      Within 24 hours of event end
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Rule version</span>
                    <span className="confirmation__rule-value">
                      {risk.settlement_rule.version}
                    </span>
                  </div>
                  <div className="confirmation__rule-item">
                    <span className="confirmation__rule-label">Verification</span>
                    <span className="confirmation__rule-value">
                      SHA-256 hash-chained audit trail
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        <div className="confirmation__actions">
          {protectionOn && (
            <Link to="/dashboard" className="btn btn--primary">
              View My Protections
            </Link>
          )}
          <Link to="/" className="btn btn--secondary">
            Browse More Events
          </Link>
        </div>
      </div>
    </div>
  );
}

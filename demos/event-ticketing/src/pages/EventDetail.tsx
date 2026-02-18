import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getEventById } from "../data/events";
import {
  fetchRiskPrice,
  createContract,
  venueToH3,
  saveProtection,
} from "../api/risk";
import type { RiskPriceResponse } from "../types";
import { getRiskLevel, getRiskLabel } from "../types";
import RiskBadge from "../components/RiskBadge";

const PROTECTION_THRESHOLD = 0.1;
const DEFAULT_PAYOUT = 100;

export default function EventDetail() {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();
  const event = eventId ? getEventById(eventId) : undefined;

  const [risk, setRisk] = useState<RiskPriceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [protectionOn, setProtectionOn] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [ticketQty, setTicketQty] = useState(1);

  useEffect(() => {
    if (!event) return;
    let cancelled = false;

    async function load() {
      const endDate = new Date(event!.date);
      endDate.setDate(endDate.getDate() + 2);
      const data = await fetchRiskPrice(
        event!.lat,
        event!.lng,
        event!.date,
        endDate.toISOString(),
        event!.id,
      );
      if (!cancelled) {
        setRisk(data);
        if (data.risk_probability >= PROTECTION_THRESHOLD) {
          setProtectionOn(true);
        }
        setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [event]);

  if (!event) {
    return (
      <div className="detail">
        <div className="detail__empty">
          <h2>Event not found</h2>
          <Link to="/" className="btn btn--secondary">Browse Events</Link>
        </div>
      </div>
    );
  }

  const riskLevel = risk ? getRiskLevel(risk.risk_probability) : null;
  const showProtection = risk && risk.risk_probability >= PROTECTION_THRESHOLD;
  const premiumPerTicket = risk?.suggested_premium_usd ?? 0;
  const subtotal = event.ticketPrice * ticketQty;
  const protectionCost = protectionOn ? premiumPerTicket * ticketQty : 0;
  const total = subtotal + protectionCost;

  async function handlePurchase() {
    if (!event || !risk) return;
    setPurchasing(true);

    try {
      const endDate = new Date(event.date);
      endDate.setDate(endDate.getDate() + 2);
      const h3Index = venueToH3(event.lat, event.lng);

      let contractData = null;

      if (protectionOn) {
        contractData = await createContract(
          {
            h3_index: h3Index,
            risk_type: "precip_heavy",
            start_time: event.date,
            end_time: endDate.toISOString(),
            notional_usd: DEFAULT_PAYOUT * ticketQty,
          },
          premiumPerTicket * ticketQty,
        );

        saveProtection({
          event,
          contract: contractData,
          riskPrice: risk,
          purchasedAt: new Date().toISOString(),
        });
      }

      navigate("/confirmation", {
        state: {
          event,
          contract: contractData,
          risk,
          ticketQty,
          protectionOn,
          total,
        },
      });
    } catch (err) {
      console.error("Purchase failed:", err);
      setPurchasing(false);
    }
  }

  return (
    <div className="detail">
      <Link to="/" className="detail__back">← All Events</Link>

      <div className="detail__hero" style={{ background: event.gradient }}>
        <span className="detail__hero-emoji">{event.emoji}</span>
        <div className="detail__hero-info">
          <div className="detail__hero-genre">{event.genre}</div>
          <h1 className="detail__hero-title">{event.name}</h1>
          <p className="detail__hero-tagline">{event.tagline}</p>
        </div>
      </div>

      <div className="detail__content">
        <div className="detail__main">
          <section className="detail__section">
            <h2 className="detail__section-title">Event Details</h2>
            <div className="detail__info-grid">
              <div className="detail__info-item">
                <span className="detail__info-label">Date</span>
                <span className="detail__info-value">{event.dateDisplay}</span>
              </div>
              <div className="detail__info-item">
                <span className="detail__info-label">Time</span>
                <span className="detail__info-value">{event.time}</span>
              </div>
              <div className="detail__info-item">
                <span className="detail__info-label">Venue</span>
                <span className="detail__info-value">{event.venue}</span>
              </div>
              <div className="detail__info-item">
                <span className="detail__info-label">Location</span>
                <span className="detail__info-value">{event.city}, {event.state}</span>
              </div>
            </div>
            <p className="detail__description">{event.description}</p>
          </section>

          <section className="detail__section">
            <h2 className="detail__section-title">Weather Risk Assessment</h2>
            {loading ? (
              <div className="detail__risk-loading">
                <div className="spinner" /> Analyzing weather data...
              </div>
            ) : risk ? (
              <div className={`detail__risk-card detail__risk-card--${riskLevel}`}>
                <div className="detail__risk-header">
                  <RiskBadge probability={risk.risk_probability} size="lg" />
                  <div>
                    <div className="detail__risk-title">
                      {getRiskLabel(getRiskLevel(risk.risk_probability))}
                    </div>
                    <div className="detail__risk-subtitle">
                      {Math.round(risk.risk_probability * 100)}% chance of heavy rain
                      during the event
                    </div>
                  </div>
                </div>
                <div className="detail__risk-details">
                  <div className="detail__risk-stat">
                    <span className="detail__risk-stat-label">Confidence</span>
                    <span className="detail__risk-stat-value">
                      {Math.round(risk.confidence_interval[0] * 100)}% –{" "}
                      {Math.round(risk.confidence_interval[1] * 100)}%
                    </span>
                  </div>
                  <div className="detail__risk-stat">
                    <span className="detail__risk-stat-label">Data Source</span>
                    <span className="detail__risk-stat-value">
                      {risk.settlement_rule.oracle_source}
                    </span>
                  </div>
                  <div className="detail__risk-stat">
                    <span className="detail__risk-stat-label">Threshold</span>
                    <span className="detail__risk-stat-value">
                      {risk.settlement_rule.threshold_mm}mm cumulative precip
                    </span>
                  </div>
                  <div className="detail__risk-stat">
                    <span className="detail__risk-stat-label">Model</span>
                    <span className="detail__risk-stat-value">
                      {risk.pricing_model}
                    </span>
                  </div>
                </div>
              </div>
            ) : null}
          </section>
        </div>

        <aside className="detail__sidebar">
          <div className="purchase-card">
            <h3 className="purchase-card__title">Get Tickets</h3>

            <div className="purchase-card__row">
              <span>General Admission</span>
              <span>${event.ticketPrice}</span>
            </div>

            <div className="purchase-card__qty">
              <label htmlFor="qty">Quantity</label>
              <div className="purchase-card__qty-controls">
                <button
                  onClick={() => setTicketQty((q) => Math.max(1, q - 1))}
                  disabled={ticketQty <= 1}
                >
                  −
                </button>
                <span id="qty">{ticketQty}</span>
                <button onClick={() => setTicketQty((q) => Math.min(10, q + 1))}>
                  +
                </button>
              </div>
            </div>

            {showProtection && (
              <div className="purchase-card__protection">
                <div className="purchase-card__protection-header">
                  <div>
                    <div className="purchase-card__protection-title">
                      🛡️ Weather Protection
                    </div>
                    <div className="purchase-card__protection-desc">
                      Get <strong>${DEFAULT_PAYOUT}</strong>/ticket if precipitation
                      exceeds {risk.settlement_rule.threshold_mm}mm during the event
                    </div>
                  </div>
                  <button
                    className={`toggle ${protectionOn ? "toggle--on" : ""}`}
                    onClick={() => setProtectionOn(!protectionOn)}
                    aria-label="Toggle weather protection"
                  >
                    <span className="toggle__knob" />
                  </button>
                </div>
                {protectionOn && (
                  <div className="purchase-card__protection-details">
                    <div className="purchase-card__row purchase-card__row--sm">
                      <span>Premium per ticket</span>
                      <span>${premiumPerTicket.toFixed(2)}</span>
                    </div>
                    <div className="purchase-card__row purchase-card__row--sm">
                      <span>Payout trigger</span>
                      <span>≥ {risk.settlement_rule.threshold_mm}mm rain</span>
                    </div>
                    <div className="purchase-card__row purchase-card__row--sm">
                      <span>Payout per ticket</span>
                      <span className="text-green">${DEFAULT_PAYOUT}</span>
                    </div>
                    <div className="purchase-card__row purchase-card__row--sm">
                      <span>Settlement</span>
                      <span>NOAA ASOS verified</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {!showProtection && !loading && risk && (
              <div className="purchase-card__no-protection">
                ☀️ Conditions look great! Weather protection not needed.
              </div>
            )}

            <div className="purchase-card__divider" />

            <div className="purchase-card__row">
              <span>Tickets ({ticketQty}×)</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>
            {protectionOn && (
              <div className="purchase-card__row">
                <span>Weather Protection ({ticketQty}×)</span>
                <span>${protectionCost.toFixed(2)}</span>
              </div>
            )}
            <div className="purchase-card__row purchase-card__total">
              <span>Total</span>
              <span>${total.toFixed(2)}</span>
            </div>

            <button
              className="btn btn--primary btn--full"
              onClick={handlePurchase}
              disabled={purchasing || loading}
            >
              {purchasing ? "Processing..." : `Purchase — $${total.toFixed(2)}`}
            </button>

            <p className="purchase-card__footnote">
              {protectionOn
                ? "Settlement powered by ATMX Risk API • NOAA-verified outcomes"
                : "Add weather protection to get covered if it rains"}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

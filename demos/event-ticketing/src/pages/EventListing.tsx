import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EVENTS } from "../data/events";
import { fetchRiskPrice } from "../api/risk";
import type { RiskPriceResponse } from "../types";
import RiskBadge from "../components/RiskBadge";

export default function EventListing() {
  const [riskData, setRiskData] = useState<Record<string, RiskPriceResponse>>({});

  useEffect(() => {
    let cancelled = false;

    async function loadRisk() {
      const results = await Promise.allSettled(
        EVENTS.map(async (evt) => {
          const endDate = new Date(evt.date);
          endDate.setDate(endDate.getDate() + 2);
          const data = await fetchRiskPrice(
            evt.lat,
            evt.lng,
            evt.date,
            endDate.toISOString(),
            evt.id,
          );
          return { id: evt.id, data };
        }),
      );

      if (cancelled) return;

      const map: Record<string, RiskPriceResponse> = {};
      for (const r of results) {
        if (r.status === "fulfilled") map[r.value.id] = r.value.data;
      }
      setRiskData(map);
    }

    loadRisk();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="listing">
      <div className="listing__hero">
        <h1 className="listing__title">Upcoming Outdoor Events</h1>
        <p className="listing__subtitle">
          Weather risk assessed in real-time by the ATMX Risk API.
          Buy tickets with optional weather protection — if it rains, you get paid.
        </p>
      </div>

      <div className="listing__grid">
        {EVENTS.map((evt) => {
          const risk = riskData[evt.id] ?? null;
          return (
            <Link
              key={evt.id}
              to={`/event/${evt.id}`}
              className="event-card"
            >
              <div
                className="event-card__visual"
                style={{ background: evt.gradient }}
              >
                <span className="event-card__emoji">{evt.emoji}</span>
                <div className="event-card__risk-pos">
                  <RiskBadge
                    probability={risk?.risk_probability ?? null}
                    size="md"
                  />
                </div>
              </div>

              <div className="event-card__body">
                <div className="event-card__meta">
                  <span className="event-card__genre">{evt.genre}</span>
                  <span className="event-card__location">
                    {evt.city}, {evt.state}
                  </span>
                </div>

                <h3 className="event-card__name">{evt.name}</h3>

                <div className="event-card__details">
                  <span className="event-card__date">{evt.dateDisplay}</span>
                  <span className="event-card__venue">{evt.venue}</span>
                </div>

                <div className="event-card__footer">
                  <span className="event-card__price">
                    From <strong>${evt.ticketPrice}</strong>
                  </span>
                  <span className="event-card__cta">View Tickets →</span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

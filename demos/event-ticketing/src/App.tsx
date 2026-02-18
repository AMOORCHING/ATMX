import { Routes, Route, Link, useLocation } from "react-router-dom";
import EventListing from "./pages/EventListing";
import EventDetail from "./pages/EventDetail";
import Confirmation from "./pages/Confirmation";
import Dashboard from "./pages/Dashboard";

const API_KEY = import.meta.env.VITE_ATMX_API_KEY || "";

export default function App() {
  const location = useLocation();

  return (
    <div className="app">
      <header className="header">
        <div className="header__inner">
          <Link to="/" className="header__brand">
            <span className="header__logo">EventShield</span>
            <span className="header__powered">
              powered by <strong>atmx</strong>
            </span>
          </Link>

          <nav className="header__nav">
            <Link
              to="/"
              className={`header__link ${location.pathname === "/" ? "header__link--active" : ""}`}
            >
              Events
            </Link>
            <Link
              to="/dashboard"
              className={`header__link ${location.pathname === "/dashboard" ? "header__link--active" : ""}`}
            >
              My Protections
            </Link>
          </nav>

          <div className="header__right">
            <span className={`api-badge ${API_KEY ? "api-badge--live" : "api-badge--demo"}`}>
              <span className="api-badge__dot" />
              {API_KEY ? "Live API" : "Demo Mode"}
            </span>
          </div>
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<EventListing />} />
          <Route path="/event/:eventId" element={<EventDetail />} />
          <Route path="/confirmation" element={<Confirmation />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="footer__inner">
          <span>EventShield Demo — ATMX Weather Risk Integration</span>
          <span className="footer__links">
            <a href="http://localhost:8001/docs" target="_blank" rel="noreferrer">
              API Docs
            </a>
            <span className="footer__sep">·</span>
            <a
              href="https://github.com/atmx-org/atmx"
              target="_blank"
              rel="noreferrer"
            >
              GitHub
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}

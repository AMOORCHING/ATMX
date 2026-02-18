"use strict";
(() => {
  // src/atmx-widget.ts
  (function() {
    "use strict";
    const SELECTOR = "#atmx-weather-protection, [data-atmx-widget]";
    const ICONS = {
      shield: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
      check: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
      alert: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
    };
    const STYLES = `
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

    :host {
      display: block;
      --atmx-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      --atmx-mono: "SF Mono", "Fira Code", Consolas, Monaco, monospace;
    }

    /* \u2500\u2500 Light Theme (default) \u2500\u2500 */
    .atmx {
      font-family: var(--atmx-font);
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      --bg: #ffffff;
      --surface: #f7f8fa;
      --border: #e5e7eb;
      --border-hover: #d1d5db;
      --text: #111827;
      --text-2: #6b7280;
      --text-3: #9ca3af;
      --accent: #4f7fff;
      --accent-bg: rgba(79, 127, 255, 0.06);
      --green: #16a34a;
      --green-bg: rgba(22, 163, 74, 0.06);
      --green-border: rgba(22, 163, 74, 0.15);
      --amber: #d97706;
      --amber-bg: rgba(217, 119, 6, 0.06);
      --amber-border: rgba(217, 119, 6, 0.15);
      --red: #dc2626;
      --red-bg: rgba(220, 38, 38, 0.04);
      --red-border: rgba(220, 38, 38, 0.12);
      --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 2px 16px rgba(0,0,0,0.04);
      --shadow-active: 0 0 0 1px rgba(22,163,74,0.15), 0 2px 16px rgba(22,163,74,0.06);
      --radius: 12px;
      --radius-sm: 8px;
      --radius-xs: 6px;
      --transition: 200ms ease;
    }

    /* \u2500\u2500 Dark Theme \u2500\u2500 */
    .atmx--dark {
      --bg: #14141f;
      --surface: #1c1c2b;
      --border: #2a2a3e;
      --border-hover: #363650;
      --text: #ededf0;
      --text-2: #9494aa;
      --text-3: #606078;
      --accent: #4f7fff;
      --accent-bg: rgba(79, 127, 255, 0.1);
      --green: #22c55e;
      --green-bg: rgba(34, 197, 94, 0.08);
      --green-border: rgba(34, 197, 94, 0.2);
      --amber: #f59e0b;
      --amber-bg: rgba(245, 158, 11, 0.08);
      --amber-border: rgba(245, 158, 11, 0.2);
      --red: #ef4444;
      --red-bg: rgba(239, 68, 68, 0.06);
      --red-border: rgba(239, 68, 68, 0.15);
      --shadow: 0 2px 8px rgba(0,0,0,0.25), 0 4px 24px rgba(0,0,0,0.15);
      --shadow-active: 0 0 0 1px rgba(34,197,94,0.2), 0 4px 24px rgba(34,197,94,0.06);
    }

    /* \u2500\u2500 Card \u2500\u2500 */
    .atmx-card {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      transition: border-color var(--transition), box-shadow var(--transition);
    }
    .atmx-card--active {
      border-color: var(--green-border);
      box-shadow: var(--shadow-active);
    }

    /* \u2500\u2500 Header \u2500\u2500 */
    .atmx-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      border-bottom: 1px solid var(--border);
    }
    .atmx-header__left {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--accent);
    }
    .atmx-header__title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -0.01em;
    }
    .atmx-header__brand {
      font-size: 10px;
      font-weight: 700;
      color: var(--text-3);
      letter-spacing: 0.08em;
    }

    /* \u2500\u2500 Body \u2500\u2500 */
    .atmx-body {
      padding: 16px 20px;
    }

    /* \u2500\u2500 Risk Assessment \u2500\u2500 */
    .atmx-risk { margin-bottom: 14px; }
    .atmx-risk__row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
    }
    .atmx-risk__emoji { font-size: 18px; line-height: 1; }
    .atmx-risk__text { font-size: 13px; font-weight: 500; color: var(--text); }
    .atmx-risk__pct { font-weight: 700; }

    .atmx-risk__bar {
      height: 6px;
      background: var(--surface);
      border-radius: 3px;
      overflow: hidden;
      margin-bottom: 10px;
    }
    .atmx-risk__fill {
      height: 100%;
      border-radius: 3px;
      width: 0%;
      transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1);
    }
    .atmx-risk__fill--low { background: var(--green); }
    .atmx-risk__fill--moderate { background: var(--amber); }
    .atmx-risk__fill--high { background: var(--red); }

    .atmx-risk__badge {
      display: inline-flex;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 9px;
      border-radius: 100px;
    }
    .atmx-risk__badge--low {
      background: var(--green-bg);
      color: var(--green);
      border: 1px solid var(--green-border);
    }
    .atmx-risk__badge--moderate {
      background: var(--amber-bg);
      color: var(--amber);
      border: 1px solid var(--amber-border);
    }
    .atmx-risk__badge--high {
      background: var(--red-bg);
      color: var(--red);
      border: 1px solid var(--red-border);
    }

    /* \u2500\u2500 Divider \u2500\u2500 */
    .atmx-divider {
      height: 1px;
      background: var(--border);
      margin: 14px 0;
    }

    /* \u2500\u2500 Detail Rows \u2500\u2500 */
    .atmx-details {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .atmx-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
    }
    .atmx-row__label { color: var(--text-2); }
    .atmx-row__value {
      font-weight: 500;
      color: var(--text);
      text-align: right;
    }
    .atmx-row__value--green {
      color: var(--green);
      font-weight: 600;
    }

    /* \u2500\u2500 Toggle Area \u2500\u2500 */
    .atmx-toggle-area {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      background: var(--surface);
      border: 1px solid transparent;
      border-radius: var(--radius-sm);
      margin-top: 14px;
      cursor: pointer;
      transition: all var(--transition);
      user-select: none;
      -webkit-user-select: none;
    }
    .atmx-toggle-area:hover {
      border-color: var(--border-hover);
    }
    .atmx-toggle-area:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    .atmx-toggle-area--on {
      background: var(--green-bg);
      border-color: var(--green-border);
    }
    .atmx-toggle-area--on:hover {
      border-color: var(--green-border);
    }
    .atmx-toggle-area__left {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .atmx-toggle-area__icon {
      font-size: 15px;
      line-height: 1;
      flex-shrink: 0;
    }
    .atmx-toggle-area__text {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
    }
    .atmx-toggle-area__price {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-2);
      margin-left: auto;
      flex-shrink: 0;
    }

    /* \u2500\u2500 Toggle Switch \u2500\u2500 */
    .atmx-switch {
      position: relative;
      width: 44px;
      height: 24px;
      border-radius: 12px;
      background: var(--border);
      border: none;
      cursor: pointer;
      flex-shrink: 0;
      transition: background var(--transition);
      padding: 0;
      -webkit-appearance: none;
      appearance: none;
    }
    .atmx-switch:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    .atmx-switch--on { background: var(--accent); }
    .atmx-switch__knob {
      position: absolute;
      top: 3px;
      left: 3px;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #fff;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
      transition: transform var(--transition);
      pointer-events: none;
    }
    .atmx-switch--on .atmx-switch__knob {
      transform: translateX(20px);
    }

    /* \u2500\u2500 Footer \u2500\u2500 */
    .atmx-footer {
      padding: 8px 20px;
      border-top: 1px solid var(--border);
      text-align: center;
    }
    .atmx-footer__text {
      font-size: 11px;
      color: var(--text-3);
    }
    .atmx-footer__link {
      color: var(--text-2);
      text-decoration: none;
      font-weight: 600;
      transition: color var(--transition);
    }
    .atmx-footer__link:hover { color: var(--accent); }

    /* \u2500\u2500 Success Banner \u2500\u2500 */
    .atmx-success {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      background: var(--green-bg);
      border: 1px solid var(--green-border);
      border-radius: var(--radius-sm);
      margin-bottom: 14px;
      animation: atmx-in 0.3s ease;
    }
    .atmx-success__icon {
      color: var(--green);
      flex-shrink: 0;
      line-height: 0;
    }
    .atmx-success__text {
      font-size: 13px;
      font-weight: 600;
      color: var(--green);
    }

    /* \u2500\u2500 Error Banner \u2500\u2500 */
    .atmx-error-msg {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      background: var(--red-bg);
      border: 1px solid var(--red-border);
      border-radius: var(--radius-sm);
    }
    .atmx-error-msg__icon {
      color: var(--red);
      flex-shrink: 0;
      line-height: 0;
    }
    .atmx-error-msg__text {
      font-size: 13px;
      color: var(--red);
      flex: 1;
    }
    .atmx-error-msg__retry {
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-xs);
      cursor: pointer;
      padding: 5px 12px;
      transition: all var(--transition);
      white-space: nowrap;
      font-family: var(--atmx-font);
    }
    .atmx-error-msg__retry:hover {
      background: var(--accent-bg);
      border-color: var(--accent);
    }

    /* \u2500\u2500 Contract ID \u2500\u2500 */
    .atmx-contract-id {
      font-size: 11px;
      color: var(--text-3);
      font-family: var(--atmx-mono);
      margin-top: 10px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* \u2500\u2500 Skeleton Loading \u2500\u2500 */
    .atmx-skel {
      background: linear-gradient(90deg, var(--surface) 25%, var(--border) 50%, var(--surface) 75%);
      background-size: 200% 100%;
      animation: atmx-shimmer 1.5s ease-in-out infinite;
      border-radius: 4px;
    }
    .atmx-skel--line { height: 13px; margin-bottom: 10px; }
    .atmx-skel--bar { height: 6px; margin-bottom: 10px; }
    .atmx-skel--pill { height: 20px; width: 80px; border-radius: 10px; }
    .atmx-skel--block { height: 48px; margin-top: 14px; border-radius: var(--radius-sm); }

    /* \u2500\u2500 Spinner \u2500\u2500 */
    .atmx-spinner {
      width: 14px;
      height: 14px;
      border: 2px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: atmx-spin 0.6s linear infinite;
      flex-shrink: 0;
    }

    /* \u2500\u2500 Animations \u2500\u2500 */
    @keyframes atmx-shimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    @keyframes atmx-spin {
      to { transform: rotate(360deg); }
    }
    @keyframes atmx-in {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `;
    function level(p) {
      return p < 0.1 ? "low" : p < 0.3 ? "moderate" : "high";
    }
    function emoji(l) {
      return l === "low" ? "\u2600\uFE0F" : l === "moderate" ? "\u{1F326}\uFE0F" : "\u26C8\uFE0F";
    }
    function label(l) {
      return l === "low" ? "Low Risk" : l === "moderate" ? "Moderate Risk" : "High Risk";
    }
    function usd(n) {
      return "$" + n.toFixed(2);
    }
    function thresholdText(r) {
      if (r.threshold_mm != null) return `${r.threshold_mm}mm rain`;
      if (r.threshold_ms != null) return `${r.threshold_ms} m/s wind`;
      if (r.threshold_c != null) return `${r.threshold_c}\xB0C`;
      if (r.threshold_cm != null) return `${r.threshold_cm}cm snow`;
      return "threshold";
    }
    function thresholdShort(r) {
      if (r.threshold_mm != null) return `\u2265 ${r.threshold_mm}mm`;
      if (r.threshold_ms != null) return `\u2265 ${r.threshold_ms} m/s`;
      if (r.threshold_c != null)
        return r.threshold_c <= 0 ? `\u2264 ${r.threshold_c}\xB0C` : `\u2265 ${r.threshold_c}\xB0C`;
      if (r.threshold_cm != null) return `\u2265 ${r.threshold_cm}cm`;
      return "\u2013";
    }
    function wait(ms) {
      return new Promise((r) => setTimeout(r, ms));
    }
    function hash(s) {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = Math.imul(31, h) + s.charCodeAt(i) | 0;
      return Math.abs(h);
    }
    function srand(seed) {
      const x = Math.sin(seed) * 1e4;
      return x - Math.floor(x);
    }
    function demoRule() {
      return {
        version: "v1.3",
        oracle_source: "NOAA_ASOS",
        threshold_mm: 12.7,
        aggregation: "sum",
        min_stations: 1,
        dispute_spread_ratio: 0.2
      };
    }
    function demoRisk(cfg) {
      const s = hash(cfg.h3Index);
      const prob = 0.1 + srand(s) * 0.35;
      const spread = 0.03 + srand(s + 1) * 0.04;
      const premium = Math.round(prob * cfg.payoutAmount * 0.125 * 100) / 100;
      return {
        h3_index: cfg.h3Index,
        risk_type: cfg.riskType,
        risk_probability: Math.round(prob * 1e3) / 1e3,
        confidence_interval: [
          Math.max(0, Math.round((prob - spread) * 1e3) / 1e3),
          Math.min(1, Math.round((prob + spread) * 1e3) / 1e3)
        ],
        suggested_premium_usd: premium,
        settlement_rule: demoRule(),
        pricing_model: "ensemble_baseline_v1",
        valid_until: new Date(Date.now() + 3e5).toISOString()
      };
    }
    function demoContract(cfg, premium) {
      const id = crypto.randomUUID();
      const d = cfg.eventEnd.slice(0, 10).replace(/-/g, "");
      return {
        contract_id: id,
        h3_index: cfg.h3Index,
        risk_type: cfg.riskType,
        start_time: cfg.eventStart,
        end_time: cfg.eventEnd,
        notional_usd: cfg.payoutAmount,
        premium_usd: premium,
        settlement_rule: demoRule(),
        status: "active",
        created_at: (/* @__PURE__ */ new Date()).toISOString(),
        ticker: `ATMX-${cfg.h3Index.slice(0, 11)}-PRECIP-13MM-${d}`
      };
    }
    async function fetchRisk(cfg) {
      if (!cfg.apiKey) {
        await wait(500);
        return demoRisk(cfg);
      }
      try {
        const params = new URLSearchParams({
          h3_index: cfg.h3Index,
          risk_type: cfg.riskType,
          start_time: cfg.eventStart,
          end_time: cfg.eventEnd
        });
        const r = await fetch(`${cfg.apiUrl}/v1/risk_price?${params}`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${cfg.apiKey}`
          }
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      } catch {
        console.warn("[ATMX] API unavailable \u2014 using demo pricing");
        return demoRisk(cfg);
      }
    }
    async function purchase(cfg, premium) {
      if (!cfg.apiKey) {
        await wait(900);
        return demoContract(cfg, premium);
      }
      try {
        const r = await fetch(`${cfg.apiUrl}/v1/contracts`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${cfg.apiKey}`
          },
          body: JSON.stringify({
            h3_index: cfg.h3Index,
            risk_type: cfg.riskType,
            start_time: cfg.eventStart,
            end_time: cfg.eventEnd,
            notional_usd: cfg.payoutAmount
          })
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      } catch {
        console.warn("[ATMX] API unavailable \u2014 using demo contract");
        return demoContract(cfg, premium);
      }
    }
    function readConfig(el) {
      const d = el.dataset;
      return {
        h3Index: d.h3Index || "",
        eventStart: d.eventStart || "",
        eventEnd: d.eventEnd || "",
        payoutAmount: parseFloat(d.payoutAmount || "50"),
        apiKey: d.apiKey || "",
        apiUrl: (d.apiUrl || "").replace(/\/$/, ""),
        theme: d.theme || "light",
        riskType: d.riskType || "precip_heavy"
      };
    }
    class ATMXWidget {
      constructor(el) {
        this.state = "loading";
        this.risk = null;
        this.contract = null;
        this.errMsg = "";
        this.el = el;
        this.cfg = readConfig(el);
        this.shadow = el.attachShadow({ mode: "open" });
        this.boot();
      }
      // ── Lifecycle ──────────────────────────────────────────────
      async boot() {
        this.render();
        if (!this.cfg.h3Index) {
          this.state = "error";
          this.errMsg = "Missing required data-h3-index attribute";
          this.render();
          return;
        }
        if (!this.cfg.eventStart || !this.cfg.eventEnd) {
          this.state = "error";
          this.errMsg = "Missing data-event-start or data-event-end";
          this.render();
          return;
        }
        try {
          this.risk = await fetchRisk(this.cfg);
          this.state = "ready";
        } catch (e) {
          this.state = "error";
          this.errMsg = e?.message || "Failed to load weather data";
        }
        this.render();
        this.animateBar();
        this.emit("ready", { riskPrice: this.risk });
      }
      // ── Rendering ─────────────────────────────────────────────
      render() {
        const dark = this.cfg.theme === "dark" ? " atmx--dark" : "";
        const active = this.state === "active" ? " atmx-card--active" : "";
        this.shadow.innerHTML = `
        <style>${STYLES}</style>
        <div class="atmx${dark}">
          <div class="atmx-card${active}">
            ${this.headerHTML()}
            <div class="atmx-body">${this.bodyHTML()}</div>
            ${this.footerHTML()}
          </div>
        </div>`;
        this.bind();
      }
      headerHTML() {
        return `
        <div class="atmx-header">
          <div class="atmx-header__left">
            ${ICONS.shield}
            <span class="atmx-header__title">Weather Protection</span>
          </div>
          <span class="atmx-header__brand">ATMX</span>
        </div>`;
      }
      footerHTML() {
        return `
        <div class="atmx-footer">
          <span class="atmx-footer__text">
            Powered by <a class="atmx-footer__link" href="https://atmx.io" target="_blank" rel="noopener">ATMX</a>
          </span>
        </div>`;
      }
      bodyHTML() {
        switch (this.state) {
          case "loading":
            return this.loadingHTML();
          case "ready":
            return this.readyHTML();
          case "activating":
            return this.activatingHTML();
          case "active":
            return this.activeHTML();
          case "error":
            return this.errorHTML();
        }
      }
      loadingHTML() {
        return `
        <div class="atmx-skel atmx-skel--line" style="width:65%"></div>
        <div class="atmx-skel atmx-skel--bar"></div>
        <div class="atmx-skel atmx-skel--pill"></div>
        <div class="atmx-divider"></div>
        <div class="atmx-skel atmx-skel--line" style="width:100%"></div>
        <div class="atmx-skel atmx-skel--line" style="width:85%"></div>
        <div class="atmx-skel atmx-skel--line" style="width:60%"></div>
        <div class="atmx-skel atmx-skel--block"></div>`;
      }
      riskSectionHTML(showBadge = true) {
        const r = this.risk;
        const l = level(r.risk_probability);
        const pct = Math.round(r.risk_probability * 100);
        return `
        <div class="atmx-risk">
          <div class="atmx-risk__row">
            <span class="atmx-risk__emoji">${emoji(l)}</span>
            <span class="atmx-risk__text">
              <span class="atmx-risk__pct">${pct}%</span> chance of heavy rain
            </span>
          </div>
          <div class="atmx-risk__bar">
            <div class="atmx-risk__fill atmx-risk__fill--${l}" data-pct="${pct}"></div>
          </div>
          ${showBadge ? `<span class="atmx-risk__badge atmx-risk__badge--${l}">${label(l)}</span>` : ""}
        </div>`;
      }
      readyHTML() {
        const r = this.risk;
        const prem = r.suggested_premium_usd;
        const payout = this.cfg.payoutAmount;
        return `
        ${this.riskSectionHTML()}
        <div class="atmx-divider"></div>
        <div class="atmx-details">
          <div class="atmx-row">
            <span class="atmx-row__label">If rain exceeds</span>
            <span class="atmx-row__value">${thresholdText(r.settlement_rule)}</span>
          </div>
          <div class="atmx-row">
            <span class="atmx-row__label">You receive</span>
            <span class="atmx-row__value atmx-row__value--green">${usd(payout)}</span>
          </div>
          <div class="atmx-row">
            <span class="atmx-row__label">Verified by</span>
            <span class="atmx-row__value">${r.settlement_rule.oracle_source.replace(/_/g, " ")}</span>
          </div>
        </div>
        <div class="atmx-toggle-area" data-action="toggle" tabindex="0" role="button"
             aria-label="Add weather protection for ${usd(prem)}">
          <div class="atmx-toggle-area__left">
            <span class="atmx-toggle-area__icon">\u{1F6E1}\uFE0F</span>
            <span class="atmx-toggle-area__text">Add Protection</span>
          </div>
          <span class="atmx-toggle-area__price">${usd(prem)}</span>
          <button class="atmx-switch" role="switch" aria-checked="false" tabindex="-1">
            <span class="atmx-switch__knob"></span>
          </button>
        </div>`;
      }
      activatingHTML() {
        const r = this.risk;
        return `
        ${this.riskSectionHTML(false)}
        <div class="atmx-divider"></div>
        <div class="atmx-toggle-area atmx-toggle-area--on">
          <div class="atmx-toggle-area__left">
            <div class="atmx-spinner"></div>
            <span class="atmx-toggle-area__text">Activating\u2026</span>
          </div>
          <span class="atmx-toggle-area__price">${usd(r.suggested_premium_usd)}</span>
          <button class="atmx-switch atmx-switch--on" disabled>
            <span class="atmx-switch__knob"></span>
          </button>
        </div>`;
      }
      activeHTML() {
        const r = this.risk;
        const c = this.contract;
        const payout = this.cfg.payoutAmount;
        return `
        <div class="atmx-success">
          <span class="atmx-success__icon">${ICONS.check}</span>
          <span class="atmx-success__text">Protection Active</span>
        </div>
        ${this.riskSectionHTML(false)}
        <div class="atmx-divider"></div>
        <div class="atmx-details">
          <div class="atmx-row">
            <span class="atmx-row__label">Premium paid</span>
            <span class="atmx-row__value">${usd(c.premium_usd)}</span>
          </div>
          <div class="atmx-row">
            <span class="atmx-row__label">Payout if triggered</span>
            <span class="atmx-row__value atmx-row__value--green">${usd(payout)}</span>
          </div>
          <div class="atmx-row">
            <span class="atmx-row__label">Trigger</span>
            <span class="atmx-row__value">${thresholdShort(r.settlement_rule)} rain</span>
          </div>
          <div class="atmx-row">
            <span class="atmx-row__label">Settlement</span>
            <span class="atmx-row__value">${r.settlement_rule.oracle_source.replace(/_/g, " ")} verified</span>
          </div>
        </div>
        <div class="atmx-toggle-area atmx-toggle-area--on" data-action="toggle" tabindex="0"
             role="button" aria-label="Remove weather protection">
          <div class="atmx-toggle-area__left">
            <span class="atmx-toggle-area__icon">\u2713</span>
            <span class="atmx-toggle-area__text">Protected</span>
          </div>
          <span class="atmx-toggle-area__price">${usd(c.premium_usd)}</span>
          <button class="atmx-switch atmx-switch--on" role="switch" aria-checked="true" tabindex="-1">
            <span class="atmx-switch__knob"></span>
          </button>
        </div>
        <div class="atmx-contract-id">Contract: ${c.ticker}</div>`;
      }
      errorHTML() {
        return `
        <div class="atmx-error-msg">
          <span class="atmx-error-msg__icon">${ICONS.alert}</span>
          <span class="atmx-error-msg__text">${this.errMsg || "Unable to load weather data"}</span>
          <button class="atmx-error-msg__retry" data-action="retry">Retry</button>
        </div>`;
      }
      // ── Event Binding ─────────────────────────────────────────
      bind() {
        const toggle = this.shadow.querySelector("[data-action=toggle]");
        if (toggle) {
          toggle.addEventListener("click", () => this.handleToggle());
          toggle.addEventListener("keydown", (e) => {
            const key = e.key;
            if (key === "Enter" || key === " ") {
              e.preventDefault();
              this.handleToggle();
            }
          });
        }
        const retry = this.shadow.querySelector("[data-action=retry]");
        if (retry) {
          retry.addEventListener("click", () => {
            this.state = "loading";
            this.errMsg = "";
            this.boot();
          });
        }
      }
      // ── Risk Bar Animation ────────────────────────────────────
      animateBar() {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            const fill = this.shadow.querySelector(".atmx-risk__fill");
            if (fill) fill.style.width = fill.dataset.pct + "%";
          });
        });
      }
      // ── Toggle Logic ──────────────────────────────────────────
      async handleToggle() {
        if (this.state === "ready") {
          this.state = "activating";
          this.render();
          this.animateBar();
          try {
            this.contract = await purchase(this.cfg, this.risk.suggested_premium_usd);
            this.state = "active";
            this.render();
            this.animateBar();
            this.emit("activated", {
              contractId: this.contract.contract_id,
              ticker: this.contract.ticker,
              premium: this.contract.premium_usd,
              contract: this.contract
            });
          } catch (e) {
            this.state = "ready";
            this.render();
            this.animateBar();
            this.emit("error", { message: e?.message });
          }
        } else if (this.state === "active") {
          this.contract = null;
          this.state = "ready";
          this.render();
          this.animateBar();
          this.emit("deactivated", {});
        }
      }
      // ── Event Emitter ─────────────────────────────────────────
      emit(name, detail) {
        this.el.dispatchEvent(
          new CustomEvent(`atmx:${name}`, { detail, bubbles: true, composed: true })
        );
        const m = window.ATMX;
        if (m?._cbs[name]) {
          for (const fn of m._cbs[name]) fn(detail);
        }
      }
      // ── Public API ────────────────────────────────────────────
      getContract() {
        return this.contract;
      }
      getRisk() {
        return this.risk;
      }
      getState() {
        return this.state;
      }
    }
    class ATMXManager {
      constructor() {
        this._widgets = /* @__PURE__ */ new Map();
        this._cbs = {};
      }
      mount(el) {
        const id = el.id || `atmx-${this._widgets.size}`;
        if (!el.id) el.id = id;
        const w = new ATMXWidget(el);
        this._widgets.set(id, w);
        return w;
      }
      get(id) {
        return this._widgets.get(id);
      }
      on(event, fn) {
        var _a;
        ((_a = this._cbs)[event] || (_a[event] = [])).push(fn);
        return this;
      }
      off(event, fn) {
        if (this._cbs[event]) this._cbs[event] = this._cbs[event].filter((f) => f !== fn);
        return this;
      }
    }
    const mgr = new ATMXManager();
    window.ATMX = mgr;
    function boot() {
      document.querySelectorAll(SELECTOR).forEach((el) => {
        if (!el.shadowRoot) mgr.mount(el);
      });
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot);
    } else {
      boot();
    }
  })();
})();

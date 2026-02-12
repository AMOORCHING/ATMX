import { useState, useCallback, useRef } from "react";
import WeatherMap, { type TradeFlash } from "./components/WeatherMap";
import MarketPanel from "./components/MarketPanel";
import HedgingTool from "./components/HedgingTool";
import { useMarkets } from "./hooks/useMarkets";
import { useWebSocket } from "./hooks/useWebSocket";
import type { WSMessage, TradeResponse } from "./types";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

type PanelMode = "markets" | "hedge";

function App() {
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [panelMode, setPanelMode] = useState<PanelMode>("markets");
  const [tradeFlashes, setTradeFlashes] = useState<TradeFlash[]>([]);
  const [highlightCells, setHighlightCells] = useState<string[]>([]);

  const { markets, loading, isDemo, updateMarketPrice, refetch } =
    useMarkets();

  // Track flash counter for unique keys.
  const flashKeyRef = useRef(0);

  // ── WebSocket handler ───────────────────────────────────────────────────
  const handleWSMessage = useCallback(
    (msg: WSMessage) => {
      if (msg.type === "trade_executed" || msg.type === "price_update") {
        // Update market prices.
        if (msg.price_yes && msg.price_no) {
          updateMarketPrice(msg.market_id, msg.price_yes, msg.price_no);
        }

        // Trigger trade flash animation on the map.
        if (msg.h3_cell_id) {
          flashKeyRef.current++;
          setTradeFlashes((prev) => [
            ...prev.slice(-10), // Keep last 10 flashes.
            {
              h3CellId: msg.h3_cell_id,
              timestamp: flashKeyRef.current,
              side: msg.side || "YES",
            },
          ]);
        }
      }
    },
    [updateMarketPrice]
  );

  const { connected } = useWebSocket(handleWSMessage);

  // ── Trade completion handler ────────────────────────────────────────────
  const handleTradeComplete = useCallback(
    (_res: TradeResponse) => {
      refetch();
    },
    [refetch]
  );

  // ── Hedging tool cell highlight ─────────────────────────────────────────
  const handleHighlightCells = useCallback((cells: string[]) => {
    setHighlightCells(cells);
  }, []);

  return (
    <div className="app">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-left">
          <h1 className="logo">atmx</h1>
          <span className="tagline">Weather Derivative Markets</span>
        </div>
        <div className="header-center">
          <button
            className={`nav-tab ${panelMode === "markets" ? "active" : ""}`}
            onClick={() => setPanelMode("markets")}
          >
            Markets
          </button>
          <button
            className={`nav-tab ${panelMode === "hedge" ? "active" : ""}`}
            onClick={() => setPanelMode("hedge")}
          >
            Hedge
          </button>
        </div>
        <div className="header-right">
          <div className={`ws-status ${connected ? "connected" : ""}`}>
            <span className="ws-dot" />
            {connected ? "Live" : "Offline"}
          </div>
          {isDemo && <span className="demo-badge">Demo</span>}
          {loading && <span className="loading-badge">Loading...</span>}
        </div>
      </header>

      {/* ── Main content ────────────────────────────────────────────────── */}
      <main className="app-main">
        <WeatherMap
          markets={markets}
          selectedCell={selectedCell}
          onCellSelect={(cell) => {
            setSelectedCell(cell);
            if (cell) setPanelMode("markets");
          }}
          tradeFlashes={tradeFlashes}
          highlightCells={highlightCells}
        />

        {panelMode === "markets" ? (
          <MarketPanel
            markets={markets}
            selectedCell={selectedCell}
            onTradeComplete={handleTradeComplete}
          />
        ) : (
          <aside className="market-panel">
            <HedgingTool
              markets={markets}
              mapboxToken={MAPBOX_TOKEN}
              onHighlightCells={handleHighlightCells}
              onClose={() => setPanelMode("markets")}
            />
          </aside>
        )}
      </main>

    </div>
  );
}

export default App;

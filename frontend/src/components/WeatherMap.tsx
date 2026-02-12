import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapGL, {
  Source,
  Layer,
  NavigationControl,
  type MapLayerMouseEvent,
  type MapRef,
} from "react-map-gl";
import { latLngToCell, cellToBoundary } from "h3-js";
import type { Market } from "../types";

interface WeatherMapProps {
  markets: Market[];
  selectedCell: string | null;
  onCellSelect: (cellId: string | null) => void;
  tradeFlashes: TradeFlash[];
  highlightCells?: string[];
}

export interface TradeFlash {
  h3CellId: string;
  timestamp: number;
  side: string;
}

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";
const H3_RESOLUTION = 7;

// NOAA NEXRAD radar composite tiles from Iowa Environmental Mesonet.
const RADAR_TILES = [
  "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png",
];

/**
 * Convert probability (0–1) to a hex color from green → yellow → red.
 */
function probToColor(prob: number): string {
  const p = Math.max(0, Math.min(1, prob));
  if (p < 0.5) {
    // Green → Yellow
    const r = Math.round(34 + 221 * (p * 2));
    return `rgb(${r}, 197, 94)`;
  }
  // Yellow → Red
  const g = Math.round(197 * (1 - (p - 0.5) * 2));
  return `rgb(239, ${g}, 68)`;
}

/**
 * Convert H3 cell boundary to GeoJSON ring coordinates.
 * h3-js returns [lat, lng] pairs; GeoJSON needs [lng, lat].
 */
function cellToGeoJSONRing(cellId: string): number[][] {
  const boundary = cellToBoundary(cellId);
  const coords = boundary.map(([lat, lng]) => [lng, lat]);
  coords.push(coords[0]); // Close the ring.
  return coords;
}

export default function WeatherMap({
  markets,
  selectedCell,
  onCellSelect,
  tradeFlashes,
  highlightCells = [],
}: WeatherMapProps) {
  const mapRef = useRef<MapRef>(null);
  const [activeFlashes, setActiveFlashes] = useState<
    { cellId: string; opacity: number; key: number }[]
  >([]);

  // ── Group markets by H3 cell ──────────────────────────────────────────────
  const cellData = useMemo(() => {
    const cells = new Map<
      string,
      { maxProb: number; marketCount: number }
    >();
    for (const market of markets) {
      if (!market.h3_cell_id) continue;
      const prob = parseFloat(market.price_yes) || 0.5;
      const existing = cells.get(market.h3_cell_id);
      if (existing) {
        existing.maxProb = Math.max(existing.maxProb, prob);
        existing.marketCount++;
      } else {
        cells.set(market.h3_cell_id, { maxProb: prob, marketCount: 1 });
      }
    }
    return cells;
  }, [markets]);

  // ── Layer 2: H3 Grid GeoJSON ──────────────────────────────────────────────
  const h3GeoJSON = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    for (const [cellId, data] of cellData) {
      try {
        features.push({
          type: "Feature",
          properties: {
            cellId,
            color: probToColor(data.maxProb),
            prob: data.maxProb,
            marketCount: data.marketCount,
            isSelected: cellId === selectedCell,
          },
          geometry: {
            type: "Polygon",
            coordinates: [cellToGeoJSONRing(cellId)],
          },
        });
      } catch {
        // Skip cells with invalid H3 indices.
      }
    }
    return { type: "FeatureCollection" as const, features };
  }, [cellData, selectedCell]);

  // ── Layer 3: Trade Flash Animation ────────────────────────────────────────
  useEffect(() => {
    if (tradeFlashes.length === 0) return;
    const latest = tradeFlashes[tradeFlashes.length - 1];

    setActiveFlashes((prev) => [
      ...prev,
      { cellId: latest.h3CellId, opacity: 0.85, key: latest.timestamp },
    ]);

    // Fade out over 1.5s.
    const fadeInterval = setInterval(() => {
      setActiveFlashes((prev) =>
        prev
          .map((f) =>
            f.key === latest.timestamp
              ? { ...f, opacity: f.opacity - 0.12 }
              : f
          )
          .filter((f) => f.opacity > 0)
      );
    }, 150);

    const cleanup = setTimeout(() => {
      clearInterval(fadeInterval);
      setActiveFlashes((prev) =>
        prev.filter((f) => f.key !== latest.timestamp)
      );
    }, 1600);

    return () => {
      clearInterval(fadeInterval);
      clearTimeout(cleanup);
    };
  }, [tradeFlashes]);

  const flashGeoJSON = useMemo(() => {
    const features: GeoJSON.Feature[] = [];
    for (const flash of activeFlashes) {
      try {
        features.push({
          type: "Feature",
          properties: { opacity: flash.opacity },
          geometry: {
            type: "Polygon",
            coordinates: [cellToGeoJSONRing(flash.cellId)],
          },
        });
      } catch {
        // Skip.
      }
    }
    return { type: "FeatureCollection" as const, features };
  }, [activeFlashes]);

  // ── Layer 4: Hedging Tool Highlight Overlay ────────────────────────────────
  const highlightGeoJSON = useMemo(() => {
    if (highlightCells.length === 0) {
      return { type: "FeatureCollection" as const, features: [] as GeoJSON.Feature[] };
    }
    const features: GeoJSON.Feature[] = [];
    for (const cellId of highlightCells) {
      try {
        features.push({
          type: "Feature",
          properties: { cellId },
          geometry: {
            type: "Polygon",
            coordinates: [cellToGeoJSONRing(cellId)],
          },
        });
      } catch {
        // Skip invalid cells.
      }
    }
    return { type: "FeatureCollection" as const, features };
  }, [highlightCells]);

  // ── Click handler: determine H3 cell ──────────────────────────────────────
  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      // Check if clicked on an H3 polygon feature.
      const features = event.features;
      if (features?.length) {
        const cellId = features[0].properties?.cellId;
        if (cellId) {
          onCellSelect(cellId);
          return;
        }
      }

      // Convert click lat/lng to H3 cell.
      try {
        const { lng, lat } = event.lngLat;
        const cell = latLngToCell(lat, lng, H3_RESOLUTION);
        onCellSelect(cellData.has(cell) ? cell : null);
      } catch {
        onCellSelect(null);
      }
    },
    [onCellSelect, cellData]
  );

  return (
    <div className="map-container">
      <MapGL
        ref={mapRef}
        initialViewState={{
          longitude: -95.7,
          latitude: 37.0,
          zoom: 4.2,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
        onClick={handleClick}
        interactiveLayerIds={["h3-fill"]}
      >
        <NavigationControl position="top-right" />

        {/* ── Layer 1: NOAA Radar Precipitation ─────────────────────────── */}
        <Source id="radar" type="raster" tiles={RADAR_TILES} tileSize={256}>
          <Layer
            id="radar-layer"
            type="raster"
            paint={{
              "raster-opacity": 0.5,
              "raster-fade-duration": 300,
            }}
          />
        </Source>

        {/* ── Layer 2: H3 Grid Heatmap ──────────────────────────────────── */}
        <Source id="h3-grid" type="geojson" data={h3GeoJSON}>
          <Layer
            id="h3-fill"
            type="fill"
            paint={{
              "fill-color": ["get", "color"],
              "fill-opacity": [
                "case",
                ["==", ["get", "isSelected"], true],
                0.65,
                0.35,
              ],
            }}
          />
          <Layer
            id="h3-outline"
            type="line"
            paint={{
              "line-color": [
                "case",
                ["==", ["get", "isSelected"], true],
                "#ffffff",
                ["get", "color"],
              ],
              "line-width": [
                "case",
                ["==", ["get", "isSelected"], true],
                2.5,
                1,
              ],
              "line-opacity": 0.85,
            }}
          />
        </Source>

        {/* ── Layer 3: Trade Flash Animation ────────────────────────────── */}
        <Source id="trade-flash" type="geojson" data={flashGeoJSON}>
          <Layer
            id="flash-fill"
            type="fill"
            paint={{
              "fill-color": "#ffffff",
              "fill-opacity": ["get", "opacity"],
            }}
          />
        </Source>

        {/* ── Layer 4: Hedging Tool Coverage Overlay ──────────────────── */}
        {highlightCells.length > 0 && (
          <Source id="hedge-highlight" type="geojson" data={highlightGeoJSON}>
            <Layer
              id="hedge-fill"
              type="fill"
              paint={{
                "fill-color": "#60a5fa",
                "fill-opacity": 0.25,
              }}
            />
            <Layer
              id="hedge-outline"
              type="line"
              paint={{
                "line-color": "#3b82f6",
                "line-width": 2,
                "line-dasharray": [2, 2],
                "line-opacity": 0.8,
              }}
            />
          </Source>
        )}
      </MapGL>

      {/* ── Map Legend ────────────────────────────────────────────────────── */}
      <div className="map-legend">
        <div className="legend-title">Market Probability</div>
        <div className="legend-gradient">
          <div className="legend-bar" />
          <div className="legend-labels">
            <span>Low</span>
            <span>High</span>
          </div>
        </div>
      </div>

      {/* ── Radar attribution ────────────────────────────────────────────── */}
      <div className="radar-badge">NEXRAD Radar</div>
    </div>
  );
}

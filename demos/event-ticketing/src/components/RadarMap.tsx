import { useRef, useEffect, useState, useCallback } from "react";
import Map, { Source, Layer, Marker, NavigationControl } from "react-map-gl";
import type { MapRef } from "react-map-gl";
import type { PurchasedProtection } from "../types";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

const NEXRAD_TILES = [
  "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png",
];

interface RadarMapProps {
  protections: PurchasedProtection[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  height?: number;
}

export default function RadarMap({
  protections,
  selectedId,
  onSelect,
  height = 400,
}: RadarMapProps) {
  const mapRef = useRef<MapRef>(null);
  const [mapReady, setMapReady] = useState(false);

  const selected = protections.find((p) => p.contract.contract_id === selectedId);

  const flyTo = useCallback(
    (lat: number, lng: number) => {
      if (!mapRef.current || !mapReady) return;
      mapRef.current.flyTo({ center: [lng, lat], zoom: 9, duration: 1200 });
    },
    [mapReady],
  );

  useEffect(() => {
    if (selected) flyTo(selected.event.lat, selected.event.lng);
  }, [selected, flyTo]);

  if (!MAPBOX_TOKEN) {
    return (
      <div className="radar-map radar-map--placeholder" style={{ height }}>
        <div className="radar-map__empty">
          <span className="radar-map__empty-icon">🛰️</span>
          <p>Set <code>VITE_MAPBOX_TOKEN</code> to enable the NEXRAD radar map</p>
        </div>
      </div>
    );
  }

  const center = selected
    ? { longitude: selected.event.lng, latitude: selected.event.lat, zoom: 9 }
    : { longitude: -98.5, latitude: 39.8, zoom: 3.5 };

  return (
    <div className="radar-map" style={{ height }}>
      <Map
        ref={mapRef}
        initialViewState={center}
        mapboxAccessToken={MAPBOX_TOKEN}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        style={{ width: "100%", height: "100%" }}
        onLoad={() => setMapReady(true)}
      >
        <NavigationControl position="top-right" />

        <Source type="raster" tiles={NEXRAD_TILES} tileSize={256}>
          <Layer
            id="nexrad-radar"
            type="raster"
            paint={{ "raster-opacity": 0.5, "raster-fade-duration": 300 }}
          />
        </Source>

        {protections.map((p) => (
          <Marker
            key={p.contract.contract_id}
            longitude={p.event.lng}
            latitude={p.event.lat}
            anchor="center"
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              onSelect?.(p.contract.contract_id);
            }}
          >
            <div
              className={`radar-marker ${
                p.contract.contract_id === selectedId ? "radar-marker--active" : ""
              }`}
            >
              <span>{p.event.emoji}</span>
            </div>
          </Marker>
        ))}
      </Map>

      <div className="radar-map__badge">
        <span className="radar-map__badge-dot" />
        NEXRAD Radar
      </div>
    </div>
  );
}

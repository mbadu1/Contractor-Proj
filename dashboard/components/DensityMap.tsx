"use client";

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import type { CityDensity } from "@/lib/types";
import { fmtUsd } from "@/lib/format";
import "leaflet/dist/leaflet.css";

function FitBounds({ cities }: { cities: CityDensity[] }) {
  const map = useMap();
  useEffect(() => {
    if (!cities.length) return;
    const lats = cities.map((c) => c.latitude);
    const lons = cities.map((c) => c.longitude);
    map.fitBounds(
      [
        [Math.min(...lats) - 1, Math.min(...lons) - 1],
        [Math.max(...lats) + 1, Math.max(...lons) + 1],
      ],
      { padding: [24, 24] }
    );
  }, [cities, map]);
  return null;
}

export function DensityMap({ cities }: { cities: CityDensity[] }) {
  const maxBiz = useMemo(
    () => Math.max(...cities.map((c) => c.business_count), 1),
    [cities]
  );

  if (!cities.length) {
    return <div className="flex h-80 items-center justify-center text-sm text-mist-400">No city data</div>;
  }

  return (
    <div className="h-80 w-full overflow-hidden rounded-md border border-ink-600">
      <MapContainer
        center={[39.8, -98.5]}
        zoom={4}
        className="h-full w-full"
        scrollWheelZoom={false}
        style={{ background: "#0c1017" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <FitBounds cities={cities} />
        {cities.map((c) => {
          const radius = 6 + (c.business_count / maxBiz) * 18;
          return (
            <CircleMarker
              key={c.city}
              center={[c.latitude, c.longitude]}
              radius={radius}
              pathOptions={{
                color: "#5eb0ff",
                fillColor: "#3d9cf0",
                fillOpacity: 0.55,
                weight: 1,
              }}
            >
              <Popup>
                <div className="text-sm">
                  <strong>{c.city}</strong>
                  <div>{c.business_count} businesses</div>
                  <div>{fmtUsd(c.total_revenue, true)} est. revenue</div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}

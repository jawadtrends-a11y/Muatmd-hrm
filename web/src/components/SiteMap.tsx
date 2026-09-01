"use client";

/**
 * خريطة تحديد موقع العمل (ق-62).
 *
 * MapLibre + OpenStreetMap — مجانية بلا مفتاح ولا عقد.
 * (Google لا تبيع مباشرةً في السعودية، والتعاقد عبر موزّع
 * يحتاج أيامًا.)
 *
 * **المنطق معزول عن الخريطة:** البصمة تحسب المسافة رياضيًا،
 * فالانتقال لمزوّد آخر يمسّ هذا الملف وحده.
 */
import { useEffect, useRef, useState } from "react";

type Props = {
  latitude: number | null;
  longitude: number | null;
  radius: number;                       // نصف القطر + الهامش، بالمتر
  onPick: (lat: number, lng: number) => void;
  height?: number;
  readOnly?: boolean;
};

// مركز السعودية — نقطة البداية حين لا إحداثيات
const DEFAULT_CENTER: [number, number] = [45.0, 24.0];
const DEFAULT_ZOOM = 5;

/** دائرة النطاق كـGeoJSON — 64 نقطة تكفي لدائرة ناعمة */
function circleGeoJSON(lat: number, lng: number, meters: number) {
  const points: [number, number][] = [];
  const km = meters / 1000;
  const dx = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  const dy = km / 110.574;

  for (let i = 0; i < 64; i++) {
    const t = (i / 64) * 2 * Math.PI;
    points.push([lng + dx * Math.cos(t), lat + dy * Math.sin(t)]);
  }
  points.push(points[0]);

  return {
    type: "Feature" as const,
    properties: {},
    geometry: { type: "Polygon" as const, coordinates: [points] },
  };
}

export default function SiteMap({
  latitude, longitude, radius, onPick, height = 380, readOnly,
}: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markerRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [locating, setLocating] = useState(false);

  // ── إنشاء الخريطة مرة واحدة ──
  useEffect(() => {
    if (!boxRef.current || mapRef.current) return;

    let cancelled = false;

    (async () => {
      // v6 تصدّر الوحدة مباشرةً بلا default
      const maplibregl = await import("maplibre-gl");
      await import("maplibre-gl/dist/maplibre-gl.css");
      if (cancelled || !boxRef.current) return;

      const map = new maplibregl.Map({
        container: boxRef.current,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap",
            },
          },
          layers: [{ id: "osm", type: "raster", source: "osm" }],
        },
        center: (latitude != null && longitude != null)
          ? [longitude, latitude] : DEFAULT_CENTER,
        zoom: (latitude != null && longitude != null) ? 16 : DEFAULT_ZOOM,
      });

      map.addControl(new maplibregl.NavigationControl(), "top-left");

      map.on("load", () => {
        if (cancelled) return;

        map.addSource("fence", {
          type: "geojson",
          data: (latitude != null && longitude != null)
            ? circleGeoJSON(latitude, longitude, radius)
            : { type: "FeatureCollection", features: [] },
        });

        map.addLayer({
          id: "fence-fill", type: "fill", source: "fence",
          paint: { "fill-color": "#0E7C86", "fill-opacity": 0.18 },
        });
        map.addLayer({
          id: "fence-line", type: "line", source: "fence",
          paint: { "line-color": "#0E7C86", "line-width": 2 },
        });

        setReady(true);
      });

      if (!readOnly) {
        map.on("click", (e: { lngLat: { lat: number; lng: number } }) => {
          onPick(
            Number(e.lngLat.lat.toFixed(7)),
            Number(e.lngLat.lng.toFixed(7)));
        });
        map.getCanvas().style.cursor = "crosshair";
      }

      mapRef.current = { map, maplibregl };
    })();

    return () => {
      cancelled = true;
      if (mapRef.current?.map) {
        mapRef.current.map.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── تحديث العلامة والدائرة ──
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const { map, maplibregl } = mapRef.current;

    if (latitude == null || longitude == null) {
      markerRef.current?.remove();
      markerRef.current = null;
      map.getSource("fence")?.setData(
        { type: "FeatureCollection", features: [] });
      return;
    }

    if (markerRef.current) {
      markerRef.current.setLngLat([longitude, latitude]);
    } else {
      markerRef.current = new maplibregl.Marker({ color: "#0E7C86" })
        .setLngLat([longitude, latitude])
        .addTo(map);
    }

    map.getSource("fence")?.setData(
      circleGeoJSON(latitude, longitude, radius));
  }, [ready, latitude, longitude, radius]);

  // ── التقريب عند تغيّر الموقع من الحقول ──
  useEffect(() => {
    if (!ready || !mapRef.current || latitude == null || longitude == null) {
      return;
    }
    const { map } = mapRef.current;
    if (map.getZoom() < 12) {
      map.flyTo({ center: [longitude, latitude], zoom: 16 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, latitude, longitude]);

  function useMyLocation() {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onPick(
          Number(pos.coords.latitude.toFixed(7)),
          Number(pos.coords.longitude.toFixed(7)));
        mapRef.current?.map.flyTo({
          center: [pos.coords.longitude, pos.coords.latitude], zoom: 17,
        });
        setLocating(false);
      },
      () => setLocating(false),
      { enableHighAccuracy: true, timeout: 10000 });
  }

  return (
    <div style={{ position: "relative" }}>
      <div ref={boxRef} style={{
        height, width: "100%", borderRadius: "var(--radius-sm)",
        overflow: "hidden", border: "1px solid var(--line)",
        background: "var(--paper-2)",
      }} />

      {!readOnly && (
        <button
          type="button"
          className="btn btn-sm"
          onClick={useMyLocation}
          disabled={locating}
          style={{
            position: "absolute", top: 10, insetInlineEnd: 10, zIndex: 5,
            background: "var(--paper)", boxShadow: "var(--shadow-sm)",
          }}
        >
          {locating ? "جارٍ التحديد…" : "موقعي الحالي"}
        </button>
      )}

      {!readOnly && (
        <div className="muted" style={{ fontSize: ".82rem", marginTop: 6 }}>
          اضغط على الخريطة لتحديد مركز الموقع، أو استخدم «موقعي الحالي»
        </div>
      )}
    </div>
  );
}

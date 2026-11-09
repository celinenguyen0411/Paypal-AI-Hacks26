import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { Polygon } from "geojson";
import type { MapRef } from "react-map-gl/mapbox";
import { TerraDraw, TerraDrawPolygonMode } from "terra-draw";
import { TerraDrawMapboxGLAdapter } from "terra-draw-mapbox-gl-adapter";

export function useZoneDrawing(mapRef: RefObject<MapRef | null>, active: boolean) {
  const [zone, setZone] = useState<Polygon | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);

  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!active || !map) return;
    const draw = new TerraDraw({
      adapter: new TerraDrawMapboxGLAdapter({ map }),
      modes: [new TerraDrawPolygonMode()],
    });
    const begin = () => {
      draw.start();
      draw.setMode("polygon");
      draw.on("finish", (id) => {
        const finished = draw.getSnapshot().find((feature) => feature.id === id);
        if (finished?.geometry.type === "Polygon") setZone(finished.geometry as Polygon);
        draw.setMode("static");
      });
      drawRef.current = draw;
    };
    if (map.isStyleLoaded()) begin();
    else map.once("idle", begin);
    return () => {
      map.off("idle", begin);
      if (drawRef.current === draw) {
        draw.stop();
        drawRef.current = null;
      }
      setZone(null);
    };
  }, [active, mapRef]);

  const redraw = useCallback(() => {
    setZone(null);
    drawRef.current?.clear();
    drawRef.current?.setMode("polygon");
  }, []);

  return { zone, redraw };
}

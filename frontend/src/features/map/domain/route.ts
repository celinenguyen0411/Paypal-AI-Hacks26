export type Coordinate = [number, number];
export type Bounds = [Coordinate, Coordinate];

const MADISON_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Chicago",
  hour: "numeric",
  minute: "2-digit",
});

export function minutesLabel(seconds: number): string {
  const minutes = seconds / 60;
  return minutes < 10 ? `${minutes.toFixed(1)} min` : `${Math.round(minutes)} min`;
}

export function formatClock(isoTime: string): string {
  return MADISON_TIME.format(new Date(isoTime)).replace(/ /g, " ");
}

export function boundsOf(coordinates: Coordinate[]): Bounds {
  const longitudes = coordinates.map(([lng]) => lng);
  const latitudes = coordinates.map(([, lat]) => lat);
  return [
    [Math.min(...longitudes), Math.min(...latitudes)],
    [Math.max(...longitudes), Math.max(...latitudes)],
  ];
}

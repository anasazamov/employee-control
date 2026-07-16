import type { Feature, Polygon } from 'geojson'

/**
 * Berilgan markaz (lon, lat) va radius (metr) atrofida taxminiy aylana-poligon.
 * Geofence doiralarini MapLibre'da fill/line qatlam sifatida chizish uchun.
 */
export function circlePolygon(
  lon: number,
  lat: number,
  radiusM: number,
  steps = 64,
): Feature<Polygon> {
  const coords: [number, number][] = []
  const earth = 6378137
  const dLat = (radiusM / earth) * (180 / Math.PI)
  const dLon = dLat / Math.cos((lat * Math.PI) / 180)
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * 2 * Math.PI
    coords.push([lon + dLon * Math.cos(theta), lat + dLat * Math.sin(theta)])
  }
  return {
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [coords] },
  }
}

export type MarkerStatus = 'on_site' | 'moving' | 'stale'

/** ts qadimiyligiga qarab nuqta "eskirgan" (stale) deb hisoblanadi. */
export const STALE_AFTER_MS = 5 * 60 * 1000

export function markerStatus(
  siteId: string | null,
  ts: string,
  now = Date.now(),
): MarkerStatus {
  const age = now - new Date(ts).getTime()
  if (Number.isFinite(age) && age > STALE_AFTER_MS) return 'stale'
  if (siteId) return 'on_site'
  return 'moving'
}

export const STATUS_COLOR: Record<MarkerStatus, string> = {
  on_site: '#52c41a', // yashil — obyekt ichida
  moving: '#1677ff', // ko'k — harakatda
  stale: '#8c8c8c', // kulrang — eskirgan signal
}

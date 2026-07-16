import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

// Placeholder basemap. Productionda self-hosted Martin tile-server ishlatiladi
// (O'zbekiston OSM-extract'idan Planetiler bilan generatsiya qilingan vector-tile'lar,
// docs/PLAN.md §11) — style URL shu konstantada almashtiriladi.
const MAP_STYLE_URL = 'https://demotiles.maplibre.org/style.json'

/** Toshkent markazi [lng, lat]. */
const TASHKENT_CENTER: [number, number] = [69.2797, 41.3111]
const DEFAULT_ZOOM = 11

export function LiveMap() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: TASHKENT_CENTER,
      zoom: DEFAULT_ZOOM,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    return () => {
      map.remove()
    }
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ flex: 1, width: '100%', height: '100%', minHeight: 400 }}
    />
  )
}

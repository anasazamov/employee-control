import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { App, Tag } from 'antd'
import type { FeatureCollection } from 'geojson'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  departmentsApi,
  sitesApi,
  usersApi,
} from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { LivePoint, WsCheckin } from '../../shared/api/types'
import {
  useLiveLocations,
  type LiveStatus,
} from '../../shared/live/useLiveLocations'
import {
  STATUS_COLOR,
  circlePolygon,
  markerStatus,
} from '../../shared/map/geo'
import { DEFAULT_ZOOM, MAP_STYLE_URL, TASHKENT_CENTER } from '../../shared/map/style'
import { FilterPanel, type LiveFilters } from './FilterPanel'

const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] }

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[
        c
      ] ?? c,
  )
}

function makeDot(color: string): HTMLDivElement {
  const el = document.createElement('div')
  el.style.cssText = `width:16px;height:16px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,0.4);cursor:pointer;`
  return el
}

function makeBadge(count: number): HTMLDivElement {
  const el = document.createElement('div')
  el.style.cssText =
    'min-width:20px;height:20px;padding:0 6px;border-radius:10px;background:#1677ff;color:#fff;font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;box-shadow:0 0 4px rgba(0,0,0,0.4);'
  el.textContent = String(count)
  return el
}

const STATUS_TAG_COLOR: Record<LiveStatus, string> = {
  connecting: 'orange',
  live: 'green',
  polling: 'gold',
  offline: 'default',
}

export function LiveMap() {
  const { t } = useTranslation()
  const { notification } = App.useApp()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const empMarkers = useRef<Map<string, maplibregl.Marker>>(new Map())
  const siteMarkers = useRef<Map<string, maplibregl.Marker>>(new Map())

  const [filters, setFilters] = useState<LiveFilters>({
    departmentIds: [],
    userIds: [],
    statuses: ['on_site', 'moving', 'stale'],
  })

  const { data: sites = [] } = useQuery({
    queryKey: qk.sites,
    queryFn: sitesApi.list,
  })
  const { data: departments = [] } = useQuery({
    queryKey: qk.departments,
    queryFn: departmentsApi.list,
  })
  const { data: users = [] } = useQuery({
    queryKey: qk.users(),
    queryFn: () => usersApi.list(),
  })

  const userMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const u of users) m[u.id] = u.full_name
    return m
  }, [users])
  const userDeptMap = useMemo(() => {
    const m: Record<string, string | null> = {}
    for (const u of users) m[u.id] = u.department_id
    return m
  }, [users])
  const siteNameMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const s of sites) m[s.id] = s.name
    return m
  }, [sites])

  const onCheckin = useCallback(
    (msg: WsCheckin) => {
      const name = userMap[msg.user_id] ?? msg.user_id
      const site = msg.site_id ? (siteNameMap[msg.site_id] ?? msg.site_id) : '—'
      notification.info({
        message: t('map.checkinNotify', { name }),
        description: `${t('sites.name')}: ${site} · ${t('review.risk')}: ${msg.risk_score}`,
        placement: 'bottomRight',
      })
    },
    [notification, userMap, siteNameMap, t],
  )

  const { points, occupancy, status } = useLiveLocations({ onCheckin })

  // --- Xaritani bir marta yaratamiz ---
  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: TASHKENT_CENTER,
      zoom: DEFAULT_ZOOM,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => {
      map.addSource('geofences', { type: 'geojson', data: EMPTY_FC })
      map.addLayer({
        id: 'geofence-fill',
        type: 'fill',
        source: 'geofences',
        paint: { 'fill-color': '#1677ff', 'fill-opacity': 0.08 },
      })
      map.addLayer({
        id: 'geofence-line',
        type: 'line',
        source: 'geofences',
        paint: { 'line-color': '#1677ff', 'line-width': 2, 'line-opacity': 0.5 },
      })
      setMapReady(true)
    })

    const emp = empMarkers.current
    const st = siteMarkers.current
    return () => {
      emp.forEach((m) => m.remove())
      emp.clear()
      st.forEach((m) => m.remove())
      st.clear()
      map.remove()
      mapRef.current = null
      setMapReady(false)
    }
  }, [])

  // --- Geofence doiralari (faqat sites o'zgarganda) ---
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const fc: FeatureCollection = {
      type: 'FeatureCollection',
      features: sites.map((s) => ({
        ...circlePolygon(s.lon, s.lat, s.radius_m),
        properties: { id: s.id, name: s.name },
      })),
    }
    const src = map.getSource('geofences') as maplibregl.GeoJSONSource | undefined
    src?.setData(fc)
  }, [sites, mapReady])

  // --- Obyekt band-badge'lari (sites + occupancy) ---
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const seen = new Set<string>()
    for (const s of sites) {
      seen.add(s.id)
      const count = occupancy[s.id] ?? 0
      const existing = siteMarkers.current.get(s.id)
      if (existing) {
        existing.getElement().textContent = String(count)
      } else {
        const marker = new maplibregl.Marker({ element: makeBadge(count) })
          .setLngLat([s.lon, s.lat])
          .addTo(map)
        siteMarkers.current.set(s.id, marker)
      }
    }
    for (const [id, marker] of siteMarkers.current) {
      if (!seen.has(id)) {
        marker.remove()
        siteMarkers.current.delete(id)
      }
    }
  }, [sites, occupancy, mapReady])

  // --- Xodim markerlari (points + filtrlar) ---
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const now = Date.now()

    const isVisible = (p: LivePoint): boolean => {
      const st = markerStatus(p.site_id, p.ts, now)
      if (!filters.statuses.includes(st)) return false
      if (filters.userIds.length > 0 && !filters.userIds.includes(p.user_id)) {
        return false
      }
      if (filters.departmentIds.length > 0) {
        const dept = userDeptMap[p.user_id]
        if (!dept || !filters.departmentIds.includes(dept)) return false
      }
      return true
    }

    const seen = new Set<string>()
    for (const p of points) {
      if (!isVisible(p)) continue
      seen.add(p.user_id)
      const st = markerStatus(p.site_id, p.ts, now)
      const color = STATUS_COLOR[st]
      const name = userMap[p.user_id] ?? p.user_id
      const html = `<div style="font-size:12px"><b>${escapeHtml(name)}</b><br/>${t(
        `map.statusLabel.${st}`,
      )}<br/>${t('map.battery')}: ${p.battery ?? '—'}%<br/>${t(
        'map.lastSeen',
      )}: ${new Date(p.ts).toLocaleTimeString()}</div>`

      let marker = empMarkers.current.get(p.user_id)
      if (!marker) {
        marker = new maplibregl.Marker({ element: makeDot(color) })
          .setLngLat([p.lon, p.lat])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(html))
          .addTo(map)
        empMarkers.current.set(p.user_id, marker)
      } else {
        marker.setLngLat([p.lon, p.lat])
        marker.getElement().style.background = color
        marker.getPopup()?.setHTML(html)
      }
    }
    for (const [id, marker] of empMarkers.current) {
      if (!seen.has(id)) {
        marker.remove()
        empMarkers.current.delete(id)
      }
    }
  }, [points, filters, mapReady, userMap, userDeptMap, t])

  return (
    <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 400 }}>
      <FilterPanel
        departments={departments}
        users={users}
        value={filters}
        onChange={setFilters}
      />
      <div style={{ flex: 1, position: 'relative', minHeight: 400 }}>
        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
        <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}>
          <Tag color={STATUS_TAG_COLOR[status]}>{t(`map.conn.${status}`)}</Tag>
        </div>
      </div>
    </div>
  )
}

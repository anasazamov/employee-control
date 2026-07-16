import { useEffect, useMemo, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  PauseOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Empty,
  Select,
  Slider,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { FeatureCollection } from 'geojson'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { employeesApi, usersApi } from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type {
  CheckinVerdict,
  TimelineSegment,
  TrackGap,
  TrackPoint,
} from '../../shared/api/types'
import {
  DEFAULT_ZOOM,
  MAP_STYLE_URL,
  TASHKENT_CENTER,
} from '../../shared/map/style'

const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] }

const VERDICT_COLOR: Record<CheckinVerdict, string> = {
  pending: '#faad14',
  verified: '#52c41a',
  flagged: '#fa541c',
  rejected: '#cf1322',
}

function makeMarkerEl(color: string, size = 14, square = false): HTMLDivElement {
  const el = document.createElement('div')
  el.style.cssText = `width:${size}px;height:${size}px;border-radius:${
    square ? '3px' : '50%'
  };background:${color};border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,0.4);`
  return el
}

function formatDwell(seconds: number): string {
  const m = Math.round(seconds / 60)
  if (m < 60) return `${m}m`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}

function gapEndpoints(
  points: TrackPoint[],
  gap: TrackGap,
): [[number, number], [number, number]] | null {
  if (
    gap.from_lat != null &&
    gap.from_lon != null &&
    gap.to_lat != null &&
    gap.to_lon != null
  ) {
    return [
      [gap.from_lon, gap.from_lat],
      [gap.to_lon, gap.to_lat],
    ]
  }
  const start = gap.from_ts ?? gap.start_ts
  const end = gap.to_ts ?? gap.end_ts
  if (!start || !end || points.length === 0) return null
  const st = new Date(start).getTime()
  const et = new Date(end).getTime()
  let before: TrackPoint | undefined
  let after: TrackPoint | undefined
  for (const p of points) {
    const pt = new Date(p.ts).getTime()
    if (pt <= st) before = p
    if (pt >= et && !after) after = p
  }
  if (before && after) {
    return [
      [before.lon, before.lat],
      [after.lon, after.lat],
    ]
  }
  return null
}

export function HistoryPage() {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const overlayMarkers = useRef<maplibregl.Marker[]>([])
  const playMarker = useRef<maplibregl.Marker | null>(null)

  const [userId, setUserId] = useState<string | undefined>()
  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => [
    dayjs().startOf('day'),
    dayjs(),
  ])
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(false)

  const tsFrom = range[0].toISOString()
  const tsTo = range[1].toISOString()

  const { data: users = [] } = useQuery({
    queryKey: qk.users(),
    queryFn: () => usersApi.list(),
  })

  const trackQuery = useQuery({
    queryKey: userId ? qk.track(userId, tsFrom, tsTo) : ['track', 'none'],
    queryFn: () =>
      employeesApi.track(userId!, { ts_from: tsFrom, ts_to: tsTo }),
    enabled: !!userId,
  })
  const timelineQuery = useQuery({
    queryKey: userId ? qk.timeline(userId, tsFrom, tsTo) : ['timeline', 'none'],
    queryFn: () =>
      employeesApi.timeline(userId!, { ts_from: tsFrom, ts_to: tsTo }),
    enabled: !!userId,
  })

  const points = useMemo(() => {
    const list = trackQuery.data?.points ?? []
    return [...list].sort(
      (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
    )
  }, [trackQuery.data])

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
      map.addSource('track', { type: 'geojson', data: EMPTY_FC })
      map.addLayer({
        id: 'track-line',
        type: 'line',
        source: 'track',
        paint: { 'line-color': '#1677ff', 'line-width': 3, 'line-opacity': 0.8 },
      })
      map.addSource('gaps', { type: 'geojson', data: EMPTY_FC })
      map.addLayer({
        id: 'gap-line',
        type: 'line',
        source: 'gaps',
        paint: {
          'line-color': '#cf1322',
          'line-width': 3,
          'line-dasharray': [2, 2],
        },
      })
      setMapReady(true)
    })
    const overlays = overlayMarkers.current
    return () => {
      overlays.forEach((m) => m.remove())
      overlays.length = 0
      playMarker.current?.remove()
      playMarker.current = null
      map.remove()
      mapRef.current = null
      setMapReady(false)
    }
  }, [])

  // --- Track ma'lumoti chizish ---
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const data = trackQuery.data

    // polyline
    const lineFc: FeatureCollection = {
      type: 'FeatureCollection',
      features:
        points.length > 1
          ? [
              {
                type: 'Feature',
                properties: {},
                geometry: {
                  type: 'LineString',
                  coordinates: points.map((p) => [p.lon, p.lat]),
                },
              },
            ]
          : [],
    }
    ;(map.getSource('track') as maplibregl.GeoJSONSource | undefined)?.setData(
      lineFc,
    )

    // qizil bo'shliq segmentlari
    const gapFc: FeatureCollection = {
      type: 'FeatureCollection',
      features: (data?.gaps ?? [])
        .map((g) => gapEndpoints(points, g))
        .filter((seg): seg is [[number, number], [number, number]] => seg !== null)
        .map((seg) => ({
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates: seg },
        })),
    }
    ;(map.getSource('gaps') as maplibregl.GeoJSONSource | undefined)?.setData(
      gapFc,
    )

    // overlay markerlarni tozalaymiz
    overlayMarkers.current.forEach((m) => m.remove())
    overlayMarkers.current = []

    // to'xtash (stop) markerlari
    for (const s of data?.stops ?? []) {
      const dwell = s.dwell_seconds ? ` · ${formatDwell(s.dwell_seconds)}` : ''
      const marker = new maplibregl.Marker({
        element: makeMarkerEl('#fa8c16', 16, true),
      })
        .setLngLat([s.lon, s.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="font-size:12px"><b>${t('history.stop')}</b>${dwell}</div>`,
          ),
        )
        .addTo(map)
      overlayMarkers.current.push(marker)
    }

    // checkin pinlari
    for (const c of data?.checkins ?? []) {
      const marker = new maplibregl.Marker({
        element: makeMarkerEl(VERDICT_COLOR[c.verdict], 14),
      })
        .setLngLat([c.lon, c.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="font-size:12px"><b>${t('history.checkin')}</b><br/>${t(
              `verdict.${c.verdict}`,
            )} · ${t('review.risk')}: ${c.risk_score}</div>`,
          ),
        )
        .addTo(map)
      overlayMarkers.current.push(marker)
    }

    // animatsiya markeri (boshiga qo'yamiz)
    setFrame(0)
    setPlaying(false)
    if (points.length > 0) {
      const first = points[0]
      if (!playMarker.current) {
        playMarker.current = new maplibregl.Marker({
          element: makeMarkerEl('#722ed1', 20),
        })
          .setLngLat([first.lon, first.lat])
          .addTo(map)
      } else {
        playMarker.current.setLngLat([first.lon, first.lat])
      }
    } else {
      playMarker.current?.remove()
      playMarker.current = null
    }

    // fit bounds
    if (points.length > 0) {
      const bounds = new maplibregl.LngLatBounds()
      for (const p of points) bounds.extend([p.lon, p.lat])
      map.fitBounds(bounds, { padding: 60, maxZoom: 15, duration: 500 })
    }
  }, [trackQuery.data, points, mapReady, t])

  // --- Slayder kadrini animatsiya markeriga bog'laymiz ---
  useEffect(() => {
    if (!playMarker.current || points.length === 0) return
    const idx = Math.min(frame, points.length - 1)
    const p = points[idx]
    playMarker.current.setLngLat([p.lon, p.lat])
  }, [frame, points])

  // --- Play/pause ---
  useEffect(() => {
    if (!playing) return
    if (points.length === 0) {
      setPlaying(false)
      return
    }
    const id = setInterval(() => {
      setFrame((f) => {
        if (f >= points.length - 1) {
          clearInterval(id)
          setPlaying(false)
          return f
        }
        return f + 1
      })
    }, 300)
    return () => clearInterval(id)
  }, [playing, points])

  const timelineColumns: TableColumnsType<TimelineSegment> = [
    { title: t('sites.name'), dataIndex: 'site_name', key: 'site_name' },
    {
      title: t('history.enteredAt'),
      dataIndex: 'entered_at',
      key: 'entered_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: t('history.exitedAt'),
      dataIndex: 'exited_at',
      key: 'exited_at',
      render: (v: string | null) =>
        v ? new Date(v).toLocaleString() : <Tag color="green">{t('sites.inside')}</Tag>,
    },
    {
      title: t('history.dwell'),
      dataIndex: 'dwell_seconds',
      key: 'dwell_seconds',
      render: (v: number) => formatDwell(v),
    },
  ]

  const currentTs =
    points.length > 0
      ? new Date(points[Math.min(frame, points.length - 1)].ts).toLocaleString()
      : '—'

  return (
    <Space direction="vertical" style={{ width: '100%', flex: 1 }} size="middle">
      <Card size="small">
        <Space wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {t('menu.history')}
          </Typography.Title>
          <Select
            showSearch
            allowClear
            style={{ width: 240 }}
            placeholder={t('history.selectEmployee')}
            value={userId}
            onChange={setUserId}
            optionFilterProp="label"
            options={users.map((u) => ({ value: u.id, label: u.full_name }))}
          />
          <DatePicker.RangePicker
            showTime
            value={range}
            onChange={(v) => {
              if (v && v[0] && v[1]) setRange([v[0], v[1]])
            }}
            allowClear={false}
          />
        </Space>
      </Card>

      <div style={{ position: 'relative', height: 440 }}>
        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
        {!userId && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255,255,255,0.6)',
              zIndex: 1,
            }}
          >
            <Empty description={t('history.selectEmployee')} />
          </div>
        )}
      </div>

      <Card size="small">
        <Space style={{ width: '100%' }} align="center">
          <Button
            type="primary"
            shape="circle"
            icon={playing ? <PauseOutlined /> : <PlayCircleOutlined />}
            disabled={points.length === 0}
            onClick={() => setPlaying((p) => !p)}
          />
          <Slider
            style={{ flex: 1, minWidth: 200, width: 400 }}
            min={0}
            max={Math.max(0, points.length - 1)}
            value={frame}
            disabled={points.length === 0}
            onChange={(v) => {
              setPlaying(false)
              setFrame(v)
            }}
            tooltip={{ open: false }}
          />
          <Typography.Text type="secondary">{currentTs}</Typography.Text>
        </Space>
      </Card>

      <Card size="small" title={t('history.timeline')}>
        <Table<TimelineSegment>
          rowKey={(r) => `${r.site_id}-${r.entered_at}`}
          size="small"
          loading={timelineQuery.isLoading}
          dataSource={timelineQuery.data ?? []}
          columns={timelineColumns}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
        />
      </Card>
    </Space>
  )
}

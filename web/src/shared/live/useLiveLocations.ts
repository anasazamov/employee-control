import { useEffect, useRef, useState } from 'react'
import { getWsBaseUrl } from '../api/client'
import { locationsApi } from '../api/endpoints'
import type { LivePoint, WsCheckin, WsMessage } from '../api/types'
import { useAuthStore } from '../auth/store'

export type LiveStatus = 'connecting' | 'live' | 'polling' | 'offline'

export interface UseLiveLocationsResult {
  points: LivePoint[]
  /** site_id → hozir ichkaridagilar soni. */
  occupancy: Record<string, number>
  status: LiveStatus
}

interface Options {
  enabled?: boolean
  onCheckin?: (msg: WsCheckin) => void
}

const POLL_INTERVAL_MS = 10_000
const DEAD_SOCKET_MS = 15_000
const RECONNECT_DELAY_MS = 3_000

export function useLiveLocations(options: Options = {}): UseLiveLocationsResult {
  const { enabled = true, onCheckin } = options
  const accessToken = useAuthStore((s) => s.accessToken)

  const [points, setPoints] = useState<LivePoint[]>([])
  const [occupancy, setOccupancy] = useState<Record<string, number>>({})
  const [status, setStatus] = useState<LiveStatus>('connecting')

  // Render'dan ajratilgan ichki holat.
  const pointsRef = useRef<Map<string, LivePoint>>(new Map())
  const occRef = useRef<Map<string, Set<string>>>(new Map())

  // Reconnect churn bo'lmasligi uchun callback ref'da.
  const onCheckinRef = useRef(onCheckin)
  onCheckinRef.current = onCheckin

  useEffect(() => {
    if (!enabled || !accessToken) return

    let closed = false
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let deadTimer: ReturnType<typeof setTimeout> | null = null

    const commit = () => {
      setPoints(Array.from(pointsRef.current.values()))
      const occ: Record<string, number> = {}
      for (const [siteId, set] of occRef.current) occ[siteId] = set.size
      setOccupancy(occ)
    }

    const removeEverywhere = (userId: string) => {
      for (const set of occRef.current.values()) set.delete(userId)
    }
    const addToSite = (userId: string, siteId: string) => {
      removeEverywhere(userId)
      let set = occRef.current.get(siteId)
      if (!set) {
        set = new Set()
        occRef.current.set(siteId, set)
      }
      set.add(userId)
    }

    const applySnapshot = (list: LivePoint[]) => {
      pointsRef.current = new Map(list.map((p) => [p.user_id, p]))
      occRef.current = new Map()
      for (const p of list) if (p.site_id) addToSite(p.user_id, p.site_id)
      commit()
    }

    const handle = (msg: WsMessage) => {
      switch (msg.type) {
        case 'snapshot':
          applySnapshot(msg.points)
          break
        case 'point': {
          const { type: _t, ...point } = msg
          pointsRef.current.set(point.user_id, point)
          if (point.site_id) addToSite(point.user_id, point.site_id)
          else removeEverywhere(point.user_id)
          commit()
          break
        }
        case 'site_enter':
          addToSite(msg.user_id, msg.site_id)
          commit()
          break
        case 'site_exit': {
          occRef.current.get(msg.site_id)?.delete(msg.user_id)
          commit()
          break
        }
        case 'checkin':
          onCheckinRef.current?.(msg)
          break
        case 'ping':
          break
      }
    }

    // --- 10s polling fallback ---
    const pollOnce = async () => {
      try {
        const data = await locationsApi.last()
        applySnapshot(data.points)
      } catch {
        // e'tiborsiz — keyingi urinishda tuzalishi mumkin
      }
    }
    const startPolling = () => {
      if (pollTimer) return
      setStatus((s) => (s === 'live' ? s : 'polling'))
      void pollOnce()
      pollTimer = setInterval(() => void pollOnce(), POLL_INTERVAL_MS)
    }
    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    const armDeadTimer = () => {
      if (deadTimer) clearTimeout(deadTimer)
      deadTimer = setTimeout(() => {
        // ~15s jimlik → o'lik soket, qayta ulash
        ws?.close()
      }, DEAD_SOCKET_MS)
    }

    const scheduleReconnect = () => {
      if (closed || reconnectTimer) return
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        connect()
      }, RECONNECT_DELAY_MS)
    }

    const connect = () => {
      if (closed) return
      setStatus('connecting')
      const url = `${getWsBaseUrl()}/v1/live?token=${encodeURIComponent(accessToken)}`
      try {
        ws = new WebSocket(url)
      } catch {
        startPolling()
        scheduleReconnect()
        return
      }

      ws.onopen = () => {
        setStatus('live')
        stopPolling()
        armDeadTimer()
      }
      ws.onmessage = (ev) => {
        armDeadTimer()
        try {
          handle(JSON.parse(ev.data as string) as WsMessage)
        } catch {
          // yaroqsiz payload — o'tkazib yuboriladi
        }
      }
      ws.onerror = () => {
        // onclose ham chaqiriladi — fallback shu yerda boshlanadi
        startPolling()
      }
      ws.onclose = () => {
        if (deadTimer) clearTimeout(deadTimer)
        if (closed) return
        setStatus('polling')
        startPolling()
        scheduleReconnect()
      }
    }

    // Xaritani darhol GET /locations/last bilan urug'lantiramiz (WS snapshot'idan oldin).
    void pollOnce()
    connect()

    return () => {
      closed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (deadTimer) clearTimeout(deadTimer)
      stopPolling()
      if (ws) {
        ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null
        ws.close()
      }
      setStatus('offline')
    }
  }, [enabled, accessToken])

  return { points, occupancy, status }
}

import type {
  RealtimeEventName,
  RealtimeEventPayloadMap,
} from '../types'

type Listener<K extends RealtimeEventName> = (payload: RealtimeEventPayloadMap[K]) => void

const EVENT_BY_LEGACY_TYPE: Record<string, RealtimeEventName> = {
  incident_created: 'INCIDENT_CREATED',
  new_incident: 'INCIDENT_CREATED',
  dispatch_created: 'DISPATCH_ASSIGNED',
  dispatch_update: 'DISPATCH_ASSIGNED',
  dispatch_overridden: 'DISPATCH_ASSIGNED',
  ambulance_location_update: 'AMBULANCE_UPDATED',
  simulation_tick: 'AMBULANCE_UPDATED',
  route_change: 'AMBULANCE_UPDATED',
  hospital_notification: 'HOSPITAL_UPDATED',
  score_update: 'BENCHMARK_UPDATED',
  ping: 'HEARTBEAT',
  state_snapshot: 'STATE_SNAPSHOT',
}

const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000]

function withoutTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

function websocketRoot(): string {
  const explicit = import.meta.env.VITE_WS_URL || import.meta.env.VITE_WS_BASE_URL
  const apiBase = import.meta.env.VITE_API_BASE_URL || ''
  const raw = withoutTrailingSlash(explicit || apiBase)
  if (raw) {
    return raw
      .replace(/^http/, 'ws')
      .replace(/\/ws\/live$/, '')
      .replace(/\/ws$/, '')
  }
  return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
}

export class RaidRealtimeSocket {
  private socket: WebSocket | null = null
  private retryIndex = 0
  private reconnectTimer: number | null = null
  private manuallyClosed = false
  private readonly listeners = new Map<RealtimeEventName, Set<Listener<RealtimeEventName>>>()

  constructor(private readonly getToken: () => string | null | undefined) {}

  connect(): void {
    if (this.socket || this.reconnectTimer) return
    this.manuallyClosed = false
    this.open()
  }

  disconnect(): void {
    this.manuallyClosed = true
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.socket?.close()
    this.socket = null
    this.retryIndex = 0
  }

  on<K extends RealtimeEventName>(event: K, listener: Listener<K>): () => void {
    const bucket = this.listeners.get(event) || new Set<Listener<RealtimeEventName>>()
    bucket.add(listener as Listener<RealtimeEventName>)
    this.listeners.set(event, bucket)
    return () => bucket.delete(listener as Listener<RealtimeEventName>)
  }

  private open(): void {
    const token = this.getToken()
    if (!token) return
    const ws = new WebSocket(`${websocketRoot()}/ws/live?token=${encodeURIComponent(token)}`)
    this.socket = ws

    ws.onopen = () => {
      this.retryIndex = 0
    }
    ws.onclose = () => {
      this.socket = null
      if (!this.manuallyClosed) this.scheduleReconnect()
    }
    ws.onerror = () => ws.close()
    ws.onmessage = (event) => this.handleMessage(event.data)
  }

  private scheduleReconnect(): void {
    if (this.retryIndex >= BACKOFF_MS.length) return
    const delay = BACKOFF_MS[this.retryIndex]
    this.retryIndex += 1
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.open()
    }, delay)
  }

  private handleMessage(raw: string): void {
    const payload = JSON.parse(raw)
    const eventName = normalizeEventName(payload.event || payload.type)
    if (eventName === 'HEARTBEAT') {
      this.socket?.send(JSON.stringify({ event: 'HEARTBEAT_ACK', type: 'HEARTBEAT_ACK' }))
    }
    const bucket = this.listeners.get(eventName)
    bucket?.forEach((listener) => listener(payload))
  }
}

function normalizeEventName(value?: string): RealtimeEventName {
  if (!value) return 'BENCHMARK_UPDATED'
  if (value && value.toUpperCase() === value) return value as RealtimeEventName
  return EVENT_BY_LEGACY_TYPE[value] || 'BENCHMARK_UPDATED'
}

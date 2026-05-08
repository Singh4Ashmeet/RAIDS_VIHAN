import { create } from 'zustand'
import api, { WS_ROOT } from '../services/api'
import { mockAmbulances, mockHospitals, mockIncidents } from '../services/mockData'
import useAuthStore from './authStore'

let _retryDelay = 1000
const MAX_DELAY = 16000
const MAX_RECONNECT_ATTEMPTS = 5

const EVENT_TYPE_BY_EVENT = {
  INCIDENT_CREATED: 'incident_created',
  DISPATCH_ASSIGNED: 'dispatch_created',
  AMBULANCE_UPDATED: 'ambulance_location_update',
  HOSPITAL_UPDATED: 'hospital_notification',
  BENCHMARK_UPDATED: 'score_update',
  HEARTBEAT: 'ping',
  STATE_SNAPSHOT: 'state_snapshot',
}

function normalizeDispatch(plan) {
  if (!plan) return null
  if (typeof plan === 'object' && plan !== null && 'status' in plan) return plan
  return { status: 'success', message: 'OK', data: plan }
}

function upsertById(items, nextItem) {
  if (!nextItem?.id) return items
  return [
    nextItem,
    ...items.filter((item) => item.id !== nextItem.id),
  ]
}

function mergeById(items, nextItem) {
  if (!nextItem?.id) return items
  if (!items.some((item) => item.id === nextItem.id)) {
    return [nextItem, ...items]
  }
  return items.map((item) => (
    item.id === nextItem.id ? { ...item, ...nextItem } : item
  ))
}

function mergeAmbulanceUpdates(current, message) {
  const updates = Array.isArray(message.ambulances)
    ? message.ambulances
    : message.ambulance
      ? [message.ambulance]
      : []
  if (updates.length === 0) return current
  const byId = new Map(current.map((item) => [item.id, item]))
  updates.forEach((item) => {
    byId.set(item.id, { ...(byId.get(item.id) || {}), ...item })
  })
  return Array.from(byId.values()).sort((left, right) => String(left.id).localeCompare(String(right.id)))
}

function mergeRoute(previous, nextRoute) {
  if (!nextRoute) return previous
  if (
    previous &&
    previous.dispatch_id === nextRoute.dispatch_id &&
    !nextRoute.coordinates &&
    previous.coordinates
  ) {
    return { ...previous, ...nextRoute, coordinates: previous.coordinates }
  }
  return { ...(previous || {}), ...nextRoute }
}

function cityKey(value) {
  return String(value || '').trim().toLowerCase()
}

function findEntityById(items, id) {
  if (!id) return null
  return items.find((item) => item.id === id) || null
}

function routeEntityContext(state, route, mapEntities = {}) {
  const mapHospitals = Array.isArray(mapEntities.hospitals) ? mapEntities.hospitals : []
  return {
    incident: mapEntities.incident?.id === route?.incident_id
      ? mapEntities.incident
      : findEntityById(state.incidents, route?.incident_id),
    ambulance: mapEntities.ambulance?.id === route?.ambulance_id
      ? mapEntities.ambulance
      : findEntityById(state.ambulances, route?.ambulance_id),
    hospital: mapEntities.hospital?.id === route?.hospital_id
      ? mapEntities.hospital
      : findEntityById(mapHospitals, route?.hospital_id) || findEntityById(state.hospitals, route?.hospital_id),
  }
}

function isCityLocalRoute(state, route, mapEntities = {}) {
  if (!route) return false
  if (route.manual_escalation) return false
  const { incident, ambulance, hospital } = routeEntityContext(state, route, mapEntities)
  const serviceCity = cityKey(route.service_city || incident?.city)
  if (!serviceCity) return true
  const entityCities = [incident?.city, ambulance?.city, hospital?.city].filter(Boolean).map(cityKey)
  return entityCities.every((city) => city === serviceCity)
}

function filterCityLocalRoutes(state, routes, mapEntities = {}) {
  if (!Array.isArray(routes)) return routes
  return routes.filter((route) => isCityLocalRoute(state, route, mapEntities))
}

function mergeDispatchPlan(current, partialPlan) {
  if (!partialPlan?.id) return current
  const currentPlan = current?.data ?? current
  const currentId = currentPlan?.id
  if (currentId && currentId !== partialPlan.id) {
    return current
  }
  if (current?.data) {
    return {
      ...current,
      data: {
        ...current.data,
        ...partialPlan,
      },
    }
  }
  return normalizeDispatch({
    ...(currentPlan || {}),
    ...partialPlan,
  })
}

function shouldApplyRoute(state, route, mapEntities = {}) {
  if (!route) return false
  if (!isCityLocalRoute(state, route, mapEntities)) return false
  const currentDispatch = state.lastDispatch?.data ?? state.lastDispatch
  const hasGeometry = Array.isArray(route.coordinates) && route.coordinates.length > 0
  if (currentDispatch?.id && route.dispatch_id && route.dispatch_id !== currentDispatch.id) {
    return hasGeometry && !state.activeRoute?.dispatch_id
  }
  if (state.activeRoute?.dispatch_id && route.dispatch_id && route.dispatch_id !== state.activeRoute.dispatch_id) {
    return hasGeometry
  }
  return true
}

function unwrapApiData(res) {
  return res?.data?.data ?? res?.data ?? null
}

function withOverriddenDispatch(current, payload) {
  if (!current) return current
  const nextFields = {
    ambulance_id: payload.new_ambulance_id,
    hospital_id: payload.new_hospital_id,
    eta_minutes: payload.new_eta_minutes,
    status: 'overridden',
    override_id: payload.override_id,
    audit_id: payload.audit_id,
  }
  if (current.data) {
    return {
      ...current,
      status: 'overridden',
      data: {
        ...current.data,
        ...nextFields,
      },
    }
  }
  return {
    ...current,
    ...nextFields,
  }
}

const useDispatchStore = create((set, get) => ({
  incidents:    [],
  ambulances:   [],
  hospitals:    [],
  lastDispatch: null,
  lastScoreBreakdown: null,
  liveAnalytics: null,
  dispatchHistory: [],
  notifications: [],
  anomalyAlerts: [],
  overrideHistory: [],
  overrideStats: null,
  availableUnits: null,
  loadingOverride: false,
  overrideError: null,
  lastOverride: null,
  trafficMultiplier: 1,
  trafficMultipliers: {},
  activeRoute: null,
  alternateRoutes: [],
  ambulanceOptions: [],
  routeChange: null,
  simulationMode: false,
  selectedMapAmbulanceId: null,
  wsStatus:     'disconnected',
  systemStatus: 'normal',
  _ws:          null,
  _wsReconnectAttempts: 0,
  _wsReconnectTimer: null,
  _wsManualClose: false,

  pushNotification: (event) => {
    if (!event) return
    set((state) => ({
      notifications: [event, ...state.notifications].slice(0, 20),
    }))
  },

  clearOverrideError: () => set({ overrideError: null }),

  setSimulationMode: (simulationMode) => set({ simulationMode }),

  setSelectedMapAmbulanceId: (selectedMapAmbulanceId) => set({ selectedMapAmbulanceId }),

  applyMapContext: (context) => {
    if (!context) return
    set((state) => {
      const route = context.route
      const mapEntities = context.map_entities || {}
      const applyRoute = shouldApplyRoute(state, route, mapEntities)
      return {
        activeRoute: applyRoute ? mergeRoute(state.activeRoute, route) : state.activeRoute,
        alternateRoutes: Array.isArray(context.alternate_routes)
          ? filterCityLocalRoutes(state, context.alternate_routes, mapEntities)
          : state.alternateRoutes,
        ambulanceOptions: Array.isArray(context.ambulance_options)
          ? context.ambulance_options
          : state.ambulanceOptions,
        incidents: mapEntities.incident
          ? upsertById(state.incidents, mapEntities.incident)
          : state.incidents,
        ambulances: mapEntities.ambulance
          ? mergeById(state.ambulances, mapEntities.ambulance)
          : state.ambulances,
        hospitals: Array.isArray(mapEntities.hospitals)
          ? mapEntities.hospitals
          : mapEntities.hospital
            ? mergeById(state.hospitals, mapEntities.hospital)
            : state.hospitals,
      }
    })
  },

  applyDispatchUpdate: (msg) => {
    if (!msg) return
    set((state) => ({
      lastDispatch: msg.dispatch_plan
        ? mergeDispatchPlan(state.lastDispatch, msg.dispatch_plan)
        : state.lastDispatch,
      activeRoute: shouldApplyRoute(state, msg.route, msg.map_entities || {})
        ? mergeRoute(state.activeRoute, msg.route)
        : state.activeRoute,
      alternateRoutes: Array.isArray(msg.alternate_routes)
        ? filterCityLocalRoutes(state, msg.alternate_routes, msg.map_entities || {})
        : state.alternateRoutes,
      ambulanceOptions: Array.isArray(msg.ambulance_options)
        ? msg.ambulance_options
        : state.ambulanceOptions,
    }))
    get().applyMapContext(msg)
  },

  dismissAnomalyAlert: () => set((state) => ({
    anomalyAlerts: state.anomalyAlerts.slice(1),
  })),

  fetchAll: async () => {
    const unwrap = (res) =>
      Array.isArray(res.data)
        ? res.data
        : (res.data?.data ?? res.data ?? [])
    try {
      const [inc, amb, hosp] = await Promise.all([
        api.get('/incidents'),
        api.get('/ambulances'),
        api.get('/hospitals'),
      ])
      set({
        incidents:  unwrap(inc),
        ambulances: unwrap(amb),
        hospitals:  unwrap(hosp),
      })
    } catch (e) {
      console.error('[dispatchStore] fetchAll failed', e)
      set({
        incidents: mockIncidents,
        ambulances: mockAmbulances,
        hospitals: mockHospitals,
      })
    }
  },

  setLastDispatch: (plan) => {
    const normalized = normalizeDispatch(plan)
    const status = normalized?.status || 'success'
    const dispatchId = normalized?.data?.id || normalized?.id
    const scoreBreakdown =
      normalized?.data?.score_breakdown ??
      normalized?.score_breakdown ??
      null
    const nextTrafficMultiplier =
      normalized?.data?.traffic_multiplier ??
      normalized?.traffic_multiplier
    set((state) => ({
      lastDispatch: normalized,
      lastScoreBreakdown: scoreBreakdown,
      trafficMultiplier:
        typeof nextTrafficMultiplier === 'number'
          ? nextTrafficMultiplier
          : state.trafficMultiplier,
      dispatchHistory: dispatchId
        ? [
            normalized,
            ...state.dispatchHistory.filter(
              (entry) => (entry?.data?.id || entry?.id) !== dispatchId
            ),
          ].slice(0, 20)
        : state.dispatchHistory,
      systemStatus: status === 'fallback' ? 'fallback'
                  : status === 'error'    ? 'overload'
          : 'normal',
    }))
  },

  fetchAvailableUnits: async (city, incident_lat, incident_lng) => {
    if (!city) return null
    set({ loadingOverride: true })
    try {
      const params = { city }
      if (incident_lat != null && incident_lng != null) {
        params.incident_lat = incident_lat
        params.incident_lng = incident_lng
      }
      const res = await api.get('/overrides/available-units', { params })
      const result = unwrapApiData(res)
      set({ availableUnits: result, loadingOverride: false })
      return result
    } catch (err) {
      set({
        overrideError: err.response?.data?.detail || 'Failed to load available override units.',
        loadingOverride: false,
      })
      return null
    }
  },

  submitOverride: async (overridePayload) => {
    set({ loadingOverride: true, overrideError: null })
    try {
      const res = await api.post('/overrides/request', overridePayload)
      const result = {
        ...overridePayload,
        ...unwrapApiData(res),
      }
      set((state) => ({
        lastOverride: result,
        overrideHistory: [result, ...state.overrideHistory].slice(0, 20),
        loadingOverride: false,
      }))
      return result
    } catch (err) {
      set({
        overrideError: err.response?.data?.detail || 'Override failed. Please try again.',
        loadingOverride: false,
      })
      return null
    }
  },

  fetchOverrideStats: async (city, days = 7) => {
    try {
      const params = { days }
      if (city) params.city = city
      const res = await api.get('/overrides/stats', { params })
      const result = unwrapApiData(res)
      set({ overrideStats: result })
      return result
    } catch (err) {
      console.error('[dispatchStore] fetchOverrideStats failed', err)
      return null
    }
  },

  connectWS: () => {
    if (get()._ws || get().wsStatus === 'connecting') return
    const clearReconnectTimer = () => {
      const timer = get()._wsReconnectTimer
      if (timer) clearTimeout(timer)
      set({ _wsReconnectTimer: null })
    }
    const connect = () => {
      clearReconnectTimer()
      const token = useAuthStore.getState().token
      if (!token) {
        _retryDelay = 1000
        set({ wsStatus: 'disconnected', _ws: null, _wsReconnectAttempts: 0 })
        return
      }
      set({ wsStatus: 'connecting', _wsManualClose: false })
      const wsUrl = WS_ROOT
        ? `${WS_ROOT}/ws/live${token ? `?token=${encodeURIComponent(token)}` : ''}`
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/live${token ? `?token=${encodeURIComponent(token)}` : ''}`
      const ws = new WebSocket(wsUrl)
      ws.onopen  = () => {
        _retryDelay = 1000
        set({ wsStatus: 'connected', _ws: ws, _wsReconnectAttempts: 0 })
      }
      ws.onclose = (event) => {
        set({ wsStatus: 'disconnected', _ws: null })
        if (event.code === 1008) {
          _retryDelay = 1000
          useAuthStore.getState().logout()
          return
        }
        if (get()._wsManualClose) return
        const attempts = get()._wsReconnectAttempts + 1
        if (attempts > MAX_RECONNECT_ATTEMPTS) {
          set({ wsStatus: 'failed', _wsReconnectAttempts: attempts })
          return
        }
        const timer = setTimeout(connect, _retryDelay)
        _retryDelay = Math.min(_retryDelay * 2, MAX_DELAY)
        set({ _wsReconnectAttempts: attempts, _wsReconnectTimer: timer })
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data)
          const msg = parsed.type
            ? parsed
            : { ...parsed, type: EVENT_TYPE_BY_EVENT[parsed.event] || parsed.event }
          if (msg.type === 'ping' || msg.event === 'HEARTBEAT') {
            if (ws.readyState === 1) {
              ws.send(JSON.stringify({
                type: 'HEARTBEAT_ACK',
                event: 'HEARTBEAT_ACK',
                timestamp: new Date().toISOString(),
              }))
            }
            return
          }
          if (msg.type === 'state_snapshot' ||
              msg.type === 'simulation_tick') {
            set({
              ambulances: msg.ambulances || get().ambulances,
              hospitals:  msg.hospitals  || get().hospitals,
              incidents:  msg.incidents  || get().incidents,
              trafficMultipliers: msg.traffic_multipliers || get().trafficMultipliers,
            })
            if (msg.traffic_multipliers) {
              const maxTraffic = Math.max(1, ...Object.values(msg.traffic_multipliers).map(Number))
              set({ trafficMultiplier: maxTraffic })
            }
            if (msg.map_context) {
              get().applyMapContext(msg.map_context)
            }
          }
          if (msg.type === 'ambulance_location_update') {
            set((state) => ({
              ambulances: mergeAmbulanceUpdates(state.ambulances, msg),
            }))
          }
          if (msg.type === 'dispatch_created') {
            const current = get().lastDispatch
            const currentId = current?.data?.id || current?.id
            if (currentId && currentId === msg.dispatch_plan?.id && current?.status && current.status !== 'success') {
              get().setLastDispatch({ ...current, data: msg.dispatch_plan })
            } else {
              get().setLastDispatch(msg.dispatch_plan)
            }
            if (msg.dispatch_plan?.incident_id) {
              set((state) => ({
                incidents: state.incidents.map((incident) => (
                  incident.id === msg.dispatch_plan.incident_id
                    ? {
                        ...incident,
                        requires_human_review: msg.dispatch_plan.requires_human_review ?? incident.requires_human_review ?? false,
                        review_reason: msg.dispatch_plan.review_reason ?? incident.review_reason ?? null,
                        triage_confidence: msg.dispatch_plan.triage_confidence ?? incident.triage_confidence ?? null,
                        triage_version: msg.dispatch_plan.triage_version ?? incident.triage_version ?? null,
                        language_detected: msg.dispatch_plan.language_detected ?? incident.language_detected ?? null,
                        language_name: msg.dispatch_plan.language_name ?? incident.language_name ?? null,
                        original_complaint: msg.dispatch_plan.original_complaint ?? incident.original_complaint ?? null,
                        translated_complaint: msg.dispatch_plan.translated_complaint ?? incident.translated_complaint ?? null,
                        translation_model: msg.dispatch_plan.translation_model ?? incident.translation_model ?? null,
                      }
                    : incident
                )),
              }))
            }
            get().applyMapContext(msg)
          }
          if (msg.type === 'dispatch_update') {
            get().applyDispatchUpdate(msg)
          }
          if (msg.type === 'route_change') {
            const routeChangeMapEntities = msg.map_entities || {}
            set((state) => ({
              routeChange: isCityLocalRoute(state, msg.new_route, routeChangeMapEntities)
                ? msg
                : { ...msg, new_route: null, alternate_routes: [] },
              activeRoute: isCityLocalRoute(state, msg.new_route, routeChangeMapEntities)
                ? mergeRoute(state.activeRoute, msg.new_route)
                : state.activeRoute,
              alternateRoutes: Array.isArray(msg.alternate_routes)
                ? filterCityLocalRoutes(state, msg.alternate_routes, routeChangeMapEntities)
                : state.alternateRoutes,
              ambulanceOptions: Array.isArray(msg.ambulance_options)
                ? msg.ambulance_options
                : state.ambulanceOptions,
              notifications: [
                {
                  type: 'route_change',
                  message: msg.label || 'Route changed',
                  timestamp: msg.timestamp,
                },
                ...state.notifications,
              ].slice(0, 20),
            }))
          }
          if (msg.type === 'incident_created' || msg.type === 'new_incident') {
            const incident = {
              ...(msg.incident || {}),
              requires_human_review: msg.requires_human_review ?? msg.incident?.requires_human_review ?? false,
              review_reason: msg.review_reason ?? msg.incident?.review_reason ?? null,
            }
            if (incident.id) {
              set((state) => ({
                incidents: upsertById(state.incidents, incident),
              }))
            }
          }
          if (msg.type === 'score_update') {
            set({
              liveAnalytics: msg.analytics || get().liveAnalytics,
            })
          }
          if (msg.type === 'dispatch_overridden') {
            set((state) => ({
              ambulances: state.ambulances.map((ambulance) => {
                if (ambulance.id === msg.original_ambulance_id) {
                  return {
                    ...ambulance,
                    status: 'available',
                    assigned_incident_id: null,
                    assigned_hospital_id: null,
                  }
                }
                if (ambulance.id === msg.new_ambulance_id) {
                  return {
                    ...ambulance,
                    status: 'en_route',
                    assigned_incident_id: msg.dispatch_id,
                    assigned_hospital_id: msg.new_hospital_id,
                  }
                }
                return ambulance
              }),
              lastDispatch: withOverriddenDispatch(state.lastDispatch, msg),
              overrideHistory: [msg, ...state.overrideHistory].slice(0, 20),
              notifications: [
                {
                  type: 'override',
                  message: `Dispatch overridden by ${msg.overridden_by}: ${msg.reason_category}`,
                  timestamp: msg.timestamp,
                },
                ...state.notifications,
              ].slice(0, 20),
              lastOverride: msg,
              systemStatus: 'normal',
            }))
          }
          if (msg.type === 'anomaly_detected') {
            const anomalies = Array.isArray(msg.anomalies) ? msg.anomalies : []
            if (anomalies.length > 0) {
              set((state) => ({
                anomalyAlerts: [...anomalies, ...state.anomalyAlerts].slice(0, 10),
                notifications: [
                  {
                    type: 'anomaly',
                    message: anomalies[0].description,
                    timestamp: anomalies[0].detected_at,
                  },
                  ...state.notifications,
                ].slice(0, 20),
              }))
            }
          }
          if (msg.type === 'hospital_notification' ||
              msg.type === 'scenario_triggered') {
            get().pushNotification(msg)
          }
        } catch {}
      }
    }
    connect()
  },

  disconnectWS: () => {
    const timer = get()._wsReconnectTimer
    if (timer) clearTimeout(timer)
    _retryDelay = 1000
    const ws = get()._ws
    if (ws) {
      ws.onclose = null
      ws.close()
    }
    set({
      _ws: null,
      wsStatus: 'disconnected',
      _wsReconnectTimer: null,
      _wsReconnectAttempts: 0,
      _wsManualClose: true,
    })
  },
}))

export default useDispatchStore

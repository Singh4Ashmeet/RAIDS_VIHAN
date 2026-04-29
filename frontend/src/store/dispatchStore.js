import { create } from 'zustand'
import api, { WS_ROOT } from '../services/api'
import { mockAmbulances, mockHospitals, mockIncidents } from '../services/mockData'
import useAuthStore from './authStore'

function normalizeDispatch(plan) {
  if (!plan) return null
  if (typeof plan === 'object' && plan !== null && 'status' in plan) return plan
  return { status: 'success', message: 'OK', data: plan }
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
        set({ wsStatus: 'disconnected', _ws: null, _wsReconnectAttempts: 0 })
        return
      }
      set({ wsStatus: 'connecting', _wsManualClose: false })
      const wsUrl = WS_ROOT
        ? `${WS_ROOT}/ws/live${token ? `?token=${encodeURIComponent(token)}` : ''}`
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/live${token ? `?token=${encodeURIComponent(token)}` : ''}`
      const ws = new WebSocket(wsUrl)
      ws.onopen  = () => set({ wsStatus: 'connected', _ws: ws, _wsReconnectAttempts: 0 })
      ws.onclose = (event) => {
        set({ wsStatus: 'disconnected', _ws: null })
        if (event.code === 1008) {
          useAuthStore.getState().logout()
          return
        }
        if (get()._wsManualClose) return
        const attempts = get()._wsReconnectAttempts + 1
        if (attempts > 10) {
          set({ wsStatus: 'failed', _wsReconnectAttempts: attempts })
          return
        }
        const delay = Math.min(30000, 1000 * (2 ** Math.min(attempts - 1, 4)))
        const timer = setTimeout(connect, delay)
        set({ _wsReconnectAttempts: attempts, _wsReconnectTimer: timer })
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'state_snapshot' ||
              msg.type === 'simulation_tick') {
            set({
              ambulances: msg.ambulances || get().ambulances,
              hospitals:  msg.hospitals  || get().hospitals,
            })
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
          }
          if (msg.type === 'incident_created') {
            const incident = {
              ...(msg.incident || {}),
              requires_human_review: msg.requires_human_review ?? msg.incident?.requires_human_review ?? false,
              review_reason: msg.review_reason ?? msg.incident?.review_reason ?? null,
            }
            if (incident.id) {
              set((state) => ({
                incidents: [
                  incident,
                  ...state.incidents.filter((item) => item.id !== incident.id),
                ],
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

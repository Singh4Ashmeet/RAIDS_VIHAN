import axios from 'axios'
import useAuthStore from '../store/authStore'

function withoutTrailingSlash(value) {
  return value.replace(/\/+$/, '')
}

function normalizeApiRoot(value) {
  const base = withoutTrailingSlash(value || '')
  if (!base) return '/api'
  return base.endsWith('/api') ? base : `${base}/api`
}

function normalizeWsRoot(value) {
  const base = withoutTrailingSlash(value || '')
  if (!base) return null
  return base
    .replace(/^http/, 'ws')
    .replace(/\/ws\/live$/, '')
    .replace(/\/ws$/, '')
}

const rawApiBase = import.meta.env.VITE_API_BASE_URL || ''
const rawWsBase = import.meta.env.VITE_WS_URL || import.meta.env.VITE_WS_BASE_URL || rawApiBase
export const API_ROOT = normalizeApiRoot(rawApiBase)
export const WS_ROOT = normalizeWsRoot(rawWsBase)

const api = axios.create({ baseURL: API_ROOT })

function formatApiError(value, fallback = 'Request failed') {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value
      .map((item) => formatApiError(item, ''))
      .filter(Boolean)
      .join('; ') || fallback
  }
  if (value && typeof value === 'object') {
    if (typeof value.detail === 'string') return value.detail
    if (typeof value.message === 'string') return value.message
    if (typeof value.msg === 'string') {
      const location = Array.isArray(value.loc) ? value.loc.join('.') : ''
      return location ? `${location}: ${value.msg}` : value.msg
    }
    try {
      return JSON.stringify(value)
    } catch {
      return fallback
    }
  }
  return fallback
}

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout(false)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

async function request(path, options = {}) {
  const token = useAuthStore.getState().token
  const normalizedPath = path.startsWith('/api/')
    ? path.slice(4)
    : path
  const url = `${API_ROOT}${normalizedPath.startsWith('/') ? normalizedPath : `/${normalizedPath}`}`
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    if (response.status === 401) {
      useAuthStore.getState().logout(false)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    let message = `Request failed with status ${response.status}`

    try {
      const errorBody = await response.json()
      message = formatApiError(errorBody?.detail ?? errorBody?.message ?? errorBody, message)
    } catch {
      const text = await response.text()
      if (text) {
        message = text
      }
    }

    throw new Error(message)
  }

  return response.json()
}

function unwrapDispatch(dispatch) {
  if (!dispatch || typeof dispatch !== 'object') {
    return dispatch
  }
  if ('data' in dispatch && !('ambulance_id' in dispatch)) {
    return dispatch.data
  }
  return dispatch
}

function unwrapEnvelope(result) {
  if (result && typeof result === 'object' && 'data' in result && 'status' in result) {
    return result.data
  }
  return result
}

function postJson(path, body) {
  return request(path, {
    method: 'POST',
    body: JSON.stringify(body ?? {}),
  })
}

export function fetchAmbulances() {
  return request('/ambulances').then(unwrapEnvelope)
}

export const getAmbulances = fetchAmbulances

export function fetchHospitals() {
  return request('/hospitals').then(unwrapEnvelope)
}

export const getHospitals = fetchHospitals

export function fetchIncidents() {
  return request('/incidents').then(unwrapEnvelope)
}

export const getIncidents = fetchIncidents

export function fetchAnalytics() {
  return request('/analytics').then(unwrapEnvelope)
}

export const getAnalytics = fetchAnalytics

export function fetchBenchmark() {
  return request('/benchmark').then(unwrapEnvelope)
}

export const getBenchmarks = fetchBenchmark

export function fetchDemandHeatmap(city, lookahead = 30) {
  const params = new URLSearchParams({ city, lookahead: String(lookahead) })
  return request(`/demand/heatmap?${params.toString()}`).then(unwrapEnvelope)
}

export const getHeatmap = fetchDemandHeatmap
export const getRecommendations = fetchDemandHeatmap

export async function fetchPatient(id) {
  const result = await request(`/api/patients/${id}`)
  const payload = unwrapEnvelope(result)
  return payload?.patient ?? payload
}

export async function createPatient(body) {
  const result = await postJson('/patients', body)
  const payload = unwrapEnvelope(result)
  return {
    ...payload,
    dispatch_plan: unwrapDispatch(payload?.dispatch_plan),
  }
}

export async function createIncident(body) {
  const result = await postJson('/incidents', body)
  const payload = unwrapEnvelope(result)
  return {
    ...payload,
    dispatch_plan: unwrapDispatch(payload?.dispatch_plan),
  }
}

export async function triggerScenario(type, options = {}) {
  const body = typeof type === 'object' && type !== null
    ? type
    : { type, ...options }
  const result = await postJson('/simulate/scenario', body)
  const payload = unwrapEnvelope(result)
  return {
    ...payload,
    dispatch_plan: unwrapDispatch(payload?.dispatch_plan),
  }
}

export async function setTrafficOverride({ city = 'Delhi', multiplier = 1, duration_seconds = 300 }) {
  const result = await postJson('/simulate/traffic', {
    city,
    multiplier,
    duration_seconds,
  })
  return unwrapEnvelope(result)
}

export async function triggerDispatch(incidentId) {
  const result = await postJson('/dispatch', { incident_id: incidentId })
  return unwrapDispatch(unwrapEnvelope(result))
}

export async function getDispatchStatus(dispatchId) {
  return request(`/dispatch/${dispatchId}`)
}

export default api

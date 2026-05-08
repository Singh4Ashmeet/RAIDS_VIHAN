import type {
  Ambulance,
  Analytics,
  BenchmarkResult,
  DispatchPlan,
  Hospital,
  Incident,
} from '../types'

function withoutTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

export const API_BASE_URL = withoutTrailingSlash(import.meta.env.VITE_API_BASE_URL || '')
export const API_ROOT = API_BASE_URL.endsWith('/api')
  ? API_BASE_URL
  : `${API_BASE_URL || ''}/api`

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function formatApiError(value: unknown, fallback: string): string {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') {
    const detail = 'detail' in value ? value.detail : undefined
    const message = 'message' in value ? value.message : undefined
    if (typeof detail === 'string') return detail
    if (typeof message === 'string') return message
  }
  return fallback
}

async function parseJson<T>(response: Response): Promise<T> {
  const body = await response.json()
  if (body && typeof body === 'object' && 'status' in body && 'data' in body) {
    return body.data as T
  }
  return body as T
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const normalizedPath = path.startsWith('/api/')
    ? path.slice(4)
    : path.startsWith('/')
      ? path
      : `/${path}`
  const response = await fetch(`${API_ROOT}${normalizedPath}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      message = formatApiError(await response.json(), message)
    } catch {
      const text = await response.text()
      if (text) message = text
    }
    throw new ApiError(message, response.status)
  }

  return parseJson<T>(response)
}

export const typedApi = {
  ambulances: () => apiFetch<Ambulance[]>('/ambulances'),
  hospitals: () => apiFetch<Hospital[]>('/hospitals'),
  incidents: () => apiFetch<Incident[]>('/incidents'),
  analytics: () => apiFetch<Analytics>('/analytics'),
  benchmark: () => apiFetch<BenchmarkResult>('/benchmark'),
  dispatch: (incidentId: string) => apiFetch<DispatchPlan>('/dispatch', {
    method: 'POST',
    body: JSON.stringify({ incident_id: incidentId }),
  }),
}

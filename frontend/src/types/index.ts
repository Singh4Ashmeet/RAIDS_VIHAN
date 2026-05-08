export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical'

export type AmbulanceStatus =
  | 'available'
  | 'en_route'
  | 'at_scene'
  | 'transporting'
  | 'at_hospital'
  | 'unavailable'

export type DispatchStatus = 'success' | 'fallback' | 'error' | 'active' | 'overridden'

export interface Incident {
  id: string
  type?: string
  severity: IncidentSeverity | string
  patient_count?: number
  location_lat?: number
  location_lng?: number
  lat?: number
  lng?: number
  city?: string
  description?: string
  status?: string
  created_at?: string
  patient_id?: string | null
  requires_human_review?: boolean
  review_reason?: string | null
}

export interface AIScoreBreakdown {
  distance?: number
  availability?: number
  specialty?: number
  total_score?: number
  components?: Record<string, number>
  weights_used?: Record<string, number>
  eta_to_scene_minutes?: number
  eta_to_hospital_minutes?: number
  total_eta_minutes?: number
}

export interface DispatchPlan {
  id: string
  ambulance_id: string
  hospital_id: string
  hospital_name?: string
  incident_id?: string
  eta_minutes: number
  final_score: number
  status: DispatchStatus
  dispatch_tier: 'ml' | 'heuristic' | 'static' | 'random'
  score_breakdown?: AIScoreBreakdown
  explanation?: DispatchDecision
  explanation_text?: string
}

export interface Explanation {
  selected_reason: string
  score_breakdown: {
    eta_score: number
    capacity_score: number
    specialty_score: number
    final_score: number
  }
  rejected_hospitals: Array<{ id: string; name: string; reason: string }>
}

export interface ScenarioResult {
  scenario: 'cardiac' | 'overload' | 'breakdown' | 'traffic'
  dispatch_plan?: DispatchPlan
  explanation?: Explanation
  dispatch_status?: 'success' | 'fallback'
  dispatch_message?: string
  overload?: { hospital_id: string; occupancy_pct: number; diversion_status: boolean }
  breakdown?: { ambulance_id: string; expires_at: string }
  traffic?: { city: string; multiplier: number; expires_at: string }
}

export interface Ambulance {
  id: string
  type: 'ALS' | 'BLS'
  status: AmbulanceStatus
  city: string
  lat?: number
  lng?: number
  current_lat?: number
  current_lng?: number
  hospital_id?: string | null
  updated_at?: string
  assigned_incident_id?: string | null
  assigned_hospital_id?: string | null
  equipment?: string[]
  crew_readiness?: number
}

export interface Hospital {
  id: string
  name: string
  city: string
  beds_available?: number
  occupancy_pct: number
  diversion_status: boolean
  specialties: string[]
  lat: number
  lng: number
  updated_at?: string
}

export interface Analytics {
  avg_eta_ai: number
  avg_eta_baseline: number
  incidents_today: number
  dispatches_today: number
  overloads_prevented: number
}

export interface DispatchDecision {
  selected_ambulance: {
    id?: string
    reason: string
  }
  selected_hospital: {
    id?: string
    reason: string
  }
  score_breakdown: AIScoreBreakdown
  rejected: Array<{ id?: string; reason: string }>
  explanation?: Record<string, unknown>
}

export interface ETAResponse {
  ambulance_id: string
  incident_id: string
  eta_minutes: number
  distance_km?: number
  model_used?: string
}

export interface BenchmarkResult {
  id?: string
  scenario_count: number
  avg_eta: number
  accuracy: number
  created_at?: string
  strategies?: Record<string, unknown>
}

export type RealtimeEventName =
  | 'INCIDENT_CREATED'
  | 'DISPATCH_ASSIGNED'
  | 'AMBULANCE_UPDATED'
  | 'HOSPITAL_UPDATED'
  | 'BENCHMARK_UPDATED'
  | 'HEARTBEAT'
  | 'HEARTBEAT_ACK'
  | 'STATE_SNAPSHOT'

export interface RealtimeEventPayloadMap {
  INCIDENT_CREATED: { incident: Incident }
  DISPATCH_ASSIGNED: { dispatch_plan: DispatchPlan }
  AMBULANCE_UPDATED: { ambulance?: Ambulance; ambulances?: Ambulance[] }
  HOSPITAL_UPDATED: { hospital?: Hospital; hospitals?: Hospital[] }
  BENCHMARK_UPDATED: { analytics?: Analytics; benchmark?: BenchmarkResult }
  HEARTBEAT: { timestamp?: string }
  HEARTBEAT_ACK: { timestamp?: string }
  STATE_SNAPSHOT: {
    ambulances: Ambulance[]
    hospitals: Hospital[]
    incidents: Incident[]
    active_dispatches?: DispatchPlan[]
  }
}

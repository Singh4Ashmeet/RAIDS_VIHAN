export interface DispatchPlan {
  id: string
  ambulance_id: string
  hospital_id: string
  hospital_name: string
  eta_minutes: number
  final_score: number
  status: 'success' | 'fallback' | 'error'
  dispatch_tier: 'ml' | 'heuristic' | 'static'
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
  status: 'available' | 'en_route' | 'unavailable'
  city: string
  lat: number
  lng: number
}

export interface Hospital {
  id: string
  name: string
  city: string
  occupancy_pct: number
  diversion_status: boolean
  specialties: string[]
  lat: number
  lng: number
}

export interface Analytics {
  avg_eta_ai: number
  avg_eta_baseline: number
  incidents_today: number
  dispatches_today: number
  overloads_prevented: number
}

import { http, HttpResponse } from 'msw'

export const MOCK_AMBULANCES = [
  {
    id: 'AMB-001', city: 'Delhi',
    current_lat: 28.7041, current_lng: 77.1025,
    status: 'available', type: 'ALS',
    equipment: ['defibrillator', 'ALS_kit', 'oxygen', 'stretcher', 'IV_kit'],
    speed_kmh: 44.0, crew_readiness: 0.95,
    assigned_incident_id: null, assigned_hospital_id: null, zone: 'North'
  },
  {
    id: 'AMB-002', city: 'Delhi',
    current_lat: 28.6304, current_lng: 77.2177,
    status: 'en_route', type: 'BLS',
    equipment: ['oxygen', 'stretcher'],
    speed_kmh: 38.0, crew_readiness: 0.80,
    assigned_incident_id: 'INC-001', assigned_hospital_id: null, zone: 'Central'
  },
  {
    id: 'AMB-003', city: 'Mumbai',
    current_lat: 19.0760, current_lng: 72.8777,
    status: 'unavailable', type: 'ALS',
    equipment: ['defibrillator', 'ALS_kit'],
    speed_kmh: 40.0, crew_readiness: 0.60,
    assigned_incident_id: null, assigned_hospital_id: null, zone: 'West'
  }
]

export const MOCK_HOSPITALS = [
  {
    id: 'HOSP-001', name: 'AIIMS Delhi', city: 'Delhi',
    lat: 28.5672, lng: 77.2100,
    type: 'multi-specialty',
    specialties: ['cardiac', 'trauma', 'neuro'],
    occupancy_pct: 68.0, er_wait_minutes: 24,
    icu_beds_available: 12, total_icu_beds: 20,
    trauma_support: true, acceptance_score: 0.84,
    diversion_status: false, incoming_patients: []
  },
  {
    id: 'HOSP-002', name: 'Safdarjung Hospital', city: 'Delhi',
    lat: 28.5688, lng: 77.2065,
    type: 'general',
    specialties: ['trauma', 'general'],
    occupancy_pct: 92.0, er_wait_minutes: 45,
    icu_beds_available: 2, total_icu_beds: 15,
    trauma_support: true, acceptance_score: 0.31,
    diversion_status: true, incoming_patients: ['INC-001']
  },
  {
    id: 'HOSP-003', name: 'KEM Hospital Mumbai', city: 'Mumbai',
    lat: 19.0041, lng: 72.8428,
    type: 'multi-specialty',
    specialties: ['cardiac', 'trauma'],
    occupancy_pct: 55.0, er_wait_minutes: 12,
    icu_beds_available: 8, total_icu_beds: 12,
    trauma_support: true, acceptance_score: 0.91,
    diversion_status: false, incoming_patients: []
  }
]

export const MOCK_DISPATCH = {
  id: 'DISP-001',
  incident_id: 'INC-001',
  patient_id: 'PAT-001',
  ambulance_id: 'AMB-001',
  hospital_id: 'HOSP-001',
  ambulance_score: 0.87,
  hospital_score: 0.79,
  route_score: 0.72,
  final_score: 0.81,
  eta_minutes: 6.4,
  distance_km: 4.2,
  rejected_ambulances: [
    { id: 'AMB-002', score: 0.61, eta_minutes: 9.2,
      reason: 'Lower combined dispatch utility than selected ambulance.',
      breakdown: { eta_score: 0.5, equipment_score: 0.6,
                   crew_readiness_score: 0.8, availability_score: 1.0 } }
  ],
  rejected_hospitals: [
    { id: 'HOSP-002', score: 0.12, travel_minutes: 5.1,
      occupancy_pct: 92.0, diversion_status: true,
      reason: 'Lower hospital suitability than selected destination.',
      breakdown: { specialty_score: 0.5, occupancy_score: 0.08,
                   er_wait_score: 0.25, travel_time_score: 0.87,
                   icu_score: 0.13 } }
  ],
  explanation_text: 'Selected ambulance AMB-001 for critical cardiac incident ' +
    'in Delhi based on response ETA (6.4 min), equipment match, crew readiness, ' +
    'and destination hospital HOSP-001 suitability.',
  fallback_hospital_id: 'HOSP-003',
  status: 'dispatched',
  created_at: new Date().toISOString(),
  baseline_eta_minutes: 9.1,
  overload_avoided: true,
  requires_human_review: false,
  review_reason: null,
  triage_confidence: 0.91,
  triage_version: 'nlp_v1'
}

export const MOCK_ANALYTICS = {
  avg_eta_ai: 6.4,
  avg_eta_baseline: 9.1,
  incidents_today: 7,
  dispatches_today: 6,
  hospitals_notified: 4,
  overloads_prevented: 2
}

export const MOCK_FAIRNESS = {
  ai_dispatch: {
    zones: {
      central: { avg_eta: 5.8, p90_eta: 8.9, specialty_match_rate: 94.2, overload_rate: 3.1 },
      mid: { avg_eta: 6.6, p90_eta: 10.7, specialty_match_rate: 91.4, overload_rate: 4.8 },
      peripheral: { avg_eta: 7.1, p90_eta: 12.2, specialty_match_rate: 88.6, overload_rate: 6.5 },
    },
    disparity_ratio: 1.224,
    equity_score: 88.8,
    equity_label: 'equitable',
    fairness_win: true,
    peripheral_penalty_pct: 22.4,
  },
  nearest_unit: {
    zones: {
      central: { avg_eta: 6.1, p90_eta: 9.8, specialty_match_rate: 71.2, overload_rate: 8.4 },
      mid: { avg_eta: 8.2, p90_eta: 13.6, specialty_match_rate: 66.7, overload_rate: 10.1 },
      peripheral: { avg_eta: 9.9, p90_eta: 16.8, specialty_match_rate: 61.5, overload_rate: 13.9 },
    },
    disparity_ratio: 1.623,
    equity_score: 68.9,
    equity_label: 'moderate disparity',
    fairness_win: false,
    peripheral_penalty_pct: 62.3,
  },
  comparison: {
    ai_more_equitable: true,
    disparity_improvement: 0.399,
    zones_where_ai_wins: ['central', 'mid', 'peripheral'],
    zones_where_ai_loses: [],
    equity_score_improvement: 19.9,
    summary: 'AI dispatch is more equitable than nearest-unit baseline, with lower disparity and better ETAs across all zones.',
  },
}

export const MOCK_BENCHMARK = {
  generated_at: '2024-01-15T10:30:00+00:00',
  total_incidents: 200,
  evaluation: {
    mode: 'standard',
    split: 'test',
    evaluation_dataset: 'test_incidents.json',
    evaluation_count: 200,
    training_dataset: 'train_incidents.json',
    training_count: 500,
    split_method: 'chronological (test = last 200 generated)',
    held_out: true,
    evaluation_generated_at: '2024-01-15T09:55:00+00:00',
  },
  strategies: {
    ai_dispatch: {
      avg_eta_minutes: 6.2,
      avg_total_time_minutes: 15.1,
      specialty_match_rate: 91.4,
      overload_events: 7,
      delayed_incidents: 18,
      p50_eta: 5.8,
      p90_eta: 11.6,
      p95_eta: 14.2,
      per_incident: [],
    },
    nearest_unit: {
      avg_eta_minutes: 8.7,
      avg_total_time_minutes: 18.6,
      specialty_match_rate: 64.8,
      overload_events: 31,
      delayed_incidents: 24,
      p50_eta: 8.1,
      p90_eta: 15.4,
      p95_eta: 18.9,
      per_incident: [],
    },
    random_dispatch: {
      avg_eta_minutes: 12.4,
      avg_total_time_minutes: 26.7,
      specialty_match_rate: 42.2,
      overload_events: 49,
      delayed_incidents: 39,
      p50_eta: 11.9,
      p90_eta: 23.5,
      p95_eta: 28.4,
      per_incident: [],
    },
  },
}

export const MOCK_LITERATURE_COMPARISON = {
  generated_at: '2024-01-15T11:00:00+00:00',
  papers: [
    {
      authors: 'Liu et al.',
      year: 2019,
      title: 'Dynamic ambulance redeployment and dispatching',
      journal: 'Transportation Research Part E',
      method: 'Approximate Dynamic Programming',
      method_short: 'ADP',
      improvement_over_baseline_pct: 22.4,
      context: 'Urban China, 3 cities',
      baseline: 'nearest available unit',
    },
    {
      authors: 'Schmid',
      year: 2012,
      title: 'Solving the dynamic ambulance relocation problem',
      journal: 'European Journal of Operational Research',
      method: 'Robust optimization',
      method_short: 'Robust Opt.',
      improvement_over_baseline_pct: 18.7,
      context: 'Vienna, Austria',
      baseline: 'static deployment',
    },
    {
      authors: 'Kergosien et al.',
      year: 2015,
      title: 'Generic model for online optimization of EMS',
      journal: 'Computers and Operations Research',
      method: 'Online optimization heuristic',
      method_short: 'Online Heur.',
      improvement_over_baseline_pct: 31.2,
      context: 'French metropolitan area',
      baseline: 'nearest available unit',
    },
    {
      authors: 'Maxwell et al.',
      year: 2010,
      title: 'Approximate dynamic programming for EMS',
      journal: 'INFORMS Journal on Computing',
      method: 'Approximate Dynamic Programming',
      method_short: 'ADP',
      improvement_over_baseline_pct: 26.8,
      context: 'Toronto, Canada',
      baseline: 'nearest available unit',
    },
  ],
  published_range: {
    from_year: 2010,
    to_year: 2019,
    min_improvement_pct: 18.7,
    max_improvement_pct: 31.2,
  },
  raid_nexus: {
    held_out: {
      year: 2024,
      method: 'Multi-objective scoring',
      improvement_over_baseline_pct: 27.9,
      source: 'benchmark_results.json',
    },
    cross_city: {
      year: 2024,
      method: 'Multi-objective scoring',
      improvement_over_baseline_pct: 25.8,
      source: 'cross_city_results.json',
    },
  },
  context_note:
    'Note: Direct comparison is not appropriate. Published studies use real EMS data in different urban contexts. RAID Nexus results are from synthetic data calibrated to Indian EMS statistics. The comparison is provided for situating our simulation results within the published range, not to claim equivalence.',
}

export const MOCK_PATIENT = {
  id: 'PAT-001', name: 'Arjun Sharma', age: 45,
  gender: 'male', mobile: '9876543210',
  location_lat: 28.6139, location_lng: 77.2090,
  chief_complaint: 'severe chest pain and shortness of breath',
  severity: 'critical', sos_mode: true,
  created_at: new Date().toISOString(),
  assigned_ambulance_id: 'AMB-001',
  assigned_hospital_id: 'HOSP-001',
  status: 'dispatched'
}

export const MOCK_INCIDENTS = [
  {
    id: 'INC-001', type: 'cardiac', severity: 'critical',
    patient_count: 1, location_lat: 28.6139, location_lng: 77.2090,
    city: 'Delhi', description: 'Chest pain',
    status: 'dispatched', created_at: new Date().toISOString(),
    patient_id: 'PAT-001',
    requires_human_review: false,
    review_reason: null,
    triage_confidence: 0.91,
    triage_version: 'nlp_v1'
  },
  {
    id: 'INC-002', type: 'trauma', severity: 'high',
    patient_count: 2, location_lat: 28.6304, location_lng: 77.2177,
    city: 'Delhi', description: 'Road accident',
    status: 'open', created_at: new Date().toISOString(),
    patient_id: null,
    requires_human_review: true,
    review_reason: 'Low confidence in incident type classification (0.48). Human review recommended before dispatch.',
    triage_confidence: 0.48,
    triage_version: 'nlp_v1'
  }
]

export const handlers = [
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      id: 'USR-ADMIN',
      username: 'admin',
      role: 'admin',
      full_name: 'Admin',
    })),
  http.post('/api/auth/login', () =>
    HttpResponse.json({
      access_token: 'test-admin-token',
      token_type: 'bearer',
      role: 'admin',
      username: 'admin',
    })),
  http.get('/api/ambulances', () =>
    HttpResponse.json(MOCK_AMBULANCES)),
  http.get('/api/hospitals', () =>
    HttpResponse.json(MOCK_HOSPITALS)),
  http.get('/api/incidents', () =>
    HttpResponse.json(MOCK_INCIDENTS)),
  http.get('/api/analytics', () =>
    HttpResponse.json(MOCK_ANALYTICS)),
  http.get('/api/benchmark', () =>
    HttpResponse.json(MOCK_BENCHMARK)),
  http.get('/api/demand/heatmap', () =>
    HttpResponse.json({
      city: 'Delhi',
      lookahead_minutes: 30,
      hotspots: [
        { lat: 28.6139, lng: 77.209, demand_score: 0.92, predicted_incidents: 2 },
        { lat: 28.6304, lng: 77.2177, demand_score: 0.72, predicted_incidents: 1 },
      ],
      preposition_recommendations: [],
      generated_at: new Date().toISOString(),
    })),
  http.get('/api/fairness', () =>
    HttpResponse.json(MOCK_FAIRNESS)),
  http.get('/api/literature-comparison', () =>
    HttpResponse.json(MOCK_LITERATURE_COMPARISON)),
  http.get('/api/overrides/stats', () =>
    HttpResponse.json({
      total_dispatches: 6,
      total_overrides: 1,
      override_rate_pct: 16.7,
      overrides_by_reason: { local_knowledge: 1 },
      avg_eta_ai: 6.4,
      avg_eta_override: 5.9,
      eta_change_on_override: -0.5,
      most_common_override_reason: 'local_knowledge',
    })),
  http.get('/api/patients/:id', () =>
    HttpResponse.json(MOCK_PATIENT)),
  http.get('/api/dispatch/:id', () =>
    HttpResponse.json(MOCK_DISPATCH)),
  http.post('/api/patients', () =>
    HttpResponse.json({
      patient: MOCK_PATIENT,
      dispatch_plan: MOCK_DISPATCH,
      notification_sent: true
    }, { status: 201 })),
  http.post('/api/incidents', () =>
    HttpResponse.json({
      incident: MOCK_INCIDENTS[0],
      dispatch_plan: MOCK_DISPATCH
    }, { status: 201 })),
  http.post('/api/simulate/scenario', async ({ request }) => {
    const { type } = await request.json()

    if (type === 'cardiac') {
      return HttpResponse.json({
        scenario: 'cardiac',
        dispatch_plan: {
          id: 'test-incident-id',
          ambulance_id: 'AMB-003',
          hospital_id: 'HOSP-001',
          hospital_name: 'AIIMS Delhi',
          eta_minutes: 7.4,
          final_score: 0.91,
          status: 'success',
        },
      })
    }

    if (type === 'overload') {
      return HttpResponse.json({
        scenario: 'overload',
        overload: {
          hospital_id: 'HOSP-005',
          occupancy_pct: 95,
          diversion_status: true,
        },
      })
    }

    if (type === 'breakdown') {
      return HttpResponse.json({
        scenario: 'breakdown',
        breakdown: {
          ambulance_id: 'AMB-007',
          expires_at: new Date(Date.now() + 60000).toISOString(),
        },
      })
    }

    if (type === 'traffic') {
      return HttpResponse.json({
        scenario: 'traffic',
        traffic: {
          city: 'Bengaluru',
          multiplier: 2.5,
          expires_at: new Date(Date.now() + 60000).toISOString(),
        },
      })
    }

    if (type === 'mass_casualty') {
      return HttpResponse.json({
        scenario: 'mass_casualty',
        mass_casualty: {
          incidents: MOCK_INCIDENTS,
          dispatches: [MOCK_DISPATCH],
          manual_assignments_required: 5,
        },
      })
    }

    if (type === 'hospital_overload') {
      return HttpResponse.json({
        scenario: 'hospital_overload',
        overload: {
          hospital_id: 'HOSP-001',
          occupancy_pct: 95,
          diversion_status: true,
        },
      })
    }

    if (type === 'traffic_surge') {
      return HttpResponse.json({
        scenario: 'traffic_surge',
        traffic: {
          city: 'Delhi',
          multiplier: 2.5,
          expires_at: new Date(Date.now() + 120000).toISOString(),
        },
      })
    }

    if (type === 'multi_zone') {
      return HttpResponse.json({
        scenario: 'multi_zone',
        multi_zone: {
          zones: ['North', 'Central', 'South', 'East'],
          results: [{ incident: MOCK_INCIDENTS[0], dispatch_plan: MOCK_DISPATCH }],
        },
      })
    }

    return HttpResponse.json({ scenario: type || 'unknown' }, { status: 200 })
  }),
  http.post('/api/simulate/traffic', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({
      traffic: {
        city: body.city || 'Delhi',
        multiplier: body.multiplier || 1,
        expires_at: new Date(Date.now() + 300000).toISOString(),
      },
    })
  }),
  http.post('/api/dispatch', () =>
    HttpResponse.json(MOCK_DISPATCH)),
]

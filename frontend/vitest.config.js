export default {
  define: {
    MOCK_DISPATCH: {
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
      rejected_ambulances: [],
      rejected_hospitals: [],
      explanation_text:
        'Selected ambulance AMB-001 for critical cardiac incident in Delhi based on response ETA (6.4 min), equipment match, crew readiness, and destination hospital HOSP-001 suitability.',
      fallback_hospital_id: 'HOSP-003',
      status: 'dispatched',
      created_at: '2026-01-01T00:00:00.000Z',
      baseline_eta_minutes: 9.1,
      overload_avoided: true,
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    fakeTimers: {
      shouldAdvanceTime: true,
    },
  },
}

import { describe, it, expect } from 'vitest'
import {
  fetchAmbulances, fetchHospitals, fetchIncidents,
  fetchAnalytics, fetchPatient, createPatient,
  createIncident, triggerScenario, triggerDispatch
} from '../services/api'
import {
  MOCK_AMBULANCES, MOCK_HOSPITALS, MOCK_INCIDENTS,
  MOCK_ANALYTICS, MOCK_PATIENT, MOCK_DISPATCH
} from './mocks/handlers'

describe('api.js', () => {
  it('fetchAmbulances returns ambulance array', async () => {
    const result = await fetchAmbulances()
    expect(result).toHaveLength(3)
    expect(result[0].id).toBe('AMB-001')
    expect(result[0]).toHaveProperty('current_lat')
    expect(result[0]).toHaveProperty('equipment')
    expect(Array.isArray(result[0].equipment)).toBe(true)
  })

  it('fetchHospitals returns hospital array with required fields', async () => {
    const result = await fetchHospitals()
    expect(result).toHaveLength(3)
    const h = result[0]
    expect(h).toHaveProperty('occupancy_pct')
    expect(h).toHaveProperty('er_wait_minutes')
    expect(h).toHaveProperty('icu_beds_available')
    expect(h).toHaveProperty('diversion_status')
    expect(Array.isArray(h.specialties)).toBe(true)
    expect(Array.isArray(h.incoming_patients)).toBe(true)
  })

  it('fetchIncidents returns incident array', async () => {
    const result = await fetchIncidents()
    expect(result).toHaveLength(2)
    expect(result[0]).toHaveProperty('severity')
    expect(result[0]).toHaveProperty('city')
  })

  it('fetchAnalytics returns all required metric fields', async () => {
    const result = await fetchAnalytics()
    expect(result).toHaveProperty('avg_eta_ai')
    expect(result).toHaveProperty('avg_eta_baseline')
    expect(result).toHaveProperty('incidents_today')
    expect(result).toHaveProperty('dispatches_today')
    expect(result).toHaveProperty('hospitals_notified')
    expect(result).toHaveProperty('overloads_prevented')
    expect(result.avg_eta_ai).toBe(6.4)
    expect(result.avg_eta_baseline).toBe(9.1)
  })

  it('fetchPatient returns patient with assigned fields', async () => {
    const result = await fetchPatient('PAT-001')
    expect(result.id).toBe('PAT-001')
    expect(result.severity).toBe('critical')
    expect(result.assigned_ambulance_id).toBe('AMB-001')
  })

  it('createPatient posts correct body and returns patient + dispatch', async () => {
    const body = {
      name: 'Arjun Sharma', age: 45, gender: 'male',
      mobile: '9876543210', location_lat: 28.6139, location_lng: 77.2090,
      chief_complaint: 'severe chest pain', sos_mode: true
    }
    const result = await createPatient(body)
    expect(result).toHaveProperty('patient')
    expect(result).toHaveProperty('dispatch_plan')
    expect(result.notification_sent).toBe(true)
    expect(result.patient.severity).toBe('critical')
    expect(result.dispatch_plan.ambulance_id).toBe('AMB-001')
  })

  it('createIncident posts and returns incident + dispatch', async () => {
    const body = {
      city: 'Delhi', type: 'cardiac', severity: 'critical',
      patient_count: 1, location_lat: 28.6139, location_lng: 77.2090,
      description: 'Chest pain', patient_id: null
    }
    const result = await createIncident(body)
    expect(result).toHaveProperty('incident')
    expect(result).toHaveProperty('dispatch_plan')
  })

  it('triggerScenario posts correct type and returns result', async () => {
    const result = await triggerScenario('cardiac')
    expect(result).toHaveProperty('scenario')
    expect(result.scenario).toBe('cardiac')
  })

  it('triggerDispatch posts incident_id and returns dispatch plan', async () => {
    const result = await triggerDispatch('INC-001')
    expect(result.id).toBe('DISP-001')
    expect(result.ambulance_id).toBe('AMB-001')
  })

  it('fetchAmbulances throws on server error', async () => {
    const { http, HttpResponse } = await import('msw')
    const { server } = await import('./mocks/server')
    server.use(
      http.get('/api/ambulances', () =>
        HttpResponse.json({ detail: 'Internal error' }, { status: 500 }))
    )
    await expect(fetchAmbulances()).rejects.toThrow()
  })
})

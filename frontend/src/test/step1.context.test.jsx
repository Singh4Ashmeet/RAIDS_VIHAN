import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import { MockWebSocket } from './mocks/websocket'
import {
  MOCK_AMBULANCES, MOCK_HOSPITALS, MOCK_DISPATCH
} from './mocks/handlers'

describe('LiveStateContext', () => {
  beforeEach(() => { vi.stubGlobal('WebSocket', MockWebSocket) })
  afterEach(() => { vi.unstubAllGlobals() })

  it('connects to /ws/live on mount', async () => {
    const { LiveStateProvider } = await import('../context/LiveStateContext')
    render(<LiveStateProvider><div data-testid="child">ok</div></LiveStateProvider>)
    await waitFor(() => {
      expect(MockWebSocket.instance).toBeDefined()
      expect(MockWebSocket.instance.url).toMatch('/ws/live')
    })
  })

  it('sets isConnected true after WebSocket opens', async () => {
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => { expect(contextValue.isConnected).toBe(true) })
  })

  it('populates ambulances and hospitals from state_snapshot', async () => {
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'state_snapshot',
        ambulances: MOCK_AMBULANCES,
        hospitals: MOCK_HOSPITALS,
        traffic_multipliers: { Delhi: 1.0 }
      })
    })
    await waitFor(() => {
      expect(contextValue.ambulances).toHaveLength(3)
      expect(contextValue.ambulances[0].id).toBe('AMB-001')
      expect(contextValue.hospitals).toHaveLength(3)
      expect(contextValue.hospitals[0].name).toBe('AIIMS Delhi')
    })
  })

  it('updates ambulances on simulation_tick without replacing hospitals', async () => {
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'state_snapshot',
        ambulances: MOCK_AMBULANCES,
        hospitals: MOCK_HOSPITALS,
        traffic_multipliers: {}
      })
    })
    const updatedAmbulances = [
      { ...MOCK_AMBULANCES[0], current_lat: 28.7100, current_lng: 77.1050 }
    ]
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'simulation_tick',
        ambulances: updatedAmbulances,
        hospitals: MOCK_HOSPITALS,
        timestamp: new Date().toISOString()
      })
    })
    await waitFor(() => {
      expect(contextValue.ambulances[0].current_lat).toBe(28.7100)
      expect(contextValue.hospitals).toHaveLength(3)
    })
  })

  it('sets latestDispatch and prepends to dispatchHistory on dispatch_created', async () => {
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'dispatch_created',
        dispatch_plan: MOCK_DISPATCH
      })
    })
    await waitFor(() => {
      expect(contextValue.latestDispatch).not.toBeNull()
      expect(contextValue.latestDispatch.id).toBe('DISP-001')
      expect(contextValue.dispatchHistory).toHaveLength(1)
      expect(contextValue.dispatchHistory[0].id).toBe('DISP-001')
    })
  })

  it('prepends notification on hospital_notification event', async () => {
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => MockWebSocket.instance?.onopen)
    const notification = {
      type: 'hospital_notification',
      hospital_id: 'HOSP-001',
      patient_name: 'Arjun Sharma',
      patient_age: 45,
      patient_gender: 'male',
      chief_complaint: 'chest pain',
      severity: 'critical',
      eta_minutes: 6.4,
      ambulance_id: 'AMB-001',
      prep_checklist: ['Prepare cardiac ICU bed', 'Alert cardiologist']
    }
    act(() => { MockWebSocket.instance.simulateMessage(notification) })
    await waitFor(() => {
      expect(contextValue.notifications).toHaveLength(1)
      expect(contextValue.notifications[0].patient_name).toBe('Arjun Sharma')
      expect(contextValue.notifications[0].hospital_id).toBe('HOSP-001')
    })
  })

  it('sets isConnected false and attempts reconnect on disconnect', async () => {
    vi.useFakeTimers()
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => { MockWebSocket.instance.simulateDisconnect() })
    await waitFor(() => { expect(contextValue.isConnected).toBe(false) })
    const firstInstance = MockWebSocket.instance
    act(() => { vi.advanceTimersByTime(3100) })
    await waitFor(() => {
      expect(MockWebSocket.instance).not.toBe(firstInstance)
    })
    vi.useRealTimers()
  })

  it('exposes setLatestDispatch to allow external plan injection', async () => {
    const { LiveStateProvider, useLiveState } =
      await import('../context/LiveStateContext')
    let contextValue
    function Consumer() { contextValue = useLiveState(); return null }
    render(<LiveStateProvider><Consumer /></LiveStateProvider>)
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => { contextValue.setLatestDispatch(MOCK_DISPATCH) })
    await waitFor(() => {
      expect(contextValue.latestDispatch?.id).toBe('DISP-001')
    })
  })
})

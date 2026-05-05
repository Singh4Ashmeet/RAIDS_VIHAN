import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import useAuthStore from '../store/authStore'
import useDispatchStore from '../store/dispatchStore'
import { MockWebSocket } from './mocks/websocket'

function resetStores() {
  useAuthStore.setState({
    user: { username: 'admin', role: 'admin' },
    token: 'admin-token',
    role: 'admin',
    username: 'admin',
    isAuthenticated: true,
    hasHydrated: true,
    isLoading: false,
    error: null,
  })
  useDispatchStore.setState({
    incidents: [],
    ambulances: [],
    hospitals: [],
    lastDispatch: null,
    dispatchHistory: [],
    notifications: [],
    anomalyAlerts: [],
    wsStatus: 'disconnected',
    systemStatus: 'normal',
    trafficMultiplier: 1,
    activeRoute: null,
    alternateRoutes: [],
    ambulanceOptions: [],
    routeChange: null,
    _ws: null,
    _wsReconnectAttempts: 0,
    _wsReconnectTimer: null,
    _wsManualClose: false,
  })
  MockWebSocket.instances = []
  MockWebSocket.instance = null
  MockWebSocket.autoOpen = true
}

describe('WebSocket reconnection', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', MockWebSocket)
    resetStores()
  })

  afterEach(() => {
    useDispatchStore.getState().disconnectWS()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('reconnects with exponential backoff after live feed disconnects', async () => {
    useDispatchStore.getState().connectWS()
    await vi.advanceTimersByTimeAsync(0)

    expect(MockWebSocket.instances).toHaveLength(1)
    expect(useDispatchStore.getState().wsStatus).toBe('connected')

    MockWebSocket.instances[0].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(1)

    await vi.advanceTimersByTimeAsync(1999)
    expect(MockWebSocket.instances).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(1)
    await vi.runOnlyPendingTimersAsync()
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(useDispatchStore.getState().wsStatus).toBe('connected')

    MockWebSocket.instances[1].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(1)

    await vi.advanceTimersByTimeAsync(2000)
    await vi.runOnlyPendingTimersAsync()
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('uses 2s, 3s, then 4.5s delays for repeated failed connections', async () => {
    MockWebSocket.autoOpen = false
    useDispatchStore.getState().connectWS()
    expect(MockWebSocket.instances).toHaveLength(1)

    MockWebSocket.instances[0].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(1)
    await vi.advanceTimersByTimeAsync(1999)
    expect(MockWebSocket.instances).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(MockWebSocket.instances).toHaveLength(2)

    MockWebSocket.instances[1].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(2)
    await vi.advanceTimersByTimeAsync(2999)
    expect(MockWebSocket.instances).toHaveLength(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(MockWebSocket.instances).toHaveLength(3)

    MockWebSocket.instances[2].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(3)
    await vi.advanceTimersByTimeAsync(4499)
    expect(MockWebSocket.instances).toHaveLength(3)
    await vi.advanceTimersByTimeAsync(1)
    expect(MockWebSocket.instances).toHaveLength(4)
  })

  it('blocks cross-city route_change routes and keeps the existing local route', async () => {
    useDispatchStore.setState({
      incidents: [{ id: 'INC-MUM-1', city: 'Mumbai' }],
      ambulances: [
        { id: 'AMB-MUM-1', city: 'Mumbai' },
        { id: 'AMB-HYD-1', city: 'Hyderabad' },
      ],
      hospitals: [
        { id: 'HOSP-MUM-1', city: 'Mumbai' },
        { id: 'HOSP-HYD-1', city: 'Hyderabad' },
      ],
      activeRoute: {
        dispatch_id: 'DISP-1',
        incident_id: 'INC-MUM-1',
        ambulance_id: 'AMB-MUM-1',
        hospital_id: 'HOSP-MUM-1',
        service_city: 'Mumbai',
        coordinates: [[72.87, 19.07], [72.83, 19.12]],
      },
    })

    useDispatchStore.getState().connectWS()
    await vi.advanceTimersByTimeAsync(0)

    MockWebSocket.instances[0].simulateMessage({
      type: 'route_change',
      dispatch_id: 'DISP-1',
      label: 'Manual escalation required; no same-city unit/hospital available',
      manual_escalation: true,
      reroute_blocked_reason: 'No feasible same-city dispatch available; manual mutual-aid escalation required.',
      old_route: useDispatchStore.getState().activeRoute,
      new_route: {
        dispatch_id: 'DISP-1',
        incident_id: 'INC-MUM-1',
        ambulance_id: 'AMB-HYD-1',
        hospital_id: 'HOSP-HYD-1',
        service_city: 'Mumbai',
        coordinates: [[78.48, 17.38], [72.87, 19.07]],
      },
      alternate_routes: [
        {
          incident_id: 'INC-MUM-1',
          ambulance_id: 'AMB-HYD-1',
          hospital_id: 'HOSP-HYD-1',
          service_city: 'Mumbai',
          coordinates: [[78.48, 17.38], [72.87, 19.07]],
        },
      ],
    })

    const state = useDispatchStore.getState()
    expect(state.activeRoute.ambulance_id).toBe('AMB-MUM-1')
    expect(state.activeRoute.hospital_id).toBe('HOSP-MUM-1')
    expect(state.routeChange.new_route).toBeNull()
    expect(state.alternateRoutes).toHaveLength(0)
    expect(state.notifications[0].message).toMatch(/manual escalation/i)
  })
})

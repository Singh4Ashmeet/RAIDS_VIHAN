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

    await vi.advanceTimersByTimeAsync(999)
    expect(MockWebSocket.instances).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(1)
    await vi.runOnlyPendingTimersAsync()
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(useDispatchStore.getState().wsStatus).toBe('connected')

    MockWebSocket.instances[1].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(1)

    await vi.advanceTimersByTimeAsync(1000)
    await vi.runOnlyPendingTimersAsync()
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('uses 1s, 2s, then 4s delays for repeated failed connections', async () => {
    MockWebSocket.autoOpen = false
    useDispatchStore.getState().connectWS()
    expect(MockWebSocket.instances).toHaveLength(1)

    MockWebSocket.instances[0].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(MockWebSocket.instances).toHaveLength(2)

    MockWebSocket.instances[1].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(2)
    await vi.advanceTimersByTimeAsync(1999)
    expect(MockWebSocket.instances).toHaveLength(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(MockWebSocket.instances).toHaveLength(3)

    MockWebSocket.instances[2].simulateDisconnect()
    expect(useDispatchStore.getState()._wsReconnectAttempts).toBe(3)
    await vi.advanceTimersByTimeAsync(4000)
    expect(MockWebSocket.instances).toHaveLength(4)
  })
})

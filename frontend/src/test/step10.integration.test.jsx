import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MockWebSocket } from './mocks/websocket'
import {
  MOCK_AMBULANCES, MOCK_HOSPITALS, MOCK_DISPATCH
} from './mocks/handlers'
import App from '../App'
 
describe('Full app integration', () => {
  beforeEach(() => { vi.stubGlobal('WebSocket', MockWebSocket) })
  afterEach(() => { vi.unstubAllGlobals() })
 
  it('command center shows dispatch card after WebSocket dispatch event', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /admin/i }))
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'state_snapshot',
        ambulances: MOCK_AMBULANCES,
        hospitals: MOCK_HOSPITALS,
        traffic_multipliers: {}
      })
    })
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'dispatch_created',
        dispatch_plan: MOCK_DISPATCH
      })
    })
    await waitFor(() => {
      expect(screen.getByText(/AMB-001/)).toBeInTheDocument()
      expect(screen.getByText(/AIIMS Delhi/)).toBeInTheDocument()
    })
  })
 
  it('fleet tab shows ambulance table on click', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /admin/i }))
    await userEvent.click(screen.getByText(/fleet/i))
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'state_snapshot',
        ambulances: MOCK_AMBULANCES,
        hospitals: MOCK_HOSPITALS,
        traffic_multipliers: {}
      })
    })
    await waitFor(() => {
      expect(screen.getByText('AMB-001')).toBeInTheDocument()
    })
  })
 
  it('user portal SOS form submits and shows success', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /user/i }))
    await userEvent.type(
      screen.getByLabelText(/name|full name/i), 'Test User'
    )
    await userEvent.type(screen.getByLabelText(/age/i), '35')
    await userEvent.selectOptions(screen.getByLabelText(/gender/i), 'male')
    await userEvent.type(
      screen.getByLabelText(/mobile|phone/i), '9999999999'
    )
    await userEvent.type(
      screen.getByLabelText(/complaint/i), 'severe chest pain'
    )
    await userEvent.click(
      screen.getByRole('button', { name: /send.*sos|sos/i })
    )
    await waitFor(() => {
      expect(
        screen.getByText(/sos received|dispatched|confirmed/i)
      ).toBeInTheDocument()
    })
  })
 
  it('whole app renders with zero emoji', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /admin/i }))
    const text = document.body.textContent || ''
    const emojiRegex = /[\u{1F300}-\u{1FFFF}]/u
    expect(emojiRegex.test(text)).toBe(false)
  })
 
  it('hospital finder updates when WebSocket pushes new hospital data', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /user/i }))
    await userEvent.click(screen.getByText(/hospital finder/i))
    await waitFor(() => MockWebSocket.instance?.onopen)
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'state_snapshot',
        ambulances: MOCK_AMBULANCES,
        hospitals: MOCK_HOSPITALS,
        traffic_multipliers: {}
      })
    })
    await waitFor(() => {
      expect(screen.getByText('AIIMS Delhi')).toBeInTheDocument()
    })
    const updatedHospitals = [
      { ...MOCK_HOSPITALS[0], occupancy_pct: 97.0, diversion_status: true }
    ]
    act(() => {
      MockWebSocket.instance.simulateMessage({
        type: 'simulation_tick',
        ambulances: MOCK_AMBULANCES,
        hospitals: updatedHospitals,
        timestamp: new Date().toISOString()
      })
    })
    await waitFor(() => {
      expect(screen.getByText(/97/)).toBeInTheDocument()
    })
  })
 
  it('analytics tab fetches and displays data', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /admin/i }))
    await userEvent.click(screen.getByText(/analytics/i))
    await waitFor(() => {
      expect(screen.getByText(/incidents today/i)).toBeInTheDocument()
      expect(screen.getByText('7')).toBeInTheDocument()
    })
  })
})

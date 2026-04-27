import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import App from '../App'
import useAuthStore from '../store/authStore'
import useDispatchStore from '../store/dispatchStore'
import { MockWebSocket } from './mocks/websocket'

function resetAuth(role = null) {
  localStorage.clear()
  useAuthStore.setState({
    user: role ? { username: role, role } : null,
    token: role ? `${role}-token` : null,
    role,
    username: role,
    isAuthenticated: Boolean(role),
    hasHydrated: Boolean(role),
    isLoading: false,
    error: null,
  })
  if (role) {
    localStorage.setItem('raid_token', `${role}-token`)
    localStorage.setItem('raid_role', role)
    localStorage.setItem('raid_username', role)
  }
}

function resetDispatch() {
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
  })
}

describe('App routed structure', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    window.history.pushState({}, '', '/')
    resetAuth()
    resetDispatch()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetAuth()
    resetDispatch()
  })

  it('renders the landing route without the legacy role-switcher shell', async () => {
    render(<App />)

    expect(await screen.findByText('RAID Nexus')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/role selector/i)).not.toBeInTheDocument()
  })

  it('renders the login route and password visibility control', async () => {
    window.history.pushState({}, '', '/login')
    render(<App />)

    expect(await screen.findByLabelText('Username', { selector: 'input' })).toBeInTheDocument()
    const passwordInput = screen.getByLabelText('Password', { selector: 'input' })
    expect(passwordInput).toHaveAttribute('type', 'password')

    await userEvent.click(screen.getByRole('button', { name: /show password/i }))
    expect(passwordInput).toHaveAttribute('type', 'text')
  })

  it('renders the modern admin route for authenticated admins', async () => {
    resetAuth('admin')
    window.history.pushState({}, '', '/admin/command')

    render(<App />)

    expect(await screen.findByRole('heading', { name: /command center/i })).toBeInTheDocument()
    expect(screen.getByText(/fleet & hospitals/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(MockWebSocket.instance?.url).toMatch('/ws/live')
    })
  })

  it('renders the modern user SOS route for authenticated users', async () => {
    resetAuth('user')
    window.history.pushState({}, '', '/user/sos')

    render(<App />)

    expect(await screen.findByRole('heading', { name: /emergency sos/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /voice report/i })).toBeInTheDocument()
  })
})

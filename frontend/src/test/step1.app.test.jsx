import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MockWebSocket } from './mocks/websocket'
import App from '../App'

describe('App scaffold', () => {
  beforeEach(() => { vi.stubGlobal('WebSocket', MockWebSocket) })
  afterEach(() => { vi.unstubAllGlobals() })

  it('renders role selector with Admin and User buttons', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /admin/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /user/i })).toBeInTheDocument()
  })

  it('shows admin tabs by default when Admin is selected', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /admin/i }))
    expect(screen.getByText(/command center/i)).toBeInTheDocument()
    expect(screen.getByText(/fleet/i)).toBeInTheDocument()
    expect(screen.getByText(/analytics/i)).toBeInTheDocument()
    expect(screen.getByText(/scenario/i)).toBeInTheDocument()
  })

  it('shows user tabs when User is selected', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /user/i }))
    expect(screen.getByText(/emergency sos/i)).toBeInTheDocument()
    expect(screen.getByText(/my status/i)).toBeInTheDocument()
    expect(screen.getByText(/hospital finder/i)).toBeInTheDocument()
  })

  it('switches portal content when role is toggled', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /user/i }))
    expect(screen.getByText(/emergency sos/i)).toBeInTheDocument()
    expect(screen.queryByText(/fleet/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /admin/i }))
    expect(screen.getByText(/fleet/i)).toBeInTheDocument()
    expect(screen.queryByText(/emergency sos/i)).not.toBeInTheDocument()
  })

  it('displays connection status indicator', async () => {
    render(<App />)
    expect(screen.getByText(/live|reconnecting/i)).toBeInTheDocument()
  })

  it('contains no emoji characters in rendered output', () => {
    render(<App />)
    const text = document.body.textContent || ''
    const emojiRegex = /[\u{1F300}-\u{1FFFF}]/u
    expect(emojiRegex.test(text)).toBe(false)
  })
})

import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import ScenarioLab from '../pages/admin/ScenarioLab'
import { server } from './mocks/server'
import useDispatchStore from '../store/dispatchStore'

function resetDispatchStore() {
  useDispatchStore.setState({
    incidents: [],
    ambulances: [],
    hospitals: [],
    lastDispatch: null,
    activeRoute: null,
    routeChange: null,
    dispatchHistory: [],
    notifications: [],
    wsStatus: 'connected',
    systemStatus: 'normal',
    trafficMultiplier: 1,
    simulationMode: true,
    _ws: null,
  })
}

describe('ScenarioLab page', () => {
  beforeEach(() => {
    resetDispatchStore()
  })

  it('renders the split-panel simulator shell with analytics and live stats', async () => {
    server.use(
      http.get('/api/analytics', () =>
        HttpResponse.json({
          avg_eta_ai: 5.2,
          avg_eta_baseline: 8.9,
          incidents_today: 12,
          dispatches_today: 10,
          overloads_prevented: 2,
        }))
    )

    render(<ScenarioLab />)

    expect(await screen.findByText('Run drills and watch how dispatch decisions change.')).toBeInTheDocument()
    expect(screen.getByText('Delhi service area')).toBeInTheDocument()
    expect(screen.getByText('Run Order')).toBeInTheDocument()
    expect(screen.getByText('1. Pick city')).toBeInTheDocument()
    expect(screen.getByLabelText(/Units:/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Incidents:/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Traffic:/i)).toBeInTheDocument()
    expect(await screen.findByText('Avg AI ETA 5.2 min')).toBeInTheDocument()
  })

  it('renders all four prompt scenario presets', async () => {
    render(<ScenarioLab />)

    expect(await screen.findByText('Mass Casualty Event')).toBeInTheDocument()
    expect(screen.getByText('Hospital Overload')).toBeInTheDocument()
    expect(screen.getByText('Traffic Surge')).toBeInTheDocument()
    expect(screen.getByText('Multi-Zone')).toBeInTheDocument()
  })

  it('renders a readable active dispatch and hides raw UUIDs from the operator list', async () => {
    render(<ScenarioLab />)

    expect(await screen.findByText('No dispatch selected')).toBeInTheDocument()
    expect(screen.getByText(/Active Incidents/i)).toBeInTheDocument()
    expect(screen.queryByText(/[0-9a-f]{8}-[0-9a-f]{4}/i)).not.toBeInTheDocument()
  })

  it('runs mass casualty, overload, traffic surge, and multi-zone presets', async () => {
    const user = userEvent.setup()
    render(<ScenarioLab />)

    for (const label of ['Mass Casualty Event', 'Hospital Overload', 'Traffic Surge', 'Multi-Zone']) {
      await user.click(await screen.findByRole('button', { name: new RegExp(label, 'i') }))
      expect(await screen.findByText(new RegExp(`${label} scenario triggered`, 'i'))).toBeInTheDocument()
    }

    expect(await screen.findByText(/AMB-001 -> HOSP-001/i)).toBeInTheDocument()
  })

  it('applies the traffic multiplier through the modal connection', async () => {
    const user = userEvent.setup()
    render(<ScenarioLab />)

    await user.click(await screen.findByLabelText('Traffic: 1.0x'))
    const dialog = await screen.findByRole('dialog')
    const slider = within(dialog).getByRole('slider')
    fireEvent.change(slider, { target: { value: '2.4' } })
    await user.click(within(dialog).getByRole('button', { name: /Apply Traffic/i }))

    expect(await screen.findByText(/Traffic multiplier set to 2.4x for Delhi/i)).toBeInTheDocument()
  })

  it('shows preset API failures in the alert feed without crashing the page', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/simulate/scenario', () =>
        HttpResponse.json({ detail: 'Scenario failed' }, { status: 500 }))
    )

    render(<ScenarioLab />)

    await user.click(await screen.findByRole('button', { name: /Mass Casualty Event/i }))

    expect(await screen.findByText('Scenario failed')).toBeInTheDocument()
    expect(screen.getByText('Alert Feed')).toBeInTheDocument()
  })

  it('disables the other presets while one preset is running', async () => {
    const user = userEvent.setup()
    let releaseMassCasualtyRequest

    server.use(
      http.post('/api/simulate/scenario', async ({ request }) => {
        const { type } = await request.json()
        if (type === 'mass_casualty') {
          await new Promise((resolve) => {
            releaseMassCasualtyRequest = resolve
          })
        }
        return HttpResponse.json({ scenario: type || 'unknown' })
      })
    )

    render(<ScenarioLab />)

    await user.click(await screen.findByRole('button', { name: /Mass Casualty Event/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Hospital Overload/i })).toBeDisabled()
      expect(screen.getByRole('button', { name: /Traffic Surge/i })).toBeDisabled()
      expect(screen.getByRole('button', { name: /Multi-Zone/i })).toBeDisabled()
    })

    releaseMassCasualtyRequest?.()
  })
})

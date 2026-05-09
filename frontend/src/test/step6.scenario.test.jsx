import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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
    dispatchHistory: [],
    notifications: [],
    wsStatus: 'connected',
    systemStatus: 'normal',
    _ws: null,
  })
}

describe('ScenarioLab page', () => {
  beforeEach(() => {
    resetDispatchStore()
  })

  it('renders analytics strip with all 5 pills and highlights AI ETA improvement', async () => {
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

    expect(await screen.findByLabelText('Incidents: 12')).toBeInTheDocument()
    expect(screen.getByLabelText('Dispatches: 10')).toBeInTheDocument()
    expect(screen.getByLabelText('AI ETA: 5.2 min')).toBeInTheDocument()
    expect(screen.getByLabelText('Baseline ETA: 8.9 min')).toBeInTheDocument()
    expect(screen.getByLabelText('Overloads prevented: 2')).toBeInTheDocument()
    expect(screen.getByText('5.2 min')).toHaveClass('text-emerald-400')
  })

  it('renders all 4 scenario cards', async () => {
    render(<ScenarioLab />)

    expect(await screen.findByText('Cardiac P1 Dispatch')).toBeInTheDocument()
    expect(screen.getByText('Hospital Overload')).toBeInTheDocument()
    expect(screen.getByText('Ambulance Breakdown')).toBeInTheDocument()
    expect(screen.getByText('Traffic Spike')).toBeInTheDocument()
  })

  it('runs the cardiac scenario and renders the step trace', async () => {
    const user = userEvent.setup()
    render(<ScenarioLab />)

    const cardiacCard = await screen.findByRole('region', {
      name: /cardiac p1 dispatch scenario/i,
    })

    await user.click(
      within(cardiacCard).getByRole('button', {
        name: /run cardiac p1 dispatch scenario/i,
      })
    )

    expect(await screen.findByText('Incident created')).toBeInTheDocument()
  })

  it('runs overload, breakdown, and traffic scenarios and renders their traces', async () => {
    const user = userEvent.setup()
    render(<ScenarioLab />)

    const cases = [
      {
        region: /hospital overload scenario/i,
        button: /run hospital overload scenario/i,
        trace: 'Hospital targeted',
      },
      {
        region: /ambulance breakdown scenario/i,
        button: /run ambulance breakdown scenario/i,
        trace: 'Ambulance taken offline',
      },
      {
        region: /traffic spike scenario/i,
        button: /run traffic spike scenario/i,
        trace: 'City affected',
      },
    ]

    for (const scenario of cases) {
      const card = await screen.findByRole('region', { name: scenario.region })
      await user.click(within(card).getByRole('button', { name: scenario.button }))
      expect(await screen.findByText(scenario.trace)).toBeInTheDocument()
    }
  })

  it('renders the fallback trace state when cardiac returns HTTP 207', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('/api/simulate/scenario', async ({ request }) => {
        const { type } = await request.json()

        if (type === 'cardiac') {
          return HttpResponse.json({
            scenario: 'cardiac',
            dispatch_status: 'fallback',
            dispatch_message: 'Heuristic fallback route selected',
            dispatch_plan: {
              id: 'fallback-dispatch-id',
              ambulance_id: 'AMB-009',
              hospital_id: 'HOSP-001',
              hospital_name: 'AIIMS Delhi',
              eta_minutes: 9.3,
              final_score: 0.71,
              status: 'fallback',
            },
          }, { status: 207 })
        }

        return HttpResponse.json({ scenario: type || 'unknown' })
      })
    )

    render(<ScenarioLab />)

    const cardiacCard = await screen.findByRole('region', {
      name: /cardiac p1 dispatch scenario/i,
    })

    await user.click(
      within(cardiacCard).getByRole('button', {
        name: /run cardiac p1 dispatch scenario/i,
      })
    )

    expect(await screen.findByText('Heuristic fallback route selected')).toBeInTheDocument()
  })

  it('shows the scenario failed card message when the API errors', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('/api/simulate/scenario', () =>
        HttpResponse.json({ detail: 'Scenario failed' }, { status: 500 }))
    )

    render(<ScenarioLab />)

    const cardiacCard = await screen.findByRole('region', {
      name: /cardiac p1 dispatch scenario/i,
    })

    await user.click(
      within(cardiacCard).getByRole('button', {
        name: /run cardiac p1 dispatch scenario/i,
      })
    )

    expect(await within(cardiacCard).findByText('Scenario failed')).toBeInTheDocument()
  })

  it('disables the other three cards while one scenario is running', async () => {
    const user = userEvent.setup()
    let releaseCardiacRequest

    server.use(
      http.post('/api/simulate/scenario', async ({ request }) => {
        const { type } = await request.json()

        if (type === 'cardiac') {
          await new Promise((resolve) => {
            releaseCardiacRequest = resolve
          })

          return HttpResponse.json({
            scenario: 'cardiac',
            dispatch_plan: {
              id: 'slow-cardiac-id',
              ambulance_id: 'AMB-003',
              hospital_id: 'HOSP-001',
              hospital_name: 'AIIMS Delhi',
              eta_minutes: 7.4,
              final_score: 0.91,
              status: 'success',
            },
          })
        }

        return HttpResponse.json({ scenario: type || 'unknown' })
      })
    )

    render(<ScenarioLab />)

    const cardiacCard = await screen.findByRole('region', {
      name: /cardiac p1 dispatch scenario/i,
    })
    const overloadCard = screen.getByRole('region', { name: /hospital overload scenario/i })
    const breakdownCard = screen.getByRole('region', { name: /ambulance breakdown scenario/i })
    const trafficCard = screen.getByRole('region', { name: /traffic spike scenario/i })

    await user.click(
      within(cardiacCard).getByRole('button', {
        name: /run cardiac p1 dispatch scenario/i,
      })
    )

    await waitFor(() => {
      expect(
        within(overloadCard).getByRole('button', {
          name: /run hospital overload scenario/i,
        })
      ).toBeDisabled()
      expect(
        within(breakdownCard).getByRole('button', {
          name: /run ambulance breakdown scenario/i,
        })
      ).toBeDisabled()
      expect(
        within(trafficCard).getByRole('button', {
          name: /run traffic spike scenario/i,
        })
      ).toBeDisabled()
    })

    releaseCardiacRequest?.()

    expect(await screen.findByText('Incident created')).toBeInTheDocument()
  })
})

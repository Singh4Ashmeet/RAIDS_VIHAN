import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MockWebSocket } from './mocks/websocket'
import {
  MOCK_AMBULANCES, MOCK_HOSPITALS,
  MOCK_DISPATCH, MOCK_INCIDENTS
} from './mocks/handlers'

describe('DispatchDecisionCard', () => {
  it('shows placeholder text when dispatch is null', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={null}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/awaiting|waiting|no dispatch/i)).toBeInTheDocument()
  })

  it('shows ambulance ID when dispatch is provided', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/AMB-001/i)).toBeInTheDocument()
  })

  it('shows hospital name resolved from hospital_id', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/AIIMS Delhi/i)).toBeInTheDocument()
  })

  it('shows ETA minutes', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/6\.4|6 min/i)).toBeInTheDocument()
  })

  it('shows final score as percentage', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/81%/i)).toBeInTheDocument()
  })

  it('has a button to view explanation', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(
      screen.getByRole('button', { name: /explanation|explain/i })
    ).toBeInTheDocument()
  })

  it('has a button to view rejected options', async () => {
    const { default: DispatchDecisionCard } =
      await import('../admin/subcomponents/DispatchDecisionCard')
    render(
      <DispatchDecisionCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(
      screen.getByRole('button', { name: /rejected/i })
    ).toBeInTheDocument()
  })
})

describe('ExplainabilityPanel', () => {
  it('shows explanation_text from dispatch', async () => {
    const { default: ExplainabilityPanel } =
      await import('../admin/subcomponents/ExplainabilityPanel')
    render(
      <ExplainabilityPanel
        dispatch={MOCK_DISPATCH}
        hospitals={MOCK_HOSPITALS}
        expanded={true}
      />
    )
    expect(screen.getByText(/AMB-001/)).toBeInTheDocument()
    expect(screen.getByText(/HOSP-001/)).toBeInTheDocument()
  })

  it('shows 3 key factor bullets when expanded', async () => {
    const { default: ExplainabilityPanel } =
      await import('../admin/subcomponents/ExplainabilityPanel')
    render(
      <ExplainabilityPanel
        dispatch={MOCK_DISPATCH}
        hospitals={MOCK_HOSPITALS}
        expanded={true}
      />
    )
    const items = screen.getAllByRole('listitem')
    expect(items.length).toBeGreaterThanOrEqual(3)
  })

  it('hides detailed content when collapsed', async () => {
    const { default: ExplainabilityPanel } =
      await import('../admin/subcomponents/ExplainabilityPanel')
    render(
      <ExplainabilityPanel
        dispatch={MOCK_DISPATCH}
        hospitals={MOCK_HOSPITALS}
        expanded={false}
      />
    )
    const items = screen.queryAllByRole('listitem')
    expect(items.length).toBeLessThan(3)
  })

  it('shows rejected hospitals count in layer 3', async () => {
    const { default: ExplainabilityPanel } =
      await import('../admin/subcomponents/ExplainabilityPanel')
    render(
      <ExplainabilityPanel
        dispatch={MOCK_DISPATCH}
        hospitals={MOCK_HOSPITALS}
        expanded={true}
      />
    )
    expect(
      screen.getByText(/rejected.*alternative|alternative.*rejected/i)
    ).toBeInTheDocument()
  })

  it('renders null dispatch without crashing', async () => {
    const { default: ExplainabilityPanel } =
      await import('../admin/subcomponents/ExplainabilityPanel')
    expect(() =>
      render(
        <ExplainabilityPanel
          dispatch={null}
          hospitals={MOCK_HOSPITALS}
          expanded={true}
        />
      )
    ).not.toThrow()
  })
})

describe('ActiveIncidentsList', () => {
  it('fetches and shows incident list', async () => {
    const { default: ActiveIncidentsList } =
      await import('../admin/subcomponents/ActiveIncidentsList')
    render(<ActiveIncidentsList />)
    await waitFor(() => {
      expect(screen.getByText(/cardiac|trauma/i)).toBeInTheDocument()
    })
  })

  it('shows empty state when no incidents', async () => {
    const { http, HttpResponse } = await import('msw')
    const { server } = await import('./mocks/server')
    server.use(http.get('/api/incidents', () => HttpResponse.json([])))
    const { default: ActiveIncidentsList } =
      await import('../admin/subcomponents/ActiveIncidentsList')
    render(<ActiveIncidentsList />)
    await waitFor(() => {
      expect(
        screen.getByText(/no active|no incidents/i)
      ).toBeInTheDocument()
    })
  })

  it('displays incident count badge', async () => {
    const { default: ActiveIncidentsList } =
      await import('../admin/subcomponents/ActiveIncidentsList')
    render(<ActiveIncidentsList />)
    await waitFor(() => { expect(screen.getByText('2')).toBeInTheDocument() })
  })
})

describe('DispatchFeed', () => {
  it('renders dispatches tab with history items', async () => {
    const { default: DispatchFeed } =
      await import('../admin/subcomponents/DispatchFeed')
    render(
      <DispatchFeed dispatchHistory={[MOCK_DISPATCH]} notifications={[]} />
    )
    expect(screen.getByText(/AMB-001/i)).toBeInTheDocument()
    expect(screen.getByText(/HOSP-001/i)).toBeInTheDocument()
  })

  it('renders alerts tab with notifications', async () => {
    const { default: DispatchFeed } =
      await import('../admin/subcomponents/DispatchFeed')
    const notification = {
      type: 'hospital_notification',
      hospital_id: 'HOSP-001',
      patient_name: 'Arjun Sharma',
      severity: 'critical',
      eta_minutes: 6.4,
      ambulance_id: 'AMB-001',
      prep_checklist: ['Prepare cardiac ICU bed']
    }
    render(
      <DispatchFeed dispatchHistory={[]} notifications={[notification]} />
    )
    await userEvent.click(screen.getByText(/alerts/i))
    expect(screen.getByText(/Arjun Sharma/i)).toBeInTheDocument()
  })
})

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MOCK_AMBULANCES, MOCK_HOSPITALS, MOCK_DISPATCH } from './mocks/handlers'
 
describe('TrackingCard', () => {
  it('shows placeholder when no dispatch provided', async () => {
    const { default: TrackingCard } =
      await import('../user/subcomponents/TrackingCard')
    render(
      <TrackingCard
        dispatch={null}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(
      screen.getByText(/no active dispatch|submit.*sos/i)
    ).toBeInTheDocument()
  })
 
  it('shows ambulance ID when dispatch is set', async () => {
    const { default: TrackingCard } =
      await import('../user/subcomponents/TrackingCard')
    render(
      <TrackingCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/AMB-001/)).toBeInTheDocument()
  })
 
  it('shows hospital name resolved from hospital_id', async () => {
    const { default: TrackingCard } =
      await import('../user/subcomponents/TrackingCard')
    render(
      <TrackingCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/AIIMS Delhi/)).toBeInTheDocument()
  })
 
  it('shows ETA in minutes', async () => {
    const { default: TrackingCard } =
      await import('../user/subcomponents/TrackingCard')
    render(
      <TrackingCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/6\.4|6 min/i)).toBeInTheDocument()
  })
 
  it('shows severity badge', async () => {
    const { default: TrackingCard } =
      await import('../user/subcomponents/TrackingCard')
    render(
      <TrackingCard
        dispatch={MOCK_DISPATCH}
        ambulances={MOCK_AMBULANCES}
        hospitals={MOCK_HOSPITALS}
      />
    )
    expect(screen.getByText(/critical/i)).toBeInTheDocument()
  })
})

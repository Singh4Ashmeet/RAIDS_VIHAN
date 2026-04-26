import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MOCK_AMBULANCES, MOCK_HOSPITALS } from './mocks/handlers'

describe('AmbulanceTable', () => {
  it('renders all ambulances by default', async () => {
    const { default: AmbulanceTable } =
      await import('../admin/subcomponents/AmbulanceTable')
    render(<AmbulanceTable ambulances={MOCK_AMBULANCES} />)
    expect(screen.getByText('AMB-001')).toBeInTheDocument()
    expect(screen.getByText('AMB-002')).toBeInTheDocument()
    expect(screen.getByText('AMB-003')).toBeInTheDocument()
  })

  it('shows ALS and BLS type badges', async () => {
    const { default: AmbulanceTable } =
      await import('../admin/subcomponents/AmbulanceTable')
    render(<AmbulanceTable ambulances={MOCK_AMBULANCES} />)
    expect(screen.getAllByText(/ALS/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/BLS/i).length).toBeGreaterThan(0)
  })

  it('filters to show only available ambulances', async () => {
    const { default: AmbulanceTable } =
      await import('../admin/subcomponents/AmbulanceTable')
    render(<AmbulanceTable ambulances={MOCK_AMBULANCES} />)
    await userEvent.click(screen.getByRole('button', { name: /available/i }))
    expect(screen.getByText('AMB-001')).toBeInTheDocument()
    expect(screen.queryByText('AMB-002')).not.toBeInTheDocument()
    expect(screen.queryByText('AMB-003')).not.toBeInTheDocument()
  })

  it('filters to show only unavailable ambulances', async () => {
    const { default: AmbulanceTable } =
      await import('../admin/subcomponents/AmbulanceTable')
    render(<AmbulanceTable ambulances={MOCK_AMBULANCES} />)
    await userEvent.click(screen.getByRole('button', { name: /unavailable/i }))
    expect(screen.queryByText('AMB-001')).not.toBeInTheDocument()
    expect(screen.getByText('AMB-003')).toBeInTheDocument()
  })

  it('shows count badges for each filter', async () => {
    const { default: AmbulanceTable } =
      await import('../admin/subcomponents/AmbulanceTable')
    render(<AmbulanceTable ambulances={MOCK_AMBULANCES} />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows no emoji in table content', async () => {
    const { default: AmbulanceTable } =
      await import('../admin/subcomponents/AmbulanceTable')
    const { container } = render(<AmbulanceTable ambulances={MOCK_AMBULANCES} />)
    const emojiRegex = /[\u{1F300}-\u{1FFFF}]/u
    expect(emojiRegex.test(container.textContent)).toBe(false)
  })
})

describe('HospitalCapacityGrid', () => {
  it('renders all hospitals', async () => {
    const { default: HospitalCapacityGrid } =
      await import('../admin/subcomponents/HospitalCapacityGrid')
    render(<HospitalCapacityGrid hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText('AIIMS Delhi')).toBeInTheDocument()
    expect(screen.getByText('Safdarjung Hospital')).toBeInTheDocument()
    expect(screen.getByText('KEM Hospital Mumbai')).toBeInTheDocument()
  })

  it('shows DIVERTED badge for hospital with diversion_status true', async () => {
    const { default: HospitalCapacityGrid } =
      await import('../admin/subcomponents/HospitalCapacityGrid')
    render(<HospitalCapacityGrid hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText(/diverted/i)).toBeInTheDocument()
  })

  it('filters hospitals by city', async () => {
    const { default: HospitalCapacityGrid } =
      await import('../admin/subcomponents/HospitalCapacityGrid')
    render(<HospitalCapacityGrid hospitals={MOCK_HOSPITALS} />)
    await userEvent.click(screen.getByRole('button', { name: /mumbai/i }))
    expect(screen.getByText('KEM Hospital Mumbai')).toBeInTheDocument()
    expect(screen.queryByText('AIIMS Delhi')).not.toBeInTheDocument()
  })

  it('shows occupancy percentage for each hospital', async () => {
    const { default: HospitalCapacityGrid } =
      await import('../admin/subcomponents/HospitalCapacityGrid')
    render(<HospitalCapacityGrid hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText(/68/)).toBeInTheDocument()
    expect(screen.getByText(/92/)).toBeInTheDocument()
  })

  it('shows ER wait times', async () => {
    const { default: HospitalCapacityGrid } =
      await import('../admin/subcomponents/HospitalCapacityGrid')
    render(<HospitalCapacityGrid hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText(/24.*min|24 min/i)).toBeInTheDocument()
  })

  it('shows ICU bed counts', async () => {
    const { default: HospitalCapacityGrid } =
      await import('../admin/subcomponents/HospitalCapacityGrid')
    render(<HospitalCapacityGrid hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText(/12.*20|12\/20/i)).toBeInTheDocument()
  })
})

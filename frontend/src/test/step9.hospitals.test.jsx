import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MOCK_HOSPITALS } from './mocks/handlers'
 
describe('HospitalCard', () => {
  it('renders hospital name and city', async () => {
    const { default: HospitalCard } =
      await import('../user/subcomponents/HospitalCard')
    render(<HospitalCard hospital={MOCK_HOSPITALS[0]} />)
    expect(screen.getByText('AIIMS Delhi')).toBeInTheDocument()
    expect(screen.getByText(/delhi/i)).toBeInTheDocument()
  })
 
  it('shows occupancy percentage', async () => {
    const { default: HospitalCard } =
      await import('../user/subcomponents/HospitalCard')
    render(<HospitalCard hospital={MOCK_HOSPITALS[0]} />)
    expect(screen.getByText(/68/)).toBeInTheDocument()
  })
 
  it('shows DIVERSION IN EFFECT for diverted hospital', async () => {
    const { default: HospitalCard } =
      await import('../user/subcomponents/HospitalCard')
    render(<HospitalCard hospital={MOCK_HOSPITALS[1]} />)
    expect(screen.getByText(/diversion in effect/i)).toBeInTheDocument()
  })
 
  it('shows Accepting patients for non-diverted hospital', async () => {
    const { default: HospitalCard } =
      await import('../user/subcomponents/HospitalCard')
    render(<HospitalCard hospital={MOCK_HOSPITALS[0]} />)
    expect(screen.getByText(/accepting patients/i)).toBeInTheDocument()
  })
 
  it('shows ER wait time', async () => {
    const { default: HospitalCard } =
      await import('../user/subcomponents/HospitalCard')
    render(<HospitalCard hospital={MOCK_HOSPITALS[0]} />)
    expect(screen.getByText(/24.*min/i)).toBeInTheDocument()
  })
 
  it('shows ICU bed ratio', async () => {
    const { default: HospitalCard } =
      await import('../user/subcomponents/HospitalCard')
    render(<HospitalCard hospital={MOCK_HOSPITALS[0]} />)
    expect(screen.getByText(/12.*20/i)).toBeInTheDocument()
  })
})
 
describe('HospitalFinder', () => {
  it('renders all hospitals from props', async () => {
    const { default: HospitalFinder } = await import('../user/HospitalFinder')
    render(<HospitalFinder hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText('AIIMS Delhi')).toBeInTheDocument()
    expect(screen.getByText('KEM Hospital Mumbai')).toBeInTheDocument()
  })
 
  it('filters hospitals by city', async () => {
    const { default: HospitalFinder } = await import('../user/HospitalFinder')
    render(<HospitalFinder hospitals={MOCK_HOSPITALS} />)
    await userEvent.click(screen.getByRole('button', { name: /mumbai/i }))
    expect(screen.getByText('KEM Hospital Mumbai')).toBeInTheDocument()
    expect(screen.queryByText('AIIMS Delhi')).not.toBeInTheDocument()
  })
 
  it('filters to show only diverted hospitals', async () => {
    const { default: HospitalFinder } = await import('../user/HospitalFinder')
    render(<HospitalFinder hospitals={MOCK_HOSPITALS} />)
    await userEvent.click(screen.getByRole('button', { name: /diverted/i }))
    expect(screen.getByText('Safdarjung Hospital')).toBeInTheDocument()
    expect(screen.queryByText('AIIMS Delhi')).not.toBeInTheDocument()
  })
 
  it('shows system summary bar with count and avg occupancy', async () => {
    const { default: HospitalFinder } = await import('../user/HospitalFinder')
    render(<HospitalFinder hospitals={MOCK_HOSPITALS} />)
    expect(screen.getByText(/2.*accepting|accepting.*2/i)).toBeInTheDocument()
    expect(screen.getByText(/1.*diverted|diverted.*1/i)).toBeInTheDocument()
  })
})

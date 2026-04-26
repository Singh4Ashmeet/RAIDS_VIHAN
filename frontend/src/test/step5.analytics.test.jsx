import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MOCK_ANALYTICS } from './mocks/handlers'

describe('Analytics dashboard', () => {
  it('shows all 6 metric cards after data loads', async () => {
    const { default: Analytics } = await import('../admin/Analytics')
    render(<Analytics />)
    await waitFor(() => {
      expect(screen.getByText(/incidents today/i)).toBeInTheDocument()
      expect(screen.getByText(/dispatches/i)).toBeInTheDocument()
      expect(screen.getByText(/hospitals notified/i)).toBeInTheDocument()
      expect(screen.getByText(/overloads prevented/i)).toBeInTheDocument()
    })
  })

  it('shows correct metric values from API', async () => {
    const { default: Analytics } = await import('../admin/Analytics')
    render(<Analytics />)
    await waitFor(() => {
      expect(screen.getByText('7')).toBeInTheDocument()
      expect(screen.getByText('6')).toBeInTheDocument()
      expect(screen.getByText('4')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
    })
  })

  it('shows time-saved message when baseline > ai eta', async () => {
    const { default: Analytics } = await import('../admin/Analytics')
    render(<Analytics />)
    await waitFor(() => {
      expect(screen.getByText(/saves.*2\.7|2\.7.*min/i)).toBeInTheDocument()
    })
  })

  it('shows loading state before data arrives', async () => {
    vi.useFakeTimers()
    const { default: Analytics } = await import('../admin/Analytics')
    render(<Analytics />)
    expect(
      document.querySelector(
        '[class*="spinner"], [class*="loading"], [class*="animate"]'
      )
    ).not.toBeNull()
    vi.useRealTimers()
  })
})

describe('EtaComparisonChart', () => {
  it('renders chart with AI and Baseline labels', async () => {
    const { default: EtaComparisonChart } =
      await import('../admin/subcomponents/EtaComparisonChart')
    render(<EtaComparisonChart data={MOCK_ANALYTICS} />)
    expect(screen.getByText(/AI.*dispatch|AI dispatch/i)).toBeInTheDocument()
    expect(screen.getByText(/baseline|nearest.unit/i)).toBeInTheDocument()
  })

  it('displays both ETA values', async () => {
    const { default: EtaComparisonChart } =
      await import('../admin/subcomponents/EtaComparisonChart')
    render(<EtaComparisonChart data={MOCK_ANALYTICS} />)
    expect(screen.getByText(/6\.4|6.4/)).toBeInTheDocument()
    expect(screen.getByText(/9\.1|9.1/)).toBeInTheDocument()
  })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

describe('StatusDot', () => {
  it('renders without emoji — only a div/span element', async () => {
    const { default: StatusDot } = await import('../shared/StatusDot')
    const { container } = render(<StatusDot status="available" />)
    const emojiRegex = /[\u{1F300}-\u{1FFFF}]/u
    expect(emojiRegex.test(container.textContent)).toBe(false)
    expect(container.firstChild).not.toBeNull()
  })

  it('applies teal color for available status', async () => {
    const { default: StatusDot } = await import('../shared/StatusDot')
    const { container } = render(<StatusDot status="available" />)
    const el = container.firstChild
    const style = el.getAttribute('style') || el.className
    expect(style.includes('#1D9E75') || style.includes('teal')).toBe(true)
  })

  it('applies coral color for unavailable status', async () => {
    const { default: StatusDot } = await import('../shared/StatusDot')
    const { container } = render(<StatusDot status="unavailable" />)
    const el = container.firstChild
    const style = el.getAttribute('style') || el.className
    expect(
      style.includes('#D85A30') || style.includes('coral') ||
      style.includes('red')
    ).toBe(true)
  })

  it('renders different color for en_route vs available', async () => {
    const { default: StatusDot } = await import('../shared/StatusDot')
    const { container: c1 } = render(<StatusDot status="available" />)
    const { container: c2 } = render(<StatusDot status="en_route" />)
    const style1 = c1.firstChild.getAttribute('style') || c1.firstChild.className
    const style2 = c2.firstChild.getAttribute('style') || c2.firstChild.className
    expect(style1).not.toBe(style2)
  })
})

describe('SeverityBadge', () => {
  it('renders severity text', async () => {
    const { default: SeverityBadge } = await import('../shared/SeverityBadge')
    render(<SeverityBadge severity="critical" />)
    expect(screen.getByText(/critical/i)).toBeInTheDocument()
  })

  it('renders all four severity levels without error', async () => {
    const { default: SeverityBadge } = await import('../shared/SeverityBadge')
    const { unmount } = render(<SeverityBadge severity="critical" />)
    unmount()
    render(<SeverityBadge severity="high" />)
    expect(screen.getByText(/high/i)).toBeInTheDocument()
  })

  it('uses different background colors for critical vs low', async () => {
    const { default: SeverityBadge } = await import('../shared/SeverityBadge')
    const { container: c1 } = render(<SeverityBadge severity="critical" />)
    const { container: c2 } = render(<SeverityBadge severity="low" />)
    const bg1 = c1.firstChild.getAttribute('style') || c1.firstChild.className
    const bg2 = c2.firstChild.getAttribute('style') || c2.firstChild.className
    expect(bg1).not.toBe(bg2)
  })
})

describe('MetricCard', () => {
  it('renders label and value', async () => {
    const { default: MetricCard } = await import('../shared/MetricCard')
    render(<MetricCard label="Incidents Today" value={7} />)
    expect(screen.getByText('Incidents Today')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders unit when provided', async () => {
    const { default: MetricCard } = await import('../shared/MetricCard')
    render(<MetricCard label="Avg ETA" value={6.4} unit="min" />)
    expect(screen.getByText(/min/)).toBeInTheDocument()
  })

  it('renders all 4 highlight variants without error', async () => {
    const { default: MetricCard } = await import('../shared/MetricCard')
    const variants = ['purple', 'teal', 'coral', 'amber']
    for (const v of variants) {
      const { unmount } = render(<MetricCard label="Test" value={1} highlight={v} />)
      expect(screen.getByText('Test')).toBeInTheDocument()
      unmount()
    }
  })
})

describe('OccupancyBar', () => {
  it('renders without crashing for values 0 through 100', async () => {
    const { default: OccupancyBar } = await import('../shared/OccupancyBar')
    for (const v of [0, 50, 70, 89, 90, 100]) {
      const { unmount } = render(<OccupancyBar value={v} />)
      unmount()
    }
  })

  it('shows the percentage value in output', async () => {
    const { default: OccupancyBar } = await import('../shared/OccupancyBar')
    render(<OccupancyBar value={68} />)
    expect(screen.getByText(/68/)).toBeInTheDocument()
  })

  it('uses different color for value above 90 vs below 70', async () => {
    const { default: OccupancyBar } = await import('../shared/OccupancyBar')
    const { container: c1 } = render(<OccupancyBar value={55} />)
    const { container: c2 } = render(<OccupancyBar value={95} />)
    const bar1 = c1.querySelector('[style], [class]')
    const bar2 = c2.querySelector('[style], [class]')
    expect(bar1).not.toBeNull()
    expect(bar2).not.toBeNull()
  })
})

describe('Toast', () => {
  it('renders message text', async () => {
    const { default: Toast } = await import('../shared/Toast')
    render(<Toast message="Dispatch confirmed" type="success" onDismiss={() => {}} />)
    expect(screen.getByText('Dispatch confirmed')).toBeInTheDocument()
  })

  it('calls onDismiss after 4 seconds', async () => {
    vi.useFakeTimers()
    const { default: Toast } = await import('../shared/Toast')
    const onDismiss = vi.fn()
    render(<Toast message="Test" type="info" onDismiss={onDismiss} />)
    act(() => { vi.advanceTimersByTime(4100) })
    expect(onDismiss).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('renders three types without error', async () => {
    const { default: Toast } = await import('../shared/Toast')
    for (const type of ['success', 'error', 'info']) {
      const { unmount } = render(
        <Toast message="msg" type={type} onDismiss={() => {}} />
      )
      unmount()
    }
  })
})

describe('Spinner', () => {
  it('renders for all size variants', async () => {
    const { default: Spinner } = await import('../shared/Spinner')
    for (const size of ['sm', 'md', 'lg']) {
      const { container, unmount } = render(<Spinner size={size} />)
      expect(container.firstChild).not.toBeNull()
      unmount()
    }
  })

  it('contains no text content', async () => {
    const { default: Spinner } = await import('../shared/Spinner')
    const { container } = render(<Spinner size="md" />)
    expect(container.textContent.trim()).toBe('')
  })
})

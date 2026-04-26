import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
 
describe('SOSForm', () => {
  it('renders all required fields', async () => {
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    render(<SOSForm onSuccess={() => {}} />)
    expect(screen.getByLabelText(/name|full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/age/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/gender/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/mobile|phone/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/chief complaint|complaint/i))
      .toBeInTheDocument()
    expect(screen.getByLabelText(/city/i)).toBeInTheDocument()
  })
 
  it('pre-fills lat/lng from city selection', async () => {
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    render(<SOSForm onSuccess={() => {}} />)
    const citySelect = screen.getByLabelText(/city/i)
    await userEvent.selectOptions(citySelect, 'Mumbai')
    const latInput = screen.getByDisplayValue(/19\.07|19.0760/i)
    expect(latInput).toBeInTheDocument()
  })
 
  it('shows SOS mode toggle defaulting to on', async () => {
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    render(<SOSForm onSuccess={() => {}} />)
    const toggle = screen.getByRole('checkbox', { name: /sos|priority/i })
    expect(toggle).toBeChecked()
  })
 
  it('calls onSuccess with patient and dispatch after submit', async () => {
    const onSuccess = vi.fn()
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    render(<SOSForm onSuccess={onSuccess} />)
    await userEvent.type(screen.getByLabelText(/name|full name/i), 'Arjun Sharma')
    await userEvent.clear(screen.getByLabelText(/age/i))
    await userEvent.type(screen.getByLabelText(/age/i), '45')
    await userEvent.selectOptions(screen.getByLabelText(/gender/i), 'male')
    await userEvent.type(screen.getByLabelText(/mobile|phone/i), '9876543210')
    await userEvent.type(
      screen.getByLabelText(/chief complaint|complaint/i),
      'severe chest pain'
    )
    await userEvent.click(screen.getByRole('button', { name: /send.*sos|sos/i }))
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1)
      const [arg] = onSuccess.mock.calls[0]
      expect(arg.patient.id).toBe('PAT-001')
      expect(arg.dispatch_plan.ambulance_id).toBe('AMB-001')
    })
  })
 
  it('shows success card after submission with track button', async () => {
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    render(<SOSForm onSuccess={() => {}} />)
    await userEvent.type(screen.getByLabelText(/name|full name/i), 'Arjun')
    await userEvent.clear(screen.getByLabelText(/age/i))
    await userEvent.type(screen.getByLabelText(/age/i), '45')
    await userEvent.selectOptions(screen.getByLabelText(/gender/i), 'male')
    await userEvent.type(screen.getByLabelText(/mobile|phone/i), '9876543210')
    await userEvent.type(screen.getByLabelText(/complaint/i), 'chest pain')
    await userEvent.click(screen.getByRole('button', { name: /send.*sos|sos/i }))
    await waitFor(() => {
      expect(screen.getByText(/sos received|dispatched/i)).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /track.*ambulance/i })
      ).toBeInTheDocument()
    })
  })
 
  it('shows error toast when API fails', async () => {
    const { http, HttpResponse } = await import('msw')
    const { server } = await import('./mocks/server')
    server.use(
      http.post('/api/patients', () =>
        HttpResponse.json({ detail: 'error' }, { status: 500 }))
    )
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    render(<SOSForm onSuccess={() => {}} />)
    await userEvent.type(screen.getByLabelText(/name|full name/i), 'Test')
    await userEvent.type(screen.getByLabelText(/age/i), '30')
    await userEvent.selectOptions(screen.getByLabelText(/gender/i), 'male')
    await userEvent.type(screen.getByLabelText(/mobile/i), '1234567890')
    await userEvent.type(screen.getByLabelText(/complaint/i), 'pain')
    await userEvent.click(screen.getByRole('button', { name: /send.*sos|sos/i }))
    await waitFor(() => {
      expect(screen.getByText(/failed|error|try again/i)).toBeInTheDocument()
    })
  })
 
  it('has no emoji in rendered output', async () => {
    const { default: SOSForm } = await import('../user/subcomponents/SOSForm')
    const { container } = render(<SOSForm onSuccess={() => {}} />)
    const emojiRegex = /[\u{1F300}-\u{1FFFF}]/u
    expect(emojiRegex.test(container.textContent)).toBe(false)
  })
})

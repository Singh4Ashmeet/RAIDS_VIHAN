import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import CommandCenter from '../pages/admin/CommandCenter'
import FleetHospitals from '../pages/admin/FleetHospitals'
import Analytics from '../pages/admin/Analytics'
import SOSPortal from '../pages/user/SOSPortal'
import DispatchStatus from '../pages/user/DispatchStatus'
import HospitalFinder from '../pages/user/HospitalFinder'
import useDispatchStore from '../store/dispatchStore'
import {
  MOCK_AMBULANCES,
  MOCK_DISPATCH,
  MOCK_HOSPITALS,
  MOCK_INCIDENTS,
} from './mocks/handlers'

function resetDispatchStore(overrides = {}) {
  useDispatchStore.setState({
    incidents: MOCK_INCIDENTS,
    ambulances: MOCK_AMBULANCES,
    hospitals: MOCK_HOSPITALS,
    lastDispatch: null,
    dispatchHistory: [],
    notifications: [],
    anomalyAlerts: [],
    wsStatus: 'connected',
    systemStatus: 'normal',
    trafficMultiplier: 1,
    _ws: null,
    ...overrides,
  })
}

function renderPage(element) {
  return render(<MemoryRouter>{element}</MemoryRouter>)
}

describe('modern routed pages', () => {
  beforeEach(() => {
    resetDispatchStore()
  })

  it('CommandCenter shows incident and dispatch decision surfaces', async () => {
    renderPage(<CommandCenter />)

    expect(await screen.findByText(/active incidents/i)).toBeInTheDocument()
    expect(screen.getByText(/cardiac/i)).toBeInTheDocument()
    expect(screen.getByText(/review recommended/i)).toBeInTheDocument()
  })

  it('FleetHospitals separates fleet and hospital views', async () => {
    const user = userEvent.setup()
    renderPage(<FleetHospitals />)

    expect(screen.getByText('AMB-001')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^Hospitals$/i }))
    expect(screen.getByText('AIIMS Delhi')).toBeInTheDocument()
  })

  it('Analytics shows benchmark and literature context', async () => {
    renderPage(<Analytics />)

    expect(await screen.findByText(/incidents today/i)).toBeInTheDocument()
    expect(screen.getByText(/published literature comparison/i)).toBeInTheDocument()
    expect(screen.getByText(/simulation vs real-world/i)).toBeInTheDocument()
  })

  it('SOSPortal submits the modern patient intake form', async () => {
    const user = userEvent.setup()
    renderPage(<SOSPortal />)

    await user.type(screen.getByLabelText(/full name/i), 'Test User')
    await user.type(screen.getByLabelText(/age/i), '35')
    await user.type(screen.getByLabelText(/mobile/i), '9999999999')
    await user.type(screen.getByLabelText(/emergency report/i), 'severe chest pain')
    await user.click(screen.getByRole('button', { name: /request emergency dispatch/i }))

    await waitFor(() => {
      expect(screen.getByText(/sos received|confirmed|fallback/i)).toBeInTheDocument()
    })
  })

  it('DispatchStatus and HospitalFinder read from the shared store', async () => {
    resetDispatchStore({ lastDispatch: MOCK_DISPATCH })

    const { rerender } = renderPage(<DispatchStatus />)
    expect(screen.getByText(/dispatch confirmed/i)).toBeInTheDocument()
    expect(screen.getAllByText(/AMB-001/).length).toBeGreaterThan(0)

    rerender(<MemoryRouter><HospitalFinder /></MemoryRouter>)
    expect(screen.getByText('AIIMS Delhi')).toBeInTheDocument()
    expect(screen.getAllByText(/accepting/i).length).toBeGreaterThan(0)
  })
})

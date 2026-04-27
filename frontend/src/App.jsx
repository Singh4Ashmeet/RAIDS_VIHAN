import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'

import useAuthStore from './store/authStore'
import useDispatchStore from './store/dispatchStore'
import { RequireAuth } from './components/ProtectedRoute'

import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import AdminLayout from './layouts/AdminLayout'
import UserLayout from './layouts/UserLayout'
import CommandCenter from './pages/admin/CommandCenter'
import FleetHospitals from './pages/admin/FleetHospitals'
import Analytics from './pages/admin/Analytics'
import ScenarioLab from './pages/admin/ScenarioLab'
import DemandHeatmap from './pages/admin/DemandHeatmap'
import SOSPortal from './pages/user/SOSPortal'
import DispatchStatus from './pages/user/DispatchStatus'
import HospitalFinder from './pages/user/HospitalFinder'

export default function App() {
  const hydrate = useAuthStore((s) => s.hydrate)
  const token = useAuthStore((s) => s.token)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const hasHydrated = useAuthStore((s) => s.hasHydrated)
  const connectWS = useDispatchStore((s) => s.connectWS)
  const disconnectWS = useDispatchStore((s) => s.disconnectWS)
  const fetchAll = useDispatchStore((s) => s.fetchAll)

  useEffect(() => {
    hydrate()
  }, [hydrate])

  useEffect(() => {
    if (!hasHydrated) return undefined

    if (!isAuthenticated || !token) {
      disconnectWS()
      return undefined
    }

    connectWS()
    fetchAll()
    return undefined
  }, [hasHydrated, isAuthenticated, token, connectWS, disconnectWS, fetchAll])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage/>}/>
        <Route path="/landing" element={<Navigate to="/" replace/>}/>
        <Route path="/login" element={<LoginPage/>}/>

        <Route path="/admin" element={
          <RequireAuth role="admin"><AdminLayout/></RequireAuth>
        }>
          <Route index element={<Navigate to="command" replace/>}/>
          <Route path="command" element={<CommandCenter/>}/>
          <Route path="fleet" element={<FleetHospitals/>}/>
          <Route path="analytics" element={<Analytics/>}/>
          <Route path="scenario" element={<ScenarioLab/>}/>
          <Route path="scenarios" element={<Navigate to="scenario" replace/>}/>
          <Route path="heatmap" element={<DemandHeatmap/>}/>
        </Route>

        <Route path="/user" element={
          <RequireAuth><UserLayout/></RequireAuth>
        }>
          <Route index element={<Navigate to="sos" replace/>}/>
          <Route path="sos" element={<SOSPortal/>}/>
          <Route path="status" element={<DispatchStatus/>}/>
          <Route path="hospitals" element={<HospitalFinder/>}/>
        </Route>

        <Route path="*" element={<Navigate to="/" replace/>}/>
      </Routes>
    </BrowserRouter>
  )
}

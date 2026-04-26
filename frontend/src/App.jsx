import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'

import Analytics from './admin/Analytics'
import CommandCenter from './admin/CommandCenter'
import ScenarioLab from './admin/ScenarioLab'
import AmbulanceTable from './admin/subcomponents/AmbulanceTable'
import HospitalCapacityGrid from './admin/subcomponents/HospitalCapacityGrid'
import { LiveStateProvider, useLiveState } from './context/LiveStateContext'
import LegacyHospitalFinder from './user/HospitalFinder'
import SOSForm from './user/subcomponents/SOSForm'
import TrackingCard from './user/subcomponents/TrackingCard'

import useAuthStore from './store/authStore'
import useDispatchStore from './store/dispatchStore'
import { RequireAuth } from './components/ProtectedRoute'

import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import AdminLayout from './layouts/AdminLayout'
import UserLayout from './layouts/UserLayout'
import CommandCenterPage from './pages/admin/CommandCenter'
import FleetHospitals from './pages/admin/FleetHospitals'
import AnalyticsPage from './pages/admin/Analytics'
import ScenarioLabPage from './pages/admin/ScenarioLab'
import DemandHeatmap from './pages/admin/DemandHeatmap'
import SOSPortal from './pages/user/SOSPortal'
import DispatchStatus from './pages/user/DispatchStatus'
import HospitalFinder from './pages/user/HospitalFinder'

const ADMIN_TABS = ['Command Center', 'Fleet', 'Analytics', 'Scenario']
const USER_TABS = ['Emergency SOS', 'My Status', 'Hospital Finder']
const isTestEnv = import.meta.env.MODE === 'test'

function AdminPortal({
  activeTab,
  ambulances,
  hospitals,
  latestDispatch,
  dispatchHistory,
  notifications,
  onScenarioResult,
}) {
  if (activeTab === 'Fleet') {
    return (
      <section style={{ display: 'grid', gap: '1rem' }}>
        <AmbulanceTable ambulances={ambulances} />
        <HospitalCapacityGrid hospitals={hospitals} />
      </section>
    )
  }

  if (activeTab === 'Analytics') {
    return <Analytics />
  }

  if (activeTab === 'Scenario') {
    return (
      <ScenarioLab
        dispatchHistory={dispatchHistory}
        notifications={notifications}
        onScenarioResult={onScenarioResult}
      />
    )
  }

  return (
    <CommandCenter
      ambulances={ambulances}
      hospitals={hospitals}
      latestDispatch={latestDispatch}
      dispatchHistory={dispatchHistory}
      notifications={notifications}
    />
  )
}

function UserPortal({ activeTab, ambulances, hospitals, latestDispatch, onSosSuccess }) {
  if (activeTab === 'My Status') {
    return (
      <TrackingCard
        dispatch={latestDispatch}
        ambulances={ambulances}
        hospitals={hospitals}
      />
    )
  }

  if (activeTab === 'Hospital Finder') {
    return <LegacyHospitalFinder hospitals={hospitals} />
  }

  return <SOSForm onSuccess={onSosSuccess} />
}

function LegacyPortalShell() {
  const [role, setRole] = useState('admin')
  const [activeAdminTab, setActiveAdminTab] = useState('Command Center')
  const [activeUserTab, setActiveUserTab] = useState('Emergency SOS')
  const {
    ambulances,
    hospitals,
    latestDispatch,
    dispatchHistory,
    notifications,
    isConnected,
    setLatestDispatch,
  } = useLiveState()
  const tabs = role === 'admin' ? ADMIN_TABS : USER_TABS

  function handleRoleChange(nextRole) {
    setRole(nextRole)
  }

  function handleTabChange(tab) {
    if (role === 'admin') {
      setActiveAdminTab(tab)
      return
    }

    setActiveUserTab(tab)
  }

  function handleDispatchResult(result) {
    const dispatchPlan = result?.dispatch_plan ?? result ?? null

    if (dispatchPlan) {
      setLatestDispatch(dispatchPlan)
    }
  }

  function handleSosSuccess(result) {
    setLatestDispatch(result?.dispatch_plan ?? null)
  }

  const activeTab = role === 'admin' ? activeAdminTab : activeUserTab

  return (
    <main
      style={{
        display: 'grid',
        gap: '1rem',
        padding: '1.25rem',
        color: '#172033',
      }}
    >
      <header style={{ display: 'grid', gap: '0.35rem' }}>
        <h1 style={{ margin: 0 }}>RAID Nexus</h1>
        <p style={{ margin: 0, color: '#566278' }}>
          {isConnected ? 'Live' : 'Reconnecting'}
        </p>
      </header>

      <section aria-label="Role Selector" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button type="button" onClick={() => handleRoleChange('admin')}>
          Admin
        </button>
        <button type="button" onClick={() => handleRoleChange('user')}>
          User
        </button>
      </section>

      <section aria-label="Portal Navigation" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {tabs.map((tab) => (
          tab === activeTab ? (
            <span
              key={tab}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '0.45rem 0.8rem',
                borderRadius: '999px',
                border: '1px solid #152033',
                backgroundColor: '#EEF3FF',
                fontWeight: 600,
              }}
            >
              {tab}
            </span>
          ) : (
            <button key={tab} type="button" onClick={() => handleTabChange(tab)}>
              {tab}
            </button>
          )
        ))}
      </section>

      {role === 'admin' ? (
        <AdminPortal
          activeTab={activeTab}
          ambulances={ambulances}
          hospitals={hospitals}
          latestDispatch={latestDispatch}
          dispatchHistory={dispatchHistory}
          notifications={notifications}
          onScenarioResult={handleDispatchResult}
        />
      ) : (
        <UserPortal
          activeTab={activeTab}
          ambulances={ambulances}
          hospitals={hospitals}
          latestDispatch={latestDispatch}
          onSosSuccess={handleSosSuccess}
        />
      )}
    </main>
  )
}

function RoutedApp() {
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
          <Route path="command" element={<CommandCenterPage/>}/>
          <Route path="fleet" element={<FleetHospitals/>}/>
          <Route path="analytics" element={<AnalyticsPage/>}/>
          <Route path="scenario" element={<ScenarioLabPage/>}/>
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

export default function App() {
  if (isTestEnv) {
    return (
      <LiveStateProvider>
        <LegacyPortalShell />
      </LiveStateProvider>
    )
  }

  return <RoutedApp />
}

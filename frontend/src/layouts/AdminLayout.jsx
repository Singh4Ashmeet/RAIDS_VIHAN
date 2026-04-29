import { useState } from 'react'
import { Outlet, NavLink, useNavigate, useLocation }
  from 'react-router-dom'
import { clsx } from 'clsx'
import {
  Activity, Truck, BarChart2, FlaskConical,
  ChevronLeft, ChevronRight, LogOut, Bell, Menu, Radar, UserRound,
} from 'lucide-react'
import useAuthStore     from '../store/authStore'
import useDispatchStore from '../store/dispatchStore'
import StatusDot        from '../components/ui/StatusDot'

const NAV = [
  { to: '/admin/command',   label: 'Command Center',   Icon: Activity },
  { to: '/admin/fleet',     label: 'Fleet & Hospitals', Icon: Truck },
  { to: '/admin/analytics', label: 'Analytics',        Icon: BarChart2 },
  { to: '/admin/scenario',  label: 'Scenario Lab',     Icon: FlaskConical },
  { to: '/admin/heatmap',   label: 'Demand Heatmap',   Icon: Radar },
]

const PAGE_TITLES = {
  '/admin/command':   'Command Center',
  '/admin/fleet':     'Fleet & Hospitals',
  '/admin/analytics': 'Analytics',
  '/admin/scenario':  'Scenario Lab',
  '/admin/scenarios': 'Scenario Lab',
  '/admin/heatmap':   'Demand Heatmap',
}

const STATUS_CONFIG = {
  normal:   { label: 'All Systems Go',  cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
  fallback: { label: 'Fallback Mode',   cls: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
  overload: { label: 'System Overload', cls: 'bg-red-500/20 text-red-400 border-red-500/30' },
}

export default function AdminLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const wsStatus = useDispatchStore((s) => s.wsStatus)
  const systemStatus = useDispatchStore((s) => s.systemStatus)
  const trafficMultiplier = useDispatchStore((s) => s.trafficMultiplier)

  const toggleCollapse = () => setCollapsed((c) => !c)
  const handleLogout = () => {
    logout()
    navigate('/login')
  }
  const pageTitle = PAGE_TITLES[location.pathname] || 'RAID Nexus'
  const sc = STATUS_CONFIG[systemStatus] || STATUS_CONFIG.normal
  const trafficPillClass = trafficMultiplier > 1.5
    ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
    : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
  const displayName = user?.full_name || user?.username || 'Admin'

  return (
    <div className="flex h-screen flex-col bg-surface text-slate-100">
      {systemStatus === 'overload' && (
        <div className="sticky top-0 z-30 border-b border-red-500/30 bg-red-900/50 px-6 py-2 text-center text-xs font-medium text-red-400">
          System Overload {'\u2014'} Incidents are being queued automatically
        </div>
      )}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {mobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}

        <aside
          className={clsx(
            'flex flex-col bg-card/95 border-r border-border z-50 shadow-2xl shadow-black/25',
            'transition-all duration-200 flex-shrink-0',
            mobileOpen ? 'fixed inset-y-0 left-0 flex w-[240px]' : 'hidden',
            'lg:flex lg:relative',
            collapsed ? 'lg:w-16' : 'lg:w-[240px]',
          )}
        >
          <div className="flex h-16 items-center justify-between border-b border-border p-4">
            {(!collapsed || mobileOpen) && (
              <div className="flex items-center gap-2">
                <span className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-blue-500/30 bg-blue-500/10 text-blue-300">
                  <Activity size={18}/>
                </span>
                <div>
                  <span className="block text-base font-bold text-white">RAID Nexus</span>
                  <span className="block text-[11px] text-slate-500">AI Dispatch Grid</span>
                </div>
              </div>
            )}
            <button
              onClick={toggleCollapse}
              className="hidden lg:flex rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              {collapsed
                ? <ChevronRight size={16}/>
                : <ChevronLeft size={16}/>}
            </button>
          </div>

          <nav className="mt-2 flex-1 space-y-1 p-2">
            {NAV.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 rounded-xl px-3 py-2.5',
                    'text-sm font-medium transition-colors',
                    'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
                    isActive
                      ? 'bg-blue-500/15 text-blue-300 ring-1 ring-blue-500/25'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  )
                }
              >
                <Icon size={18} className="flex-shrink-0"/>
                {(!collapsed || mobileOpen) && <span>{label}</span>}
              </NavLink>
            ))}
          </nav>

          <div className="space-y-2 border-t border-border p-3">
            <button
              onClick={() => navigate('/user/sos')}
              className={clsx(
                'flex w-full items-center gap-2 rounded-xl px-3 py-2',
                'text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
              )}
            >
              <UserRound size={16}/>
              {(!collapsed || mobileOpen) && <span>User Portal</span>}
            </button>
            {(!collapsed || mobileOpen) && user && (
              <div className="flex items-center gap-3 px-2 py-1">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
                  {displayName[0]?.toUpperCase() || 'A'}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-200">{displayName}</p>
                  <p className="text-xs text-slate-500">Admin</p>
                </div>
              </div>
            )}
            <button
              onClick={handleLogout}
              className={clsx(
                'flex w-full items-center gap-2 rounded-xl px-3 py-2',
                'text-sm text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-400',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
              )}
            >
              <LogOut size={16}/>
              {(!collapsed || mobileOpen) && <span>Logout</span>}
            </button>
          </div>
        </aside>

        <div className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-border bg-card/90 px-3 shadow-lg shadow-black/10 sm:px-6">
            <div className="flex items-center">
              <button
                className="mr-3 rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-700 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 lg:hidden"
                onClick={() => setMobileOpen(true)}
              >
                <Menu size={20}/>
              </button>
              <h1 className="text-[22px] font-semibold text-white lg:text-[28px]">
                {pageTitle}
              </h1>
            </div>
            <div className="flex items-center gap-2 sm:gap-4 min-w-0">
              <span className={clsx(
                'hidden sm:inline text-xs font-medium px-2.5 py-1 rounded-full border',
                sc.cls
              )}>
                {sc.label}
              </span>
              <span
                className={clsx(
                  'hidden sm:inline text-xs font-medium px-2.5 py-1 rounded-full border',
                  trafficPillClass
                )}
              >
                Traffic: {Number(trafficMultiplier || 1).toFixed(1)}x
              </span>
              <div className="flex items-center gap-1.5">
                <StatusDot status={
                  wsStatus === 'connected' ? 'available' : 'unavailable'
                }/>
                <span className="text-xs text-slate-400">
                  {wsStatus === 'connected' ? 'Live' : 'Reconnecting'}
                </span>
              </div>
              <button
                className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <Bell size={18}/>
              </button>
            </div>
          </header>

          <main className="flex-1 overflow-y-auto p-3 sm:p-6">
            <Outlet/>
          </main>
        </div>
      </div>
    </div>
  )
}

import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { Phone, MapPin, Hospital, LogOut, Shield } from 'lucide-react'
import useAuthStore from '../store/authStore'

const NAV = [
  { to: '/user/sos',       label: 'Emergency SOS',  Icon: Phone    },
  { to: '/user/status',    label: 'My Status',      Icon: MapPin   },
  { to: '/user/hospitals', label: 'Hospital Finder',Icon: Hospital },
]

export default function UserLayout() {
  const navigate = useNavigate()
  const logout   = useAuthStore(s => s.logout)

  return (
    <div className="min-h-screen bg-surface text-slate-100 flex flex-col">

      <header className="bg-card/95 border-b border-border
        sticky top-0 z-40">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-2 px-3 sm:px-4">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 text-red-300">
              <Shield size={18}/>
            </span>
            <span className="text-white font-bold text-sm">
              RAID Nexus
            </span>
          </div>
          <nav className="flex gap-1 overflow-x-auto scrollbar-none">
            {NAV.map(({ to, label, Icon }) => (
              <NavLink key={to} to={to} className={({ isActive }) =>
                clsx(
                  'flex items-center gap-1.5 px-3 py-2 rounded-xl',
                  'text-xs font-medium transition-colors',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
                  isActive
                    ? 'bg-brand-600/20 text-brand-300 ring-1 ring-brand-500/25'
                    : 'text-slate-400 hover:text-slate-200'
                )
              }>
                <Icon size={14}/>
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="flex items-center gap-1.5 px-3 py-1.5
              rounded-lg text-xs text-slate-400 hover:text-red-400
              hover:bg-red-500/10 transition-colors
              focus:outline-none focus-visible:ring-2
              focus-visible:ring-brand-500"
          >
            <LogOut size={14}/>
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-3 py-4 sm:px-4 sm:py-6">
        <Outlet/>
      </main>
    </div>
  )
}

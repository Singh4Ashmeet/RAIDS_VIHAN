import { useNavigate } from 'react-router-dom'
import {
  BarChart2,
  Brain,
  Building2,
  Radio,
  RefreshCw,
  Truck,
} from 'lucide-react'

import Button from '../components/ui/Button'

const features = [
  {
    icon: Brain,
    iconBg: 'rgba(168, 85, 247, 0.2)',
    iconColor: '#c084fc',
    title: 'AI Triage',
    description: 'Severity classification under 200ms using trained ML models.',
  },
  {
    icon: Truck,
    iconBg: 'rgba(59, 130, 246, 0.2)',
    iconColor: '#60a5fa',
    title: 'Smart Routing',
    description: 'Nearest available unit with live traffic-aware ETA scoring.',
  },
  {
    icon: Building2,
    iconBg: 'rgba(16, 185, 129, 0.2)',
    iconColor: '#34d399',
    title: 'Hospital Match',
    description: 'Bed availability, specialization, and occupancy scoring.',
  },
  {
    icon: Radio,
    iconBg: 'rgba(245, 158, 11, 0.2)',
    iconColor: '#fbbf24',
    title: 'Live Tracking',
    description: 'WebSocket updates stream ambulance and hospital state in real time.',
  },
  {
    icon: RefreshCw,
    iconBg: 'rgba(239, 68, 68, 0.2)',
    iconColor: '#f87171',
    title: 'Fallback Logic',
    description: 'Never crashes. Queues incidents when all units are deployed.',
  },
  {
    icon: BarChart2,
    iconBg: 'rgba(34, 211, 238, 0.2)',
    iconColor: '#67e8f9',
    title: 'Analytics',
    description: 'Compare AI vs baseline dispatch performance with live metrics.',
  },
]

const stats = [
  { value: 'under 2 min', label: 'dispatch time' },
  { value: '98.4%', label: 'system uptime' },
  { value: '15+', label: 'cities covered' },
]

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-surface text-slate-100">
      <nav className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center gap-3">
            <span className="relative inline-flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75"/>
              <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500"/>
            </span>
            <span className="text-lg font-bold text-white">RAID Nexus</span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={() => navigate('/login')}>
              Login
            </Button>
            <Button variant="primary" onClick={() => navigate('/login')}>
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      <section
        className="relative flex min-h-screen items-center justify-center overflow-hidden"
        style={{
          backgroundImage: [
            'linear-gradient(rgba(51,65,85,0.4) 1px, transparent 1px)',
            'linear-gradient(to right, rgba(51,65,85,0.4) 1px, transparent 1px)',
          ].join(', '),
          backgroundSize: '48px 48px',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%,-50%)',
            width: 'min(72vw, 500px)',
            height: 'min(72vw, 500px)',
            background: 'radial-gradient(circle, rgba(37,99,235,0.15), transparent 70%)',
            borderRadius: '50%',
            pointerEvents: 'none',
          }}
        />
        <div className="relative z-10 mx-auto max-w-3xl px-6 text-center">
          <div className="mb-6 inline-block rounded-full border border-red-500/30 bg-red-500/10 px-4 py-1.5 text-sm text-red-400">
            AI-Powered Emergency Dispatch
          </div>
          <h1 className="mb-6 text-4xl xs:text-5xl font-bold text-white md:text-7xl leading-tight">
            <span className="block">Save Lives Faster</span>
            <span className="block">
              With{' '}
              <span
                style={{
                  background: 'linear-gradient(to right, #60a5fa, #a78bfa)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                Intelligent Routing
              </span>
            </span>
          </h1>
          <p className="mx-auto mb-10 max-w-2xl text-base sm:text-xl text-slate-400 px-2">
            Real-time ambulance dispatch, hospital matching, and AI triage built for India&apos;s emergency response.
          </p>
          <div className="flex flex-col xs:flex-row flex-wrap justify-center gap-3 sm:gap-4 w-full sm:w-auto px-4 xs:px-0">
            <div className="w-full xs:w-auto"><Button variant="danger" size="lg" onClick={() => navigate('/user/sos')}>
              Request Emergency
            </Button></div>
            <div className="w-full xs:w-auto"><Button variant="primary" size="lg" onClick={() => navigate('/login')}>
              Admin Dashboard
            </Button></div>
          </div>
          <div className="mt-8 sm:mt-10 flex flex-wrap justify-center gap-6 sm:gap-8">
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-2xl font-bold text-white">{stat.value}</div>
                <div className="mt-1 text-sm text-slate-400">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 sm:px-6 py-12 sm:py-24">
        <h2 className="mb-4 text-center text-3xl font-bold text-white">
          Built for real emergencies
        </h2>
        <p className="mb-16 text-center text-slate-400">
          Every second matters.
        </p>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => {
            const Icon = feature.icon
            return (
              <div
                key={feature.title}
                className="cursor-default rounded-2xl border border-border bg-card p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-500/50"
              >
                <div
                  className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: feature.iconBg }}
                >
                  <Icon size={20} style={{ color: feature.iconColor }}/>
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">
                  {feature.title}
                </h3>
                <p className="text-sm leading-6 text-slate-400">
                  {feature.description}
                </p>
              </div>
            )
          })}
        </div>
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-slate-500">
        Copyright 2026 RAID Nexus | Vihan 9.0 Hackathon | Built for India
      </footer>
    </div>
  )
}

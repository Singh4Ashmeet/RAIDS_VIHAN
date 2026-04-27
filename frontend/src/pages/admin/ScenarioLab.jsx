import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { Activity, AlertTriangle, Pause, Play, RotateCcw, Route, Siren } from 'lucide-react'

import { fetchAnalytics } from '../../services/api'
import Skeleton from '../../components/ui/Skeleton'
import ScenarioCard from '../../components/scenario/ScenarioCard'
import ScenarioStepTrace from '../../components/scenario/ScenarioStepTrace'
import ScenarioEventLog from '../../components/scenario/ScenarioEventLog'

const SCENARIOS = [
  {
    type: 'cardiac',
    title: 'Cardiac P1 Dispatch',
    description: 'Injects a critical cardiac emergency and validates ALS routing, ETA scoring, and hospital pre-alert.',
    Icon: Siren,
    accentColor: 'red',
    affects: ['Critical', 'ALS routing', 'Pre-alert'],
    ttlSeconds: null,
  },
  {
    type: 'overload',
    title: 'Hospital Overload',
    description: 'Pushes a hospital into diversion so the dispatcher proves capacity-aware rerouting.',
    Icon: AlertTriangle,
    accentColor: 'amber',
    affects: ['High load', 'Diversion', 'Capacity'],
    ttlSeconds: null,
  },
  {
    type: 'breakdown',
    title: 'Ambulance Breakdown',
    description: 'Takes one unit offline for 60 seconds to test live fleet resilience and fallback dispatch.',
    Icon: Activity,
    accentColor: 'blue',
    affects: ['Unit outage', 'Re-plan', 'Fallback'],
    ttlSeconds: 60,
  },
  {
    type: 'traffic',
    title: 'Traffic Spike',
    description: 'Applies a 2.5x congestion multiplier to Bengaluru routes and watches ETA decisions shift.',
    Icon: Route,
    accentColor: 'blue',
    affects: ['Traffic', 'ETA', 'Routing'],
    ttlSeconds: 60,
  },
]

function AnalyticsStrip({ analytics, loading }) {
  if (loading) {
    return (
      <div className="flex flex-wrap gap-2 mb-5">
        {[...Array(5)].map((_, index) => (
          <Skeleton key={index} className="h-7 w-28 rounded-full" />
        ))}
      </div>
    )
  }

  if (!analytics) {
    return null
  }

  const pills = [
    { label: 'Incidents', value: analytics.incidents_today, cls: 'text-slate-300' },
    { label: 'Dispatches', value: analytics.dispatches_today, cls: 'text-slate-300' },
    {
      label: 'AI ETA',
      value: `${Number(analytics.avg_eta_ai).toFixed(1)} min`,
      cls: analytics.avg_eta_ai < analytics.avg_eta_baseline ? 'text-emerald-400' : 'text-amber-400',
    },
    {
      label: 'Baseline ETA',
      value: `${Number(analytics.avg_eta_baseline).toFixed(1)} min`,
      cls: 'text-slate-400',
    },
    {
      label: 'Overloads prevented',
      value: analytics.overloads_prevented,
      cls: analytics.overloads_prevented > 0 ? 'text-emerald-400' : 'text-slate-300',
    },
  ]

  return (
    <div className="flex flex-wrap gap-2 mb-5">
      {pills.map(({ label, value, cls }) => (
        <span
          key={label}
          aria-label={`${label}: ${value}`}
          className="inline-flex items-center gap-1.5 rounded-full bg-slate-800 border border-border px-3 py-1 text-xs text-slate-300"
        >
          <span className="text-slate-500">{label}</span>
          <span className={clsx('font-medium', cls)}>{value}</span>
        </span>
      ))}
    </div>
  )
}

export default function ScenarioLab() {
  const [runningType, setRunningType] = useState(null)
  const [activeType, setActiveType] = useState(null)
  const [activeResult, setActiveResult] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(true)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = () => {
      fetchAnalytics()
        .then((data) => {
          if (!cancelled) {
            setAnalytics(data)
          }
        })
        .catch(() => {})
        .finally(() => {
          if (!cancelled) {
            setAnalyticsLoading(false)
          }
        })
    }

    load()
    const id = setInterval(load, 30_000)

    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  function handleResult(type, result) {
    setActiveType(type)
    setActiveResult(result)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <h1 className="text-[28px] font-semibold text-white">Scenario Lab</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Simulation testing for high-pressure dispatch states, fallback paths, and routing behavior.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setPaused((value) => !value)}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-slate-800 px-3 py-2 text-sm text-slate-300 transition hover:text-white"
          >
            {paused ? <Play size={16} /> : <Pause size={16} />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveType(null)
              setActiveResult(null)
              setRunningType(null)
            }}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-slate-800 px-3 py-2 text-sm text-slate-300 transition hover:text-white"
          >
            <RotateCcw size={16} />
            Reset
          </button>
        </div>
      </div>

      <AnalyticsStrip analytics={analytics} loading={analyticsLoading} />

      {paused ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          Scenario controls are paused locally. Resume to run another backend scenario.
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {SCENARIOS.map((scenario) => (
            <ScenarioCard
              key={scenario.type}
              {...scenario}
              globallyBusy={paused || (runningType !== null && runningType !== scenario.type)}
              onRunStart={() => {
                setRunningType(scenario.type)
                setActiveType(scenario.type)
                setActiveResult(null)
              }}
              onResult={(result) => {
                setRunningType(null)
                handleResult(scenario.type, result)
              }}
              onError={(errorMessage) => {
                setRunningType(null)
                setActiveType(scenario.type)
                setActiveResult({
                  error: true,
                  error_message: errorMessage,
                  scenario: scenario.type,
                })
              }}
            />
          ))}
        </div>

        <div className="min-w-0 space-y-5">
          <ScenarioStepTrace type={activeType} result={activeResult} />
          <ScenarioEventLog />
        </div>
      </div>
    </div>
  )
}

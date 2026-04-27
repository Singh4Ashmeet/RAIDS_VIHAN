import { motion, useReducedMotion } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  FlaskConical,
  Route,
  Siren,
  XCircle,
} from 'lucide-react'

import Badge from '../ui/Badge'
import Card from '../ui/Card'
import Skeleton from '../ui/Skeleton'

const SCENARIO_META = {
  cardiac: {
    title: 'Cardiac P1 Dispatch',
    Icon: Siren,
  },
  overload: {
    title: 'Hospital Overload',
    Icon: AlertTriangle,
  },
  breakdown: {
    title: 'Ambulance Breakdown',
    Icon: Activity,
  },
  traffic: {
    title: 'Traffic Spike',
    Icon: Route,
  },
}

function formatShortId(value) {
  return value ? `${value.slice(0, 8)}\u2026` : null
}

function formatEta(value) {
  return value != null ? `${Number(value).toFixed(1)} min ETA` : null
}

function formatTime(value) {
  if (!value) {
    return null
  }

  return new Date(value).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function buildSteps(type, result) {
  if (result?.error) {
    return [
      {
        label: 'Scenario request',
        value: result.error_message || 'Request failed',
        status: 'error',
      },
    ]
  }

  if (type === 'cardiac') {
    return [
      {
        label: 'Incident created',
        value: formatShortId(result?.dispatch_plan?.id),
        status: 'success',
      },
      {
        label: 'ALS unit selected',
        value: result?.dispatch_plan?.ambulance_id,
        status: 'success',
      },
      {
        label: 'Route computed',
        value: formatEta(result?.dispatch_plan?.eta_minutes),
        status: 'success',
      },
      {
        label: 'Hospital pre-alert',
        value: result?.dispatch_plan?.hospital_name || result?.dispatch_plan?.hospital_id,
        status: 'success',
      },
      {
        label: 'Dispatch status',
        value: result?.dispatch_status === 'fallback' ? result?.dispatch_message : 'Confirmed',
        status: result?.dispatch_status === 'fallback' ? 'warning' : 'success',
      },
    ]
  }

  if (type === 'overload') {
    return [
      {
        label: 'Hospital targeted',
        value: result?.overload?.hospital_id,
        status: 'success',
      },
      {
        label: 'Occupancy set',
        value: result?.overload?.occupancy_pct != null ? `${result.overload.occupancy_pct}%` : null,
        status: 'warning',
      },
      {
        label: 'Diversion active',
        value: result?.overload?.diversion_status ? 'Yes \u2014 rerouting incoming' : 'No',
        status: result?.overload?.diversion_status ? 'warning' : 'success',
      },
      {
        label: 'Fallback routing',
        value: 'Engine triggered automatically',
        status: 'success',
      },
    ]
  }

  if (type === 'breakdown') {
    return [
      {
        label: 'Ambulance taken offline',
        value: result?.breakdown?.ambulance_id,
        status: 'warning',
      },
      {
        label: 'Outage expires',
        value: formatTime(result?.breakdown?.expires_at),
        status: 'success',
      },
      {
        label: 'Fallback dispatch',
        value: 'Re-plan triggered from available pool',
        status: 'success',
      },
    ]
  }

  if (type === 'traffic') {
    return [
      {
        label: 'City affected',
        value: result?.traffic?.city,
        status: 'warning',
      },
      {
        label: 'Congestion multiplier',
        value: result?.traffic?.multiplier != null ? `${result.traffic.multiplier}\u00d7` : null,
        status: 'warning',
      },
      {
        label: 'Override expires',
        value: formatTime(result?.traffic?.expires_at),
        status: 'success',
      },
      {
        label: 'ETA adjustment',
        value: 'Active \u2014 all routes scaled',
        status: 'warning',
      },
    ]
  }

  return []
}

function StepIcon({ status }) {
  if (status === 'warning') {
    return (
      <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-amber-500/20">
        <AlertTriangle size={12} className="text-amber-400" />
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-red-500/20">
        <XCircle size={12} className="text-red-400" />
      </div>
    )
  }

  return (
    <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-emerald-500/20">
      <CheckCircle size={12} className="text-emerald-400" />
    </div>
  )
}

export default function ScenarioStepTrace({ type, result }) {
  const prefersReducedMotion = useReducedMotion()
  const meta = SCENARIO_META[type]
  const Icon = meta?.Icon || FlaskConical
  const steps = type && result ? buildSteps(type, result) : []
  const isFallback = type === 'cardiac' && result?.dispatch_status === 'fallback'
  const badgeVariant = result?.error ? 'error' : isFallback ? 'warning' : 'success'
  const badgeLabel = result?.error ? 'Error' : isFallback ? 'Fallback' : 'Triggered'

  if (type == null) {
    return (
      <div role="status" aria-live="polite" aria-label="No scenario active">
        <Card className="flex flex-col items-center justify-center min-h-[260px] text-center gap-3">
          <div className="rounded-2xl bg-slate-800 p-4">
            <FlaskConical size={24} className="text-slate-500" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-300">Select a scenario</p>
            <p className="text-xs text-slate-500 mt-1">
              Run a scenario from the left panel to see the live dispatch trace here.
            </p>
          </div>
        </Card>
      </div>
    )
  }

  if (result == null) {
    return (
      <div role="status" aria-live="polite">
        <Card>
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-slate-800 p-3">
              <Icon size={18} className="text-slate-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">{meta?.title || 'Scenario trace'}</h2>
              <p className="text-xs text-slate-500 mt-1">Awaiting live scenario response</p>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full rounded-xl" />
            ))}
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div role="status" aria-live="polite">
      <Card>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="rounded-2xl bg-slate-800 p-3">
              <Icon size={18} className="text-slate-300" />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-white">{meta?.title || 'Scenario trace'}</h2>
            </div>
          </div>
          <Badge variant={badgeVariant}>{badgeLabel}</Badge>
        </div>

        <hr className="border-border my-4" />

        <motion.div
          key={type + JSON.stringify(result)}
          initial="hidden"
          animate="visible"
          variants={
            prefersReducedMotion
              ? {}
              : {
                  hidden: {},
                  visible: { transition: { staggerChildren: 0.08 } },
                }
          }
        >
          {steps.map((step) => (
            <motion.div
              key={step.label}
              variants={
                prefersReducedMotion
                  ? {}
                  : {
                      hidden: { opacity: 0, y: 6 },
                      visible: { opacity: 1, y: 0, transition: { duration: 0.2 } },
                    }
              }
            >
              <div className="flex items-start gap-3 py-2.5 border-b border-border last:border-0">
                <StepIcon status={step.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-slate-400">{step.label}</p>
                  <p className="text-sm text-slate-100 font-medium mt-0.5 truncate">
                    {step.value || '\u2014'}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </Card>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { clsx } from 'clsx'
import { Waves } from 'lucide-react'

import Badge from '../ui/Badge'
import Card from '../ui/Card'
import EmptyState from '../ui/EmptyState'
import useDispatchStore from '../../store/dispatchStore'

const scenarioBorderMap = {
  cardiac: 'border-l-2 border-red-500/60',
  overload: 'border-l-2 border-amber-500/60',
  breakdown: 'border-l-2 border-purple-500/60',
  traffic: 'border-l-2 border-blue-500/60',
}

function formatTime(value) {
  if (!value) {
    return 'Just now'
  }

  return new Date(value).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function normalizeDispatchEntry(entry) {
  if (!entry || typeof entry !== 'object') {
    return null
  }

  if ('data' in entry && entry.data && typeof entry.data === 'object') {
    return {
      status: entry.status || 'success',
      message: entry.message,
      data: entry.data,
    }
  }

  return {
    status: entry.status === 'fallback' ? 'fallback' : 'success',
    message: entry.message,
    data: entry,
  }
}

function formatDispatchUnit(ambulanceId) {
  if (!ambulanceId) {
    return 'AMB-'
  }

  return String(ambulanceId).startsWith('AMB-') ? ambulanceId : `AMB-${ambulanceId}`
}

function buildDispatchEvents(dispatchHistory) {
  return dispatchHistory
    .map((entry, index) => {
      const normalized = normalizeDispatchEntry(entry)
      const plan = normalized?.data

      if (!plan) {
        return null
      }

      return {
        key: `dispatch-${plan.id || index}`,
        sortTime: plan.created_at || plan.timestamp || new Date().toISOString(),
        label: 'Dispatch',
        variant: normalized.status === 'fallback' ? 'warning' : 'success',
        time: formatTime(plan.created_at || plan.timestamp),
        summary: `${formatDispatchUnit(plan.ambulance_id)} \u2192 ${plan.hospital_id || '--'} \u00b7 ${Number(plan.eta_minutes || 0).toFixed(1)} min ETA`,
        borderClass: 'border-l-2 border-emerald-500/40',
      }
    })
    .filter(Boolean)
}

function buildNotificationEvents(notifications) {
  return notifications
    .map((entry, index) => {
      const timestamp = entry?.timestamp || entry?.created_at || new Date().toISOString()

      if (entry?.type === 'hospital_notification') {
        return {
          key: `notify-${entry.hospital_id || 'hospital'}-${timestamp}-${index}`,
          sortTime: timestamp,
          label: 'Notify',
          variant: 'info',
          time: formatTime(timestamp),
          summary: `Pre-alert for ${entry.patient_name || 'patient'} sent to ${entry.hospital_id || '--'}`,
          borderClass: 'border-l-2 border-blue-500/40',
        }
      }

      if (entry?.type === 'scenario_triggered') {
        return {
          key: `scenario-${entry.scenario || 'unknown'}-${timestamp}-${index}`,
          sortTime: timestamp,
          label: 'Scenario',
          variant: 'neutral',
          time: formatTime(timestamp),
          summary: `${entry.title || entry.scenario || 'Scenario'} triggered`,
          borderClass: scenarioBorderMap[entry.scenario] || 'border-l-2 border-border',
        }
      }

      if (entry?.type === 'route_change') {
        return {
          key: `route-${timestamp}-${index}`,
          sortTime: timestamp,
          label: 'Reroute',
          variant: 'warning',
          time: formatTime(timestamp),
          summary: entry.message || 'Route changed due to live conditions',
          borderClass: 'border-l-2 border-amber-500/50',
        }
      }

      if (entry?.type === 'tick' || entry?.label === 'Tick') {
        return {
          key: `tick-${timestamp}-${index}`,
          sortTime: timestamp,
          label: 'Tick',
          variant: 'neutral',
          time: formatTime(timestamp),
          summary: entry.summary || 'Simulation tick received',
          borderClass: 'border-l-2 border-slate-500/40',
        }
      }

      return null
    })
    .filter(Boolean)
}

export default function ScenarioEventLog() {
  const [hideTicks, setHideTicks] = useState(false)
  const prefersReducedMotion = useReducedMotion()

  const dispatchHistory = useDispatchStore((state) => state.dispatchHistory || [])
  const notifications = useDispatchStore((state) => state.notifications || [])
  const wsStatus = useDispatchStore((state) => state.wsStatus)

  const events = useMemo(() => {
    const merged = [...buildDispatchEvents(dispatchHistory), ...buildNotificationEvents(notifications)]
      .sort((left, right) => new Date(right.sortTime).getTime() - new Date(left.sortTime).getTime())

    const filtered = hideTicks ? merged.filter((entry) => entry.label !== 'Tick') : merged

    return filtered.slice(0, 15)
  }, [dispatchHistory, notifications, hideTicks])

  return (
    <div role="log" aria-live="polite" aria-label="Scenario event log">
      <Card>
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-semibold text-white">Event Log</h2>
            <p className="text-xs text-slate-400 mt-0.5">Live scenario + dispatch activity</p>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={hideTicks}
                onChange={(event) => setHideTicks(event.target.checked)}
                className="rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500"
              />
              Hide ticks
            </label>
            <div className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">
              {events.length} items
            </div>
          </div>
        </div>

        {wsStatus !== 'connected' && (
          <div className="mb-3 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-400">
            Live feed reconnecting - displayed events may be stale
          </div>
        )}

        {events.length === 0 ? (
          <EmptyState
            icon={Waves}
            title="No events yet"
            subtitle="Run a scenario or wait for dispatch activity."
          />
        ) : (
          <AnimatePresence initial={false}>
            <div className="space-y-2">
              {events.map((event) => (
                <motion.div
                  key={event.key}
                  layout
                  initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 8 }}
                  animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: prefersReducedMotion ? 0 : 0.15 }}
                  className={clsx(
                    'flex items-start justify-between gap-3 rounded-xl',
                    'border border-border bg-slate-800/40 px-4 py-3',
                    event.borderClass
                  )}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={event.variant}>{event.label}</Badge>
                      <span className="text-xs text-slate-500">{event.time}</span>
                    </div>
                    <p className="mt-1.5 text-sm text-slate-200 leading-snug">{event.summary}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </AnimatePresence>
        )}
      </Card>
    </div>
  )
}

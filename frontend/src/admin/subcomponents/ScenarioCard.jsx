import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { clsx } from 'clsx'
import { Play } from 'lucide-react'

import Button from '../../components/ui/Button'
import Card from '../../components/ui/Card'
import { triggerScenario } from '../../services/api'
import useDispatchStore from '../../store/dispatchStore'

const accentMap = {
  red: {
    border: 'border-red-500/40',
    glow: 'shadow-red-500/20',
    ring: 'ring-red-500/30',
    iconBg: 'bg-red-500/10',
    iconText: 'text-red-400',
    solidBg: 'bg-red-500',
  },
  amber: {
    border: 'border-amber-500/40',
    glow: 'shadow-amber-500/20',
    ring: 'ring-amber-500/30',
    iconBg: 'bg-amber-500/10',
    iconText: 'text-amber-400',
    solidBg: 'bg-amber-500',
  },
  purple: {
    border: 'border-purple-500/40',
    glow: 'shadow-purple-500/20',
    ring: 'ring-purple-500/30',
    iconBg: 'bg-purple-500/10',
    iconText: 'text-purple-400',
    solidBg: 'bg-purple-500',
  },
  blue: {
    border: 'border-blue-500/40',
    glow: 'shadow-blue-500/20',
    ring: 'ring-blue-500/30',
    iconBg: 'bg-blue-500/10',
    iconText: 'text-blue-400',
    solidBg: 'bg-blue-500',
  },
}

function formatDurationText(status, ttlSeconds, progress) {
  if (ttlSeconds == null) {
    return 'Instantaneous'
  }

  if (status === 'running') {
    const remainingSeconds = Math.max(0, Math.ceil((progress / 100) * ttlSeconds))
    return `${remainingSeconds} s remaining`
  }

  return `${ttlSeconds} s duration`
}

function formatScenarioError(error) {
  const value = error?.message ?? error
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value
      .map((item) => formatScenarioError(item))
      .filter(Boolean)
      .join('; ') || 'Scenario request failed'
  }
  if (value && typeof value === 'object') {
    if (typeof value.detail === 'string') return value.detail
    if (typeof value.message === 'string') return value.message
    if (typeof value.msg === 'string') return value.msg
    try {
      return JSON.stringify(value)
    } catch {
      return 'Scenario request failed'
    }
  }
  return 'Scenario request failed'
}

export default function ScenarioCard({
  type,
  title,
  description,
  Icon,
  accentColor,
  affects,
  ttlSeconds,
  globallyBusy = false,
  onRunStart,
  onResult,
  onError,
}) {
  const [status, setStatus] = useState('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [progress, setProgress] = useState(100)

  const setLastDispatch = useDispatchStore((state) => state.setLastDispatch)
  const pushNotification = useDispatchStore((state) => state.pushNotification)

  const countdownRef = useRef(null)
  const resetTimerRef = useRef(null)
  const accent = accentMap[accentColor] || accentMap.blue
  const prefersReducedMotion = useReducedMotion()

  function clearCountdown() {
    clearInterval(countdownRef.current)
    countdownRef.current = null
  }

  function clearResetTimer() {
    clearTimeout(resetTimerRef.current)
    resetTimerRef.current = null
  }

  function resetToIdle() {
    clearCountdown()
    clearResetTimer()
    setProgress(100)
    setStatus('idle')
  }

  function startCountdown() {
    if (ttlSeconds == null) {
      return
    }

    const start = Date.now()
    setProgress(100)
    clearCountdown()

    countdownRef.current = setInterval(() => {
      const elapsed = (Date.now() - start) / 1000
      const remaining = Math.max(0, 1 - elapsed / ttlSeconds) * 100

      setProgress(remaining)

      if (remaining <= 0) {
        clearCountdown()
      }
    }, 100)
  }

  useEffect(() => () => {
    clearCountdown()
    clearResetTimer()
  }, [])

  const statusCardClass = {
    idle: '',
    running: `ring-1 shadow-lg ${accent.ring} ${accent.glow} ${accent.border}`,
    complete: 'ring-1 ring-emerald-500/30 shadow-lg shadow-emerald-500/10',
    error: 'ring-1 ring-red-500/40 shadow-lg shadow-red-500/10',
  }[status]

  async function handleClick() {
    if (status === 'running' || globallyBusy) {
      return
    }

    clearResetTimer()
    clearCountdown()
    setProgress(100)
    setStatus('running')
    setErrorMessage('')
    startCountdown()
    onRunStart?.()

    try {
      const result = await triggerScenario(type)
      const plan = result?.dispatch_plan

      clearCountdown()

      if (plan) {
        setLastDispatch(plan)
      }

      pushNotification({
        type: 'scenario_triggered',
        scenario: type,
        title,
        timestamp: new Date().toISOString(),
      })

      setStatus('complete')
      onResult?.(result)
      resetTimerRef.current = setTimeout(() => {
        resetToIdle()
      }, 8000)
    } catch (error) {
      const nextErrorMessage = formatScenarioError(error) || 'Scenario failed - check backend logs'

      clearCountdown()
      setStatus('error')
      setErrorMessage(nextErrorMessage)
      onError?.(nextErrorMessage)
      resetTimerRef.current = setTimeout(() => {
        resetToIdle()
      }, 6000)
    }
  }

  return (
    <div role="region" aria-label={`${title} scenario`}>
      <Card className={clsx('transition-all duration-300', statusCardClass)}>
        <div className="flex items-start gap-3">
          <div className={clsx('rounded-2xl p-3', accent.iconBg)}>
            {Icon ? <Icon size={18} className={accent.iconText} /> : null}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold text-white">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
          </div>
        </div>

        <div className="mt-4 border-t border-border pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">Affects:</span>
            {affects.map((item) => (
              <span
                key={item}
                className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400 border border-border"
              >
                {item}
              </span>
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-xs text-slate-400">
              Duration: {formatDurationText(status, ttlSeconds, progress)}
            </span>
            <div className="w-full sm:w-40">
              <Button
                variant="secondary"
                className="w-full"
                icon={Play}
                loading={status === 'running'}
                disabled={globallyBusy && status !== 'running'}
                aria-busy={status === 'running'}
                aria-disabled={globallyBusy}
                aria-label={`Run ${title} scenario`}
                onClick={handleClick}
              >
                {status === 'running' ? 'Running...' : 'Run Scenario'}
              </Button>
            </div>
          </div>
        </div>

        {ttlSeconds != null && status === 'running' ? (
          <div className="h-1 w-full rounded-full bg-slate-800 overflow-hidden mt-3">
            <div
              className={clsx('h-full rounded-full transition-none', accent.solidBg)}
              style={{ width: `${progress}%` }}
            />
          </div>
        ) : null}

        <AnimatePresence>
          {(status === 'complete' || status === 'error') && (
            <motion.div
              key={status}
              initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: -4 }}
              animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.2 }}
            >
              {status === 'complete' ? (
                <div className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
                  Scenario triggered - observe the step trace
                </div>
              ) : (
                <div className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-400">
                  {errorMessage}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </div>
  )
}

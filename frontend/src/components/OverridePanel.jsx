import clsx from 'clsx'
import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle,
  ShieldAlert,
  TriangleAlert,
} from 'lucide-react'

import useDispatchStore from '../store/dispatchStore'
import Badge from './ui/Badge'
import Button from './ui/Button'
import Card from './ui/Card'
import ProgressBar from './ui/ProgressBar'
import Skeleton from './ui/Skeleton'
import StatusDot from './ui/StatusDot'

const REASON_CATEGORIES = [
  ['ambulance_closer', 'Ambulance Closer'],
  ['hospital_specialty', 'Hospital Specialty'],
  ['local_knowledge', 'Local Knowledge'],
  ['ai_error', 'AI Error'],
  ['resource_conflict', 'Resource Conflict'],
  ['other', 'Other'],
]

function resetLocalState(setters) {
  setters.setSelectedAmb(null)
  setters.setSelectedHosp(null)
  setters.setReason('')
  setters.setReasonCat('')
  setters.setConfirming(false)
}

export default function OverridePanel({ dispatch, city, onSuccess }) {
  const availableUnits = useDispatchStore((s) => s.availableUnits)
  const loadingOverride = useDispatchStore((s) => s.loadingOverride)
  const overrideError = useDispatchStore((s) => s.overrideError)
  const fetchAvailableUnits = useDispatchStore((s) => s.fetchAvailableUnits)
  const submitOverride = useDispatchStore((s) => s.submitOverride)
  const clearOverrideError = useDispatchStore((s) => s.clearOverrideError)

  const [isExpanded, setIsExpanded] = useState(false)
  const [selectedAmb, setSelectedAmb] = useState(null)
  const [selectedHosp, setSelectedHosp] = useState(null)
  const [reason, setReason] = useState('')
  const [reasonCat, setReasonCat] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [successResult, setSuccessResult] = useState(null)

  const incidentLat = dispatch?.incident_lat ?? dispatch?.location_lat
  const incidentLng = dispatch?.incident_lng ?? dispatch?.location_lng
  const setters = {
    setSelectedAmb,
    setSelectedHosp,
    setReason,
    setReasonCat,
    setConfirming,
  }

  useEffect(() => {
    if (!isExpanded || !city || !dispatch?.id) return
    fetchAvailableUnits(city, incidentLat, incidentLng)
  }, [city, dispatch?.id, fetchAvailableUnits, incidentLat, incidentLng, isExpanded])

  useEffect(() => {
    if (!successResult) return undefined
    const timeout = setTimeout(() => {
      setIsExpanded(false)
      setSuccessResult(null)
      resetLocalState(setters)
      onSuccess?.()
    }, 3000)
    return () => clearTimeout(timeout)
  }, [onSuccess, successResult])

  const ambulances = useMemo(() => {
    const items = availableUnits?.ambulances || []
    return [...items].sort((a, b) => {
      if (a.type === b.type) return a.id.localeCompare(b.id)
      return a.type === 'ALS' ? -1 : 1
    })
  }, [availableUnits?.ambulances])

  const hospitals = availableUnits?.hospitals || []
  const selectedAmbulance = ambulances.find((item) => item.id === selectedAmb)
  const selectedHospital = hospitals.find((item) => item.id === selectedHosp)
  const canReview = selectedAmb && selectedHosp && reasonCat && reason.trim().length >= 20
  const reasonCharsLeft = 500 - reason.length

  const handleCancel = () => {
    setIsExpanded(false)
    setSuccessResult(null)
    clearOverrideError?.()
    resetLocalState(setters)
  }

  const handleSubmit = async () => {
    const result = await submitOverride({
      dispatch_id: dispatch.id,
      proposed_ambulance_id: selectedAmb,
      proposed_hospital_id: selectedHosp,
      reason: reason.trim(),
      reason_category: reasonCat,
    })
    if (result) {
      setSuccessResult(result)
    }
  }

  if (!isExpanded) {
    return (
      <button
        type="button"
        onClick={() => setIsExpanded(true)}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-amber-500/30 py-2 text-sm font-medium text-amber-400 transition hover:border-amber-500/50 hover:bg-amber-500/5 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
      >
        <ShieldAlert size={14} />
        Override Dispatch
      </button>
    )
  }

  if (successResult) {
    return (
      <Card className="mt-3 text-center">
        <CheckCircle size={32} className="mx-auto text-emerald-400" />
        <p className="mt-3 font-medium text-white">Override Applied</p>
        <p className="mt-2 text-sm text-brand-500">
          New ETA: {Number(successResult.new_eta_minutes || 0).toFixed(1)}min
        </p>
      </Card>
    )
  }

  return (
    <Card className="mt-3">
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-400">
        <TriangleAlert size={16} />
        <span>Human Override Mode - Your decision will be logged</span>
      </div>

      {!availableUnits || (loadingOverride && !confirming) ? (
        <Skeleton count={2} />
      ) : confirming ? (
        <div className="rounded-xl border border-border bg-slate-900/70 p-4">
          <p className="text-sm font-semibold text-white">Confirm Override</p>
          <div className="mt-4 space-y-2 text-sm">
            <p className="flex justify-between gap-3 text-slate-400">
              <span>New Ambulance</span>
              <span className="font-mono text-white">{selectedAmb}</span>
            </p>
            <p className="flex justify-between gap-3 text-slate-400">
              <span>New Hospital</span>
              <span className="font-mono text-white">{selectedHosp}</span>
            </p>
          </div>
          <p className="mt-4 text-sm italic text-slate-400">{reason}</p>
          <p className="mt-3 text-xs text-amber-400">
            This action will be permanently logged in the audit trail.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          <section>
            <p className="mb-2 text-xs uppercase tracking-widest text-slate-400">Select Ambulance</p>
            <div className="space-y-2">
              {ambulances.map((ambulance) => {
                const disabled = ambulance.id === dispatch.ambulance_id || ambulance.status !== 'available'
                return (
                  <button
                    key={ambulance.id}
                    type="button"
                    disabled={disabled}
                    onClick={() => setSelectedAmb(ambulance.id)}
                    className={clsx(
                      'flex w-full cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-left transition focus:outline-none focus:ring-2 focus:ring-brand-500',
                      selectedAmb === ambulance.id
                        ? 'border-brand-500 bg-brand-500/10'
                        : 'border-border hover:border-brand-500/40',
                      disabled && 'cursor-not-allowed opacity-40'
                    )}
                  >
                    <StatusDot status={ambulance.status} />
                    <span className="font-mono text-sm text-white">{ambulance.id}</span>
                    <Badge variant={ambulance.type === 'ALS' ? 'info' : 'neutral'}>{ambulance.type}</Badge>
                    <div className="ml-auto flex items-center gap-3">
                      <span className="text-xs text-brand-500">
                        ETA {ambulance.eta_to_scene == null ? '-' : Number(ambulance.eta_to_scene).toFixed(1)}min
                      </span>
                      <ProgressBar value={ambulance.crew_readiness} className="bg-emerald-500" />
                    </div>
                  </button>
                )
              })}
            </div>
          </section>

          <section>
            <p className="mb-2 text-xs uppercase tracking-widest text-slate-400">Select Hospital</p>
            <div className="space-y-2">
              {hospitals.map((hospital) => {
                const disabled = Boolean(hospital.diversion_status)
                return (
                  <button
                    key={hospital.id}
                    type="button"
                    disabled={disabled}
                    onClick={() => setSelectedHosp(hospital.id)}
                    className={clsx(
                      'flex w-full cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-left transition focus:outline-none focus:ring-2 focus:ring-brand-500',
                      selectedHosp === hospital.id
                        ? 'border-brand-500 bg-brand-500/10'
                        : 'border-border hover:border-brand-500/40',
                      disabled && 'cursor-not-allowed opacity-40'
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-white">{hospital.name}</p>
                        {hospital.diversion_status ? <Badge variant="error">Diversion</Badge> : null}
                      </div>
                      <p className="text-xs text-slate-400">{city}</p>
                    </div>
                    <ProgressBar value={hospital.occupancy_pct} max={100} className="bg-amber-500" />
                    <span className="text-xs text-slate-400">{hospital.er_wait_minutes}m ER</span>
                  </button>
                )
              })}
            </div>
          </section>

          <section>
            <p className="mb-2 text-xs uppercase tracking-widest text-slate-400">Reason Category</p>
            <div className="flex flex-wrap gap-2">
              {REASON_CATEGORIES.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setReasonCat(value)}
                  className={clsx(
                    'rounded-full border px-3 py-1.5 text-xs font-medium transition focus:outline-none focus:ring-2 focus:ring-brand-500',
                    reasonCat === value
                      ? 'border-brand-500 bg-brand-500/10 text-brand-500'
                      : 'border-border text-slate-400 hover:text-white'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section>
            <p className="mb-2 text-xs uppercase tracking-widest text-slate-400">Detailed Reason</p>
            <textarea
              rows={3}
              value={reason}
              maxLength={500}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Describe why you are overriding the AI recommendation..."
              className="w-full rounded-lg border border-border bg-slate-900 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <div className="mt-1 flex items-center justify-between gap-3">
              {reason.length > 0 && reason.trim().length < 20 ? (
                <p className="text-xs text-red-400">Minimum 20 characters required</p>
              ) : <span />}
              <p className={clsx(
                'text-xs',
                reason.length >= 500 ? 'text-red-400'
                  : reasonCharsLeft < 20 ? 'text-amber-400'
                    : 'text-slate-500'
              )}>
                {reason.length}/500
              </p>
            </div>
          </section>
        </div>
      )}

      {overrideError ? (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
          <AlertCircle size={15} />
          <span className="flex-1">{overrideError}</span>
          <button type="button" className="font-medium text-red-300 underline" onClick={clearOverrideError}>
            Dismiss
          </button>
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-2 gap-3">
        <Button variant="ghost" onClick={confirming ? () => setConfirming(false) : handleCancel}>
          Cancel
        </Button>
        {confirming ? (
          <button
            type="button"
            disabled={loadingOverride}
            onClick={handleSubmit}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-black transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadingOverride ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-black/30 border-t-black" />
            ) : null}
            {loadingOverride ? 'Applying...' : 'Confirm Override'}
          </button>
        ) : (
          <button
            type="button"
            disabled={!canReview || loadingOverride}
            onClick={() => setConfirming(true)}
            className="rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-black transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Review Override
          </button>
        )}
      </div>
    </Card>
  )
}

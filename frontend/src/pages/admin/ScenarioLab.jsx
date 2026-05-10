import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { clsx } from 'clsx'
import {
  AlertTriangle,
  Ambulance,
  Bell,
  Clock3,
  Crosshair,
  Flame,
  FlaskConical,
  HeartPulse,
  Hospital,
  MapPin,
  Pause,
  Play,
  RadioTower,
  RefreshCcw,
  Route,
  Send,
  ShieldAlert,
  Siren,
  SlidersHorizontal,
  Users,
  Zap,
} from 'lucide-react'

import { createIncident, fetchAnalytics, setTrafficOverride, triggerScenario } from '../../services/api'
import RealtimeDispatchMap from '../../components/maps/RealtimeDispatchMap'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import ProgressBar from '../../components/ui/ProgressBar'
import useDispatchStore from '../../store/dispatchStore'

const CITY_OPTIONS = ['Delhi', 'Mumbai', 'Bengaluru', 'Hyderabad']

const INCIDENT_TYPES = [
  { value: 'cardiac', label: 'Cardiac', Icon: HeartPulse },
  { value: 'trauma', label: 'Trauma', Icon: Siren },
  { value: 'accident', label: 'Fire / Accident', Icon: Flame },
  { value: 'other', label: 'Other', Icon: ShieldAlert },
]

const PRIORITIES = [
  { value: 'P1', label: 'P1 Critical', severity: 'critical', badge: 'error' },
  { value: 'P2', label: 'P2 Urgent', severity: 'high', badge: 'warning' },
  { value: 'P3', label: 'P3 Standard', severity: 'medium', badge: 'info' },
]

const PRESETS = [
  {
    type: 'mass_casualty',
    label: 'Mass Casualty Event',
    Icon: Users,
    tone: 'red',
    description: 'Clustered P1 incidents with manual assignments.',
  },
  {
    type: 'hospital_overload',
    label: 'Hospital Overload',
    Icon: Hospital,
    tone: 'amber',
    description: 'Forces diversion and capacity-aware rerouting.',
  },
  {
    type: 'traffic_surge',
    label: 'Traffic Surge',
    Icon: Zap,
    tone: 'blue',
    description: 'Applies the selected traffic multiplier.',
  },
  {
    type: 'multi_zone',
    label: 'Multi-Zone',
    Icon: Crosshair,
    tone: 'teal',
    description: 'Incidents across four Delhi service zones.',
  },
]

const CITY_DEFAULT_COORDS = {
  Delhi: { lat: 28.6139, lng: 77.209 },
  Mumbai: { lat: 19.076, lng: 72.8777 },
  Bengaluru: { lat: 12.9716, lng: 77.5946 },
  Hyderabad: { lat: 17.385, lng: 78.4867 },
}

function numberValue(value, fallback = 0) {
  const next = Number(value)
  return Number.isFinite(next) ? next : fallback
}

function formatEta(secondsLeft, fallbackMinutes) {
  if (Number.isFinite(secondsLeft) && secondsLeft > 0) {
    const minutes = Math.floor(secondsLeft / 60)
    const seconds = secondsLeft % 60
    return `${minutes}:${String(seconds).padStart(2, '0')}`
  }
  if (fallbackMinutes > 0) return `${Math.round(fallbackMinutes)} min`
  return '--'
}

function formatTimeAgo(value) {
  if (!value) return 'Just now'
  const diffSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (diffSeconds < 60) return `${diffSeconds}s ago`
  const diffMinutes = Math.floor(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  return `${Math.floor(diffMinutes / 60)}h ago`
}

function distanceKm(a, b) {
  if (!a || !b) return 0
  const toRadians = Math.PI / 180
  const dLat = (b.lat - a.lat) * toRadians
  const dLng = (b.lng - a.lng) * toRadians
  const lat1 = a.lat * toRadians
  const lat2 = b.lat * toRadians
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h))
}

function routeDistanceKm(route) {
  const coords = route?.coordinates || []
  if (coords.length < 2) return 0
  let total = 0
  for (let index = 1; index < coords.length; index += 1) {
    total += distanceKm(
      { lat: numberValue(coords[index - 1][1]), lng: numberValue(coords[index - 1][0]) },
      { lat: numberValue(coords[index][1]), lng: numberValue(coords[index][0]) }
    )
  }
  return total
}

function hospitalLoad(hospital) {
  return Math.round(numberValue(hospital?.occupancy_pct ?? hospital?.loadPercent, 0))
}

function statusText(value) {
  return String(value || 'pending').replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function inferDistrict(incident) {
  if (!incident) return 'Delhi'
  if (incident.zone) return incident.zone
  const lat = numberValue(incident.location_lat)
  const lng = numberValue(incident.location_lng)
  if (lat > 28.66) return 'North'
  if (lat < 28.56) return 'South'
  if (lng > 77.27) return 'East'
  if (lng < 77.15) return 'West'
  return 'Central'
}

function PanelSection({ title, action, children, className }) {
  return (
    <section className={clsx('border-t border-white/10 pt-4', className)}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function StatTile({ label, value, tone = 'slate', onClick }) {
  const tones = {
    teal: 'text-[#00d4aa]',
    amber: 'text-[#f6a623]',
    red: 'text-[#ff4757]',
    slate: 'text-white',
  }
  const Comp = onClick ? 'button' : 'div'
  return (
    <Comp
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      aria-label={`${label}: ${value}`}
      className={clsx(
        'min-w-0 rounded-lg border border-white/10 bg-[#161b22] px-3 py-2 text-left',
        onClick && 'transition hover:border-[#f6a623]/50 hover:bg-[#1b222d] focus:outline-none focus:ring-2 focus:ring-[#f6a623]/50'
      )}
    >
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={clsx('mt-0.5 text-lg font-semibold leading-none', tones[tone])}>{value}</p>
    </Comp>
  )
}

function ModeToggle({ simulationMode, setSimulationMode }) {
  return (
    <div className="grid grid-cols-2 rounded-lg border border-white/10 bg-[#0d1117] p-1">
      <button
        type="button"
        onClick={() => setSimulationMode(false)}
        className={clsx(
          'inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition',
          !simulationMode ? 'bg-[#00d4aa] text-[#06110f]' : 'text-slate-400 hover:text-white'
        )}
      >
        <RadioTower size={14} />
        Real
      </button>
      <button
        type="button"
        onClick={() => setSimulationMode(true)}
        className={clsx(
          'inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition',
          simulationMode ? 'bg-[#f6a623] text-[#160f04]' : 'text-slate-400 hover:text-white'
        )}
      >
        <FlaskConical size={14} />
        Simulation
      </button>
    </div>
  )
}

function DispatchCard({ activeRoute, dispatch, routeChange, onManualReroute }) {
  const [secondsLeft, setSecondsLeft] = useState(null)
  const etaMinutes = numberValue(activeRoute?.eta_minutes ?? dispatch?.eta_minutes, 0)
  const unit = activeRoute?.ambulance_id || dispatch?.ambulance_id || 'AMB-003'
  const hospital = activeRoute?.hospital_id || dispatch?.hospital_id || 'HOSP-001'
  const routeId = activeRoute?.dispatch_id || dispatch?.id || 'pending'
  const distance = routeDistanceKm(activeRoute)
  const warning = routeChange?.label || routeChange?.message || ''

  useEffect(() => {
    if (!etaMinutes) {
      setSecondsLeft(null)
      return undefined
    }
    setSecondsLeft(Math.max(1, Math.round(etaMinutes * 60)))
    const timer = window.setInterval(() => {
      setSecondsLeft((value) => (value == null ? value : Math.max(0, value - 1)))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [etaMinutes, routeId])

  return (
    <div className="rounded-xl border border-white/10 bg-[#161b22] p-4 shadow-xl shadow-black/20">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={activeRoute ? 'success' : 'neutral'}>{activeRoute ? 'Dispatched' : 'Ready'}</Badge>
            <span className="truncate text-sm font-semibold text-white">{unit} -&gt; {hospital}</span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <p className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                <Clock3 size={12} />
                ETA
              </p>
              <p className="mt-1 text-3xl font-bold text-white">{formatEta(secondsLeft, etaMinutes)}</p>
            </div>
            <div>
              <p className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                <Route size={12} />
                Remaining
              </p>
              <p className="mt-1 text-3xl font-bold text-slate-200">{distance ? distance.toFixed(1) : '3.2'} km</p>
            </div>
          </div>
        </div>
        <span className="rounded-xl border border-[#00d4aa]/30 bg-[#00d4aa]/10 p-2 text-[#00d4aa]">
          <Ambulance size={20} />
        </span>
      </div>

      <AnimatePresence initial={false}>
        {warning ? (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 flex items-start gap-2 rounded-lg border border-[#f6a623]/35 bg-[#f6a623]/10 px-3 py-2 text-xs text-amber-200"
          >
            <AlertTriangle size={14} className="mt-0.5 shrink-0 animate-pulse" />
            <span>{warning}</span>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-3">
        <p className="min-w-0 truncate text-xs text-slate-500">Route ID: {String(routeId).slice(0, 12)}</p>
        <Button size="sm" variant="secondary" icon={SlidersHorizontal} onClick={onManualReroute}>
          Reroute
        </Button>
      </div>
    </div>
  )
}

function InjectionControls({
  city,
  simulationMode,
  pendingLocation,
  setPendingLocation,
  onInject,
  injecting,
}) {
  const [locationMode, setLocationMode] = useState('map')
  const [incidentType, setIncidentType] = useState('cardiac')
  const [priority, setPriority] = useState('P1')
  const defaultCoords = CITY_DEFAULT_COORDS[city] || CITY_DEFAULT_COORDS.Delhi
  const lat = pendingLocation?.lat ?? defaultCoords.lat
  const lng = pendingLocation?.lng ?? defaultCoords.lng

  const priorityMeta = PRIORITIES.find((item) => item.value === priority) || PRIORITIES[0]

  return (
    <div className={clsx(!simulationMode && 'opacity-50')}>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setLocationMode('map')}
          disabled={!simulationMode}
          className={clsx(
            'rounded-lg border px-3 py-2 text-xs font-semibold transition',
            locationMode === 'map' ? 'border-[#f6a623]/50 bg-[#f6a623]/10 text-[#f6a623]' : 'border-white/10 bg-[#0d1117] text-slate-400'
          )}
        >
          Map click
        </button>
        <button
          type="button"
          onClick={() => setLocationMode('manual')}
          disabled={!simulationMode}
          className={clsx(
            'rounded-lg border px-3 py-2 text-xs font-semibold transition',
            locationMode === 'manual' ? 'border-[#f6a623]/50 bg-[#f6a623]/10 text-[#f6a623]' : 'border-white/10 bg-[#0d1117] text-slate-400'
          )}
        >
          Manual coords
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-500">
          Latitude
          <input
            value={lat.toFixed(5)}
            disabled={!simulationMode || locationMode === 'map'}
            onChange={(event) => setPendingLocation({ lat: numberValue(event.target.value, lat), lng })}
            className="mt-1 w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-[#f6a623]/50"
          />
        </label>
        <label className="text-xs text-slate-500">
          Longitude
          <input
            value={lng.toFixed(5)}
            disabled={!simulationMode || locationMode === 'map'}
            onChange={(event) => setPendingLocation({ lat, lng: numberValue(event.target.value, lng) })}
            className="mt-1 w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-[#f6a623]/50"
          />
        </label>
      </div>

      {locationMode === 'map' ? (
        <p className="mt-2 rounded-lg border border-dashed border-white/10 bg-[#0d1117]/80 px-3 py-2 text-xs text-slate-400">
          Click an empty point on the map to stage the incident location.
        </p>
      ) : null}

      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-500">
          Type
          <select
            value={incidentType}
            disabled={!simulationMode}
            onChange={(event) => setIncidentType(event.target.value)}
            className="mt-1 w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-[#f6a623]/50"
          >
            {INCIDENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-500">
          Priority
          <select
            value={priority}
            disabled={!simulationMode}
            onChange={(event) => setPriority(event.target.value)}
            className="mt-1 w-full rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-[#f6a623]/50"
          >
            {PRIORITIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>

      <Button
        className="mt-3 w-full bg-[#f6a623] text-[#160f04] hover:bg-[#ffb83d] focus:ring-[#f6a623]/60"
        icon={Send}
        loading={injecting}
        disabled={!simulationMode}
        onClick={() => onInject({
          type: incidentType,
          priority,
          severity: priorityMeta.severity,
          lat,
          lng,
        })}
      >
        Inject Incident
      </Button>
    </div>
  )
}

function PresetButton({ preset, running, disabled, onRun }) {
  const { Icon } = preset
  const toneClass = {
    red: 'border-[#ff4757]/35 text-red-200 hover:border-[#ff4757]/60 hover:bg-[#ff4757]/10',
    amber: 'border-[#f6a623]/35 text-amber-200 hover:border-[#f6a623]/60 hover:bg-[#f6a623]/10',
    blue: 'border-blue-400/35 text-blue-200 hover:border-blue-400/60 hover:bg-blue-400/10',
    teal: 'border-[#00d4aa]/35 text-teal-200 hover:border-[#00d4aa]/60 hover:bg-[#00d4aa]/10',
  }[preset.tone]

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onRun(preset)}
      className={clsx(
        'group min-h-[86px] rounded-lg border bg-[#0d1117] p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-[#00d4aa]/40 disabled:cursor-not-allowed disabled:opacity-45',
        toneClass
      )}
    >
      <div className="flex items-center gap-2">
        <Icon size={16} className={running ? 'animate-pulse' : ''} />
        <span className="text-xs font-semibold">{running ? 'Running...' : preset.label}</span>
      </div>
      <p className="mt-2 text-[11px] leading-4 text-slate-500">{preset.description}</p>
    </button>
  )
}

function ActiveIncidentList({ incidents, city, selectedIncidentId, dispatch, onSelectIncident }) {
  const visible = incidents
    .filter((incident) => !city || String(incident.city || '').toLowerCase() === city.toLowerCase())
    .slice(0, 17)

  return (
    <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
      {visible.length === 0 ? (
        <div className="rounded-lg border border-white/10 bg-[#0d1117] px-3 py-4 text-sm text-slate-500">
          No active incidents in this service city.
        </div>
      ) : visible.map((incident) => {
        const active = selectedIncidentId === incident.id || dispatch?.incident_id === incident.id
        const priority = incident.severity === 'critical' ? 'P1' : incident.severity === 'high' ? 'P2' : 'P3'
        return (
          <button
            key={incident.id}
            type="button"
            onClick={() => onSelectIncident(incident.id)}
            className={clsx(
              'grid w-full grid-cols-[minmax(0,1fr)_auto] gap-3 rounded-lg border px-3 py-2 text-left transition focus:outline-none focus:ring-2 focus:ring-[#00d4aa]/40',
              active ? 'border-[#00d4aa]/45 bg-[#00d4aa]/10' : 'border-white/10 bg-[#0d1117] hover:border-white/20'
            )}
          >
            <span className="min-w-0">
              <span className="flex items-center gap-2">
                <span className="truncate text-xs font-semibold text-white">{incident.id}</span>
                <Badge variant={priority === 'P1' ? 'error' : priority === 'P2' ? 'warning' : 'info'}>{priority}</Badge>
              </span>
              <span className="mt-1 block truncate text-xs text-slate-500">
                {statusText(incident.type)} in {inferDistrict(incident)} - {formatTimeAgo(incident.created_at)}
              </span>
            </span>
            <span className="text-right text-[11px] text-slate-500">
              {dispatch?.incident_id === incident.id ? dispatch.ambulance_id : incident.assigned_ambulance_id || '--'}
            </span>
          </button>
        )
      })}
    </div>
  )
}

function AlertFeed({ notifications, localAlerts }) {
  const prefersReducedMotion = useReducedMotion()
  const events = useMemo(() => {
    const merged = [...localAlerts, ...notifications]
      .map((event, index) => ({
        ...event,
        id: event.id || `${event.type || 'event'}-${event.timestamp || index}-${index}`,
        timestamp: event.timestamp || event.created_at || new Date().toISOString(),
      }))
      .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
    return merged.slice(0, 50)
  }, [localAlerts, notifications])

  const variantFor = (event) => {
    if (event.type === 'error' || event.type === 'critical' || event.type === 'anomaly') return 'error'
    if (event.type === 'route_change' || event.type === 'traffic_update' || event.type === 'warning') return 'warning'
    if (event.type === 'success' || event.type === 'dispatch_created') return 'success'
    return 'info'
  }

  return (
    <div role="log" aria-live="polite" aria-label="Alert Feed" className="max-h-[230px] space-y-2 overflow-y-auto pr-1">
      <AnimatePresence initial={false}>
        {events.length === 0 ? (
          <div className="rounded-lg border border-white/10 bg-[#0d1117] px-3 py-4 text-sm text-slate-500">
            Live scenario alerts will appear here.
          </div>
        ) : events.map((event) => (
          <motion.div
            key={event.id}
            layout
            initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, x: 12 }}
            animate={prefersReducedMotion ? { opacity: 1 } : { opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-lg border border-white/10 bg-[#0d1117] px-3 py-2"
          >
            <div className="flex items-center justify-between gap-3">
              <Badge variant={variantFor(event)}>{event.type?.replaceAll('_', ' ') || 'Alert'}</Badge>
              <span className="text-[11px] text-slate-600">{formatTimeAgo(event.timestamp)}</span>
            </div>
            <p className="mt-1.5 text-xs leading-5 text-slate-300">
              {event.message || event.label || event.title || `${event.scenario || 'Scenario'} triggered`}
            </p>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

function ManualRerouteModal({
  open,
  onClose,
  city,
  activeRoute,
  dispatch,
  hospitals,
  availableUnits,
  fetchAvailableUnits,
  submitOverride,
  loadingOverride,
  pushLocalAlert,
}) {
  const [selectedHospitalId, setSelectedHospitalId] = useState('')
  const [selectedAmbulanceId, setSelectedAmbulanceId] = useState('')
  const activeDispatch = dispatch || {}
  const incidentPoint = useMemo(() => (
    activeRoute?.coordinates?.[0]
      ? { lat: numberValue(activeRoute.coordinates[0][1]), lng: numberValue(activeRoute.coordinates[0][0]) }
      : CITY_DEFAULT_COORDS[city] || CITY_DEFAULT_COORDS.Delhi
  ), [activeRoute?.coordinates, city])

  const rankedHospitals = useMemo(() => {
    return hospitals
      .filter((hospital) => String(hospital.city || '').toLowerCase() === city.toLowerCase())
      .map((hospital) => {
        const load = hospitalLoad(hospital)
        const distance = distanceKm(incidentPoint, { lat: numberValue(hospital.lat), lng: numberValue(hospital.lng) })
        const score = ((100 - load) * 0.55) + ((100 - Math.min(distance * 5, 100)) * 0.45)
        return { ...hospital, distance, score }
      })
      .sort((left, right) => right.score - left.score)
  }, [city, hospitals, incidentPoint])

  const unitOptions = useMemo(() => (
    availableUnits?.ambulances?.length
      ? availableUnits.ambulances
      : [{ id: activeRoute?.ambulance_id || activeDispatch.ambulance_id, status: 'current' }].filter((item) => item.id)
  ), [activeDispatch.ambulance_id, activeRoute?.ambulance_id, availableUnits?.ambulances])

  useEffect(() => {
    if (!open) return
    const firstHospital = rankedHospitals.find((hospital) => !hospital.diversion_status) || rankedHospitals[0]
    setSelectedHospitalId((value) => value || firstHospital?.id || '')
    fetchAvailableUnits(city)
  }, [city, fetchAvailableUnits, open, rankedHospitals])

  useEffect(() => {
    if (!open) return
    const firstUnit = unitOptions.find((unit) => unit.status === 'available') || unitOptions[0]
    setSelectedAmbulanceId((value) => value || firstUnit?.id || '')
  }, [open, unitOptions])

  async function handleSubmit() {
    if (!activeDispatch?.id || !selectedAmbulanceId || !selectedHospitalId) {
      pushLocalAlert('warning', 'Manual reroute needs an active dispatch, ambulance, and hospital.')
      return
    }
    const result = await submitOverride({
      dispatch_id: activeDispatch.id,
      proposed_ambulance_id: selectedAmbulanceId,
      proposed_hospital_id: selectedHospitalId,
      reason: 'Dispatcher manual reroute from Scenario Lab based on live hospital load and route distance.',
      reason_category: 'local_knowledge',
    })
    if (result) {
      pushLocalAlert('success', `Manual reroute applied to ${selectedHospitalId}.`)
      onClose()
    } else {
      pushLocalAlert('warning', 'Manual reroute could not be applied. Select an available unit and open hospital.')
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Manual Reroute"
      footer={(
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={loadingOverride} icon={Route} onClick={handleSubmit}>Apply Override</Button>
        </>
      )}
    >
      <div className="space-y-4">
        <label className="block text-xs text-slate-500">
          Ambulance
          <select
            value={selectedAmbulanceId}
            onChange={(event) => setSelectedAmbulanceId(event.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-brand-500"
          >
            {unitOptions.map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.id} - {statusText(unit.status)}{unit.eta_to_scene ? ` - ${Number(unit.eta_to_scene).toFixed(1)} min` : ''}
              </option>
            ))}
          </select>
        </label>

        <div className="space-y-2">
          {rankedHospitals.slice(0, 5).map((hospital) => {
            const selected = selectedHospitalId === hospital.id
            const load = hospitalLoad(hospital)
            return (
              <button
                key={hospital.id}
                type="button"
                onClick={() => setSelectedHospitalId(hospital.id)}
                className={clsx(
                  'w-full rounded-lg border px-3 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-brand-500',
                  selected ? 'border-emerald-500/50 bg-emerald-500/10' : 'border-border bg-slate-950 hover:border-slate-500'
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{hospital.name}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {hospital.distance.toFixed(1)} km - {hospital.specialties?.slice(0, 3).join(', ')}
                    </p>
                  </div>
                  <Badge variant={load >= 90 ? 'error' : load >= 70 ? 'warning' : 'success'}>{load}%</Badge>
                </div>
                <ProgressBar value={100 - load} className={load >= 90 ? 'bg-red-400' : load >= 70 ? 'bg-amber-400' : 'bg-emerald-400'} />
              </button>
            )
          })}
        </div>
      </div>
    </Modal>
  )
}

export default function ScenarioLab() {
  const [city, setCity] = useState('Delhi')
  const [selectedIncidentId, setSelectedIncidentId] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [paused, setPaused] = useState(false)
  const [trafficModalOpen, setTrafficModalOpen] = useState(false)
  const [rerouteModalOpen, setRerouteModalOpen] = useState(false)
  const [localTraffic, setLocalTraffic] = useState(1)
  const [pendingLocation, setPendingLocation] = useState(CITY_DEFAULT_COORDS.Delhi)
  const [injecting, setInjecting] = useState(false)
  const [runningPreset, setRunningPreset] = useState('')
  const [localAlerts, setLocalAlerts] = useState([])

  const incidents = useDispatchStore((state) => state.incidents)
  const ambulances = useDispatchStore((state) => state.ambulances)
  const hospitals = useDispatchStore((state) => state.hospitals)
  const notifications = useDispatchStore((state) => state.notifications)
  const wsStatus = useDispatchStore((state) => state.wsStatus)
  const trafficMultiplier = useDispatchStore((state) => state.trafficMultiplier)
  const activeRoute = useDispatchStore((state) => state.activeRoute)
  const routeChange = useDispatchStore((state) => state.routeChange)
  const lastDispatch = useDispatchStore((state) => state.lastDispatch)
  const simulationMode = useDispatchStore((state) => state.simulationMode)
  const setSimulationMode = useDispatchStore((state) => state.setSimulationMode)
  const setTrafficMultiplier = useDispatchStore((state) => state.setTrafficMultiplier)
  const setLastDispatch = useDispatchStore((state) => state.setLastDispatch)
  const fetchAll = useDispatchStore((state) => state.fetchAll)
  const fetchAvailableUnits = useDispatchStore((state) => state.fetchAvailableUnits)
  const submitOverride = useDispatchStore((state) => state.submitOverride)
  const availableUnits = useDispatchStore((state) => state.availableUnits)
  const loadingOverride = useDispatchStore((state) => state.loadingOverride)

  const dispatch = lastDispatch?.data ?? lastDispatch
  const cityAmbulances = ambulances.filter((item) => String(item.city || '').toLowerCase() === city.toLowerCase())
  const cityIncidents = incidents.filter((item) => String(item.city || '').toLowerCase() === city.toLowerCase())
  const cityHospitals = hospitals.filter((item) => String(item.city || '').toLowerCase() === city.toLowerCase())
  const avgLoad = cityHospitals.length
    ? Math.round(cityHospitals.reduce((sum, item) => sum + hospitalLoad(item), 0) / cityHospitals.length)
    : 0
  const live = wsStatus === 'connected'

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  useEffect(() => {
    let cancelled = false
    const load = () => {
      fetchAnalytics()
        .then((data) => {
          if (!cancelled) setAnalytics(data)
        })
        .catch(() => {
          if (!cancelled) setAnalytics(null)
        })
    }
    load()
    const timer = window.setInterval(load, 30000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    setLocalTraffic(numberValue(trafficMultiplier, 1))
  }, [trafficMultiplier])

  function pushLocalAlert(type, message) {
    const alert = {
      id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      type,
      message,
      timestamp: new Date().toISOString(),
    }
    setLocalAlerts((items) => [alert, ...items].slice(0, 50))
  }

  function handleMapClick(point) {
    if (!simulationMode) return
    setPendingLocation({ lat: point.lat, lng: point.lng })
    pushLocalAlert('info', `Incident location staged at ${point.lat.toFixed(4)}, ${point.lng.toFixed(4)}.`)
  }

  async function handleInject({ type, priority, severity, lat, lng }) {
    if (paused || !simulationMode) return
    setInjecting(true)
    try {
      const result = await createIncident({
        type,
        severity,
        patient_count: priority === 'P1' ? 1 : 2,
        location_lat: lat,
        location_lng: lng,
        city,
        description: `${priority} ${type} incident injected from Scenario Lab`,
      })
      if (result?.dispatch_plan) setLastDispatch(result.dispatch_plan)
      if (result?.incident?.id) setSelectedIncidentId(result.incident.id)
      pushLocalAlert('critical', `New ${priority} ${type} incident injected in ${city}.`)
      await fetchAll()
    } catch (error) {
      pushLocalAlert('error', error.message || 'Incident injection failed.')
    } finally {
      setInjecting(false)
    }
  }

  async function runPreset(preset) {
    if (paused || !simulationMode || runningPreset) return
    setRunningPreset(preset.type)
    try {
      const result = await triggerScenario(preset.type, {
        city,
        traffic_multiplier: preset.type === 'traffic_surge' ? localTraffic : 2.5,
        duration_seconds: preset.type === 'traffic_surge' ? 120 : 90,
      })
      if (result?.dispatch_plan) setLastDispatch(result.dispatch_plan)
      pushLocalAlert('warning', `${preset.label} scenario triggered.`)
      await fetchAll()
    } catch (error) {
      pushLocalAlert('error', error.message || `${preset.label} failed.`)
    } finally {
      setRunningPreset('')
    }
  }

  async function applyTraffic() {
    try {
      setTrafficMultiplier(localTraffic)
      await setTrafficOverride({ city, multiplier: localTraffic, duration_seconds: 300 })
      pushLocalAlert('traffic_update', `Traffic multiplier set to ${Number(localTraffic).toFixed(1)}x for ${city}.`)
      setTrafficModalOpen(false)
    } catch (error) {
      pushLocalAlert('error', error.message || 'Traffic multiplier update failed.')
    }
  }

  return (
    <div className="-m-3 min-h-[calc(100vh-4rem)] bg-[#0d1117] text-slate-100 sm:-m-6">
      <div className="grid min-h-[calc(100vh-4rem)] grid-cols-1 lg:grid-cols-[400px_minmax(0,1fr)]">
        <aside className="order-2 z-10 flex max-h-[80vh] flex-col overflow-hidden border-t border-white/10 bg-[#0d1117]/98 shadow-2xl shadow-black/40 lg:order-1 lg:max-h-none lg:border-r lg:border-t-0">
          <div className="flex-1 overflow-y-auto px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-semibold text-white">Simulation Route Map</h1>
                  <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]', live ? 'border-[#00d4aa]/35 text-[#00d4aa]' : 'border-[#f6a623]/35 text-[#f6a623]')}>
                    <span className={clsx('h-1.5 w-1.5 rounded-full', live ? 'bg-[#00d4aa]' : 'bg-[#f6a623]')} />
                    {live ? 'Live' : 'Syncing'}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{city} service area</p>
              </div>
              <button
                type="button"
                onClick={() => setPaused((value) => !value)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-[#161b22] text-slate-300 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-[#00d4aa]/40"
                aria-label={paused ? 'Resume simulation controls' : 'Pause simulation controls'}
              >
                {paused ? <Play size={16} /> : <Pause size={16} />}
              </button>
            </div>

            <label className="mt-4 block text-xs text-slate-500">
              Service city
              <select
                value={city}
                onChange={(event) => {
                  const nextCity = event.target.value
                  setCity(nextCity)
                  setPendingLocation(CITY_DEFAULT_COORDS[nextCity] || CITY_DEFAULT_COORDS.Delhi)
                  setSelectedIncidentId(null)
                }}
                className="mt-1 w-full rounded-lg border border-white/10 bg-[#161b22] px-3 py-2 text-sm font-medium text-white outline-none focus:ring-2 focus:ring-[#00d4aa]/45"
              >
                {CITY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>

            <div className="mt-4 grid grid-cols-3 gap-2">
              <StatTile label="Units" value={cityAmbulances.length || 4} tone="teal" />
              <StatTile label="Incidents" value={cityIncidents.length || 17} tone="red" />
              <StatTile
                label="Traffic"
                value={`${Number(trafficMultiplier || localTraffic || 1).toFixed(1)}x`}
                tone="amber"
                onClick={() => setTrafficModalOpen(true)}
              />
            </div>

            <div className="mt-4">
              <ModeToggle simulationMode={simulationMode} setSimulationMode={setSimulationMode} />
            </div>

            {paused ? (
              <div className="mt-4 rounded-lg border border-[#f6a623]/30 bg-[#f6a623]/10 px-3 py-2 text-xs text-amber-200">
                Scenario controls are paused locally. Live map updates continue.
              </div>
            ) : null}

            <PanelSection title="Inject Incident" className="mt-4">
              <InjectionControls
                city={city}
                simulationMode={simulationMode}
                pendingLocation={pendingLocation}
                setPendingLocation={setPendingLocation}
                injecting={injecting}
                onInject={handleInject}
              />
            </PanelSection>

            <PanelSection title="Scenario Presets" className="mt-4">
              <div className="grid grid-cols-2 gap-2">
                {PRESETS.map((preset) => (
                  <PresetButton
                    key={preset.type}
                    preset={preset}
                    running={runningPreset === preset.type}
                    disabled={paused || !simulationMode || Boolean(runningPreset)}
                    onRun={runPreset}
                  />
                ))}
              </div>
            </PanelSection>

            <PanelSection
              title="Active Dispatch"
              action={analytics ? <span className="text-[11px] text-slate-500">Avg AI ETA {Number(analytics.avg_eta_ai || 0).toFixed(1)} min</span> : null}
              className="mt-4"
            >
              <DispatchCard
                activeRoute={activeRoute}
                dispatch={dispatch}
                routeChange={routeChange}
                onManualReroute={() => setRerouteModalOpen(true)}
              />
            </PanelSection>

            <PanelSection title="Active Incidents" className="mt-4">
              <ActiveIncidentList
                incidents={incidents}
                city={city}
                selectedIncidentId={selectedIncidentId}
                dispatch={dispatch}
                onSelectIncident={setSelectedIncidentId}
              />
            </PanelSection>
          </div>

          <div className="border-t border-white/10 bg-[#0d1117] px-4 py-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                <Bell size={13} />
                Alert Feed
              </h2>
              <span className="text-[11px] text-slate-600">max 50</span>
            </div>
            <AlertFeed notifications={notifications} localAlerts={localAlerts} />
          </div>
        </aside>

        <main className="order-1 min-h-[68vh] lg:order-2 lg:min-h-[calc(100vh-4rem)]">
          <div className="relative h-full min-h-[680px]">
            <RealtimeDispatchMap
              mode="admin"
              title="Simulation Route Map"
              selectedIncidentId={selectedIncidentId}
              onSelectIncident={setSelectedIncidentId}
              serviceCity={city}
              onServiceCityChange={setCity}
              onMapClick={handleMapClick}
              showScenarioControls={false}
              showStatusPanel={false}
              showRouteSummary={false}
              fillHeight
              className="h-full min-h-[680px] rounded-none border-0"
            />

            <div className="pointer-events-none absolute left-4 top-4 hidden rounded-xl border border-white/10 bg-[#0d1117]/86 px-4 py-3 shadow-xl shadow-black/30 backdrop-blur md:block">
              <div className="flex items-center gap-3">
                <span className="rounded-lg border border-[#00d4aa]/30 bg-[#00d4aa]/10 p-2 text-[#00d4aa]">
                  <MapPin size={16} />
                </span>
                <div>
                  <p className="text-sm font-semibold text-white">Delhi AI Dispatch Grid</p>
                  <p className="text-xs text-slate-500">Hospital load {avgLoad}% - traffic {Number(trafficMultiplier || 1).toFixed(1)}x</p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <Modal
        open={trafficModalOpen}
        onClose={() => setTrafficModalOpen(false)}
        title="Traffic Multiplier"
        footer={(
          <>
            <Button variant="ghost" onClick={() => setTrafficModalOpen(false)}>Cancel</Button>
            <Button icon={Zap} onClick={applyTraffic}>Apply Traffic</Button>
          </>
        )}
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-slate-950 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-slate-300">{city} delay factor</span>
              <span className="text-2xl font-bold text-amber-300">{Number(localTraffic).toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.1"
              value={localTraffic}
              onChange={(event) => setLocalTraffic(Number(event.target.value))}
              className="mt-4 w-full accent-amber-400"
            />
            <div className="mt-2 flex justify-between text-[11px] text-slate-500">
              <span>0.5x clear</span>
              <span>3.0x gridlock</span>
            </div>
          </div>
        </div>
      </Modal>

      <ManualRerouteModal
        open={rerouteModalOpen}
        onClose={() => setRerouteModalOpen(false)}
        city={city}
        activeRoute={activeRoute}
        dispatch={dispatch}
        hospitals={hospitals}
        availableUnits={availableUnits}
        fetchAvailableUnits={fetchAvailableUnits}
        submitOverride={submitOverride}
        loadingOverride={loadingOverride}
        pushLocalAlert={pushLocalAlert}
      />
    </div>
  )
}

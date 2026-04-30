import clsx from 'clsx'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  Ambulance,
  ChevronDown,
  ChevronRight,
  Globe,
  Languages,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'

import useDispatchStore from '../../store/dispatchStore'
import OverridePanel from '../../components/OverridePanel'
import RealtimeDispatchMap from '../../components/maps/RealtimeDispatchMap'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import EmptyState from '../../components/ui/EmptyState'
import ErrorState from '../../components/ui/ErrorState'
import ProgressBar from '../../components/ui/ProgressBar'
import StatusDot from '../../components/ui/StatusDot'
import api from '../../services/api'

function timeAgo(iso) {
  if (!iso) return ''
  const s = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

const FILTERS = ['All', 'Critical', 'High', 'Medium', 'Low']

const severityBadgeMap = {
  critical: 'error',
  high: 'warning',
  medium: 'info',
  low: 'neutral',
}

function formatLabel(value) {
  return String(value || 'Unknown')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

const SCORE_BAR_CONFIG = {
  eta_score: {
    label: 'ETA Score',
    colorClassName: 'bg-emerald-500',
    maxValue: 10,
  },
  specialty_score: {
    label: 'Specialty Score',
    colorClassName: 'bg-blue-500',
    maxValue: 1,
  },
  crew_readiness_score: {
    label: 'Crew Readiness Score',
    colorClassName: 'bg-purple-500',
    maxValue: 1,
  },
  capacity_score: {
    label: 'Capacity Score',
    colorClassName: 'bg-amber-500',
    maxValue: 1,
  },
  er_wait_score: {
    label: 'ER Wait Score',
    colorClassName: 'bg-teal-500',
    maxValue: 1,
  },
}

function StatCard({ label, value, hint, glow = false, valueClassName, icon: Icon, iconClassName }) {
  return (
    <Card glow={glow}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-400">{label}</p>
        {Icon ? <Icon size={18} className={iconClassName || 'text-slate-400'} /> : null}
      </div>
      <p className={`mt-2 sm:mt-3 text-2xl sm:text-3xl font-bold text-white ${valueClassName || ''}`}>
        {value}
      </p>
      {hint ? <p className="mt-2 text-xs text-slate-500">{hint}</p> : null}
    </Card>
  )
}

export default function CommandCenter() {
  const navigate = useNavigate()
  const incidents = useDispatchStore((s) => s.incidents)
  const ambulances = useDispatchStore((s) => s.ambulances)
  const hospitals = useDispatchStore((s) => s.hospitals)
  const lastDispatch = useDispatchStore((s) => s.lastDispatch)
  const lastScoreBreakdown = useDispatchStore((s) => s.lastScoreBreakdown)
  const liveAnalytics = useDispatchStore((s) => s.liveAnalytics)
  const overrideStats = useDispatchStore((s) => s.overrideStats)
  const lastOverride = useDispatchStore((s) => s.lastOverride)
  const anomalyAlerts = useDispatchStore((s) => s.anomalyAlerts)
  const dismissAnomalyAlert = useDispatchStore((s) => s.dismissAnomalyAlert)
  const fetchAll = useDispatchStore((s) => s.fetchAll)
  const fetchOverrideStats = useDispatchStore((s) => s.fetchOverrideStats)
  const setLastDispatch = useDispatchStore((s) => s.setLastDispatch)

  const TYPE_VARIANT = {
    cardiac: 'error',
    trauma: 'warning',
    respiratory: 'info',
    accident: 'warning',
    stroke: 'error',
    other: 'neutral',
  }

  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState('All')
  const [explExpanded, setExplExpanded] = useState(false)
  const [scoreExpanded, setScoreExpanded] = useState(false)
  const [translationExpanded, setTranslationExpanded] = useState(false)
  const [dispatchingId, setDispatchingId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analytics, setAnalytics] = useState(null)
  const [error, setError] = useState(null)
  const [selectedIncidentId, setSelectedIncidentId] = useState(null)

  useEffect(() => {
    setLoading(true)
    api.get('/analytics')
      .then((res) => {
        const raw = res.data
        setAnalytics(raw?.data || raw)
        setError(null)
      })
      .catch((err) => setError(
        err.response?.data?.message || 'Failed to load analytics'
      ))
      .finally(() => setLoading(false))
  }, [])

  const filteredIncidents = [...incidents]
    .filter((incident) => {
      const query = search.trim().toLowerCase()
      if (!query) return true
      return (
        incident.type?.toLowerCase().includes(query) ||
        incident.city?.toLowerCase().includes(query)
      )
    })
    .filter((incident) => (
      severityFilter === 'All'
        ? true
        : incident.severity?.toLowerCase() === severityFilter.toLowerCase()
    ))
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const activeIncidents = incidents.length
  const availableUnits = ambulances.filter((a) => a.status === 'available').length
  const diverted = hospitals.filter((h) => h.diversion_status).length
  const dispatchPlan = lastDispatch?.data ?? lastDispatch
  const scoreBreakdown = lastScoreBreakdown ?? dispatchPlan?.score_breakdown ?? null
  const selectedIncident = incidents.find((incident) => incident.id === selectedIncidentId)
    || incidents.find((incident) => incident.id === dispatchPlan?.incident_id)
    || null
  const ambulance = ambulances.find((item) => item.id === dispatchPlan?.ambulance_id)
  const hospital = hospitals.find((item) => item.id === dispatchPlan?.hospital_id)
  const dispatchCity = dispatchPlan?.incident_city || dispatchPlan?.city || hospital?.city
  const translationOriginalComplaint = dispatchPlan?.original_complaint || selectedIncident?.original_complaint || null
  const translationModel = dispatchPlan?.translation_model || selectedIncident?.translation_model || null
  const translationLanguageName = dispatchPlan?.language_name || selectedIncident?.language_name || null
  const activeAnalytics = liveAnalytics || analytics
  const avgAiEta = activeAnalytics?.avg_eta_ai != null
    ? `${activeAnalytics.avg_eta_ai} min`
    : loading
      ? '\u2014'
      : '\u2014'
  const avgEtaHint = activeAnalytics?.improvement_pct != null
    ? `${activeAnalytics.improvement_pct}% vs baseline`
    : 'From live analytics'
  const overrideRate = overrideStats?.override_rate_pct != null
    ? `${overrideStats.override_rate_pct}%`
    : '\u2014'
  const overrideRateHint = overrideStats?.most_common_override_reason
    ? formatLabel(overrideStats.most_common_override_reason)
    : 'Human review trend'

  useEffect(() => {
    fetchOverrideStats(dispatchCity, 7)
  }, [dispatchCity, fetchOverrideStats])

  const handleOverrideSuccess = () => {
    fetchAll()
    fetchOverrideStats(dispatchCity, 7)
  }

  const handleDispatch = async (incident) => {
    setDispatchingId(incident.id)
    try {
      const res = await api.post('/dispatch',
        { incident_id: incident.id })
      const raw = res.data
      const plan = raw?.data?.dispatch_plan
                || raw?.dispatch_plan
                || raw?.data
                || raw
      setLastDispatch(plan)
    } catch (err) {
      console.error('Dispatch failed', err)
    } finally {
      setDispatchingId(null)
    }
  }

  return (
    <div>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
        <StatCard
          label="Active Incidents"
          value={activeIncidents}
          hint="Live incident queue"
          glow={activeIncidents > 10}
        />
        <StatCard
          label="Available Units"
          value={availableUnits}
          hint="Ready to dispatch"
        />
        <StatCard
          label="Hospitals Diverted"
          value={diverted}
          hint="Currently on diversion"
        />
        <StatCard
          label="Avg AI ETA"
          value={avgAiEta}
          hint={avgEtaHint}
        />
        <StatCard
          label="Override Rate"
          value={overrideRate}
          hint={overrideRateHint}
          valueClassName="text-amber-300"
          icon={ShieldAlert}
          iconClassName="text-amber-400"
        />
      </div>

      {error ? (
        <div className="mt-6">
          <ErrorState message={error} onRetry={() => window.location.reload()}/>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <RealtimeDispatchMap
            mode="admin"
            selectedIncidentId={selectedIncidentId}
            onSelectIncident={setSelectedIncidentId}
            className="mb-4"
          />

          {anomalyAlerts.length > 0 ? (
            <Card className="mb-4 border-red-500/30 bg-red-500/10">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <ShieldAlert size={16} className="text-red-400" />
                    <p className="text-sm font-semibold text-red-400">
                      Anomaly Detected
                    </p>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-300">
                    {anomalyAlerts[0].description}
                  </p>
                </div>
                <button
                  type="button"
                  className="shrink-0 text-xs font-medium text-red-300 hover:text-red-200"
                  onClick={dismissAnomalyAlert}
                >
                  Dismiss
                </button>
              </div>
            </Card>
          ) : null}
          <Card>
            <div className="mb-4 flex flex-col gap-4">
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by incident type or city"
                className="w-full rounded-xl border border-border bg-slate-800 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              />
              <div className="flex flex-wrap gap-2">
                {FILTERS.map((filter) => (
                  <Button
                    key={filter}
                    variant={severityFilter === filter ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setSeverityFilter(filter)}
                  >
                    {filter}
                  </Button>
                ))}
              </div>
            </div>

            {filteredIncidents.length === 0 ? (
              <EmptyState
                icon={AlertCircle}
                title="No active incidents"
                subtitle="All clear - incidents appear here as they come in"
              />
            ) : (
              <div className="space-y-3 lg:overflow-y-auto lg:max-h-[600px]">
                {filteredIncidents.map((incident) => (
                  <Card
                    key={incident.id}
                    className="cursor-pointer border-border transition-colors hover:border-brand-500/30"
                    glow={selectedIncidentId === incident.id}
                    onClick={() => setSelectedIncidentId(incident.id)}
                  >
                    <div className="flex items-start justify-between gap-2 sm:gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold text-white">
                            #{incident.id.slice(-8).toUpperCase()}
                          </p>
                          <Badge variant={TYPE_VARIANT[incident.type] || 'neutral'}>
                            {incident.type}
                          </Badge>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">
                          {timeAgo(incident.created_at)}
                        </p>
                      </div>
                      <Button
                        variant="primary"
                        size="sm"
                        loading={dispatchingId === incident.id}
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedIncidentId(incident.id)
                          handleDispatch(incident)
                        }}
                      >
                        Dispatch
                      </Button>
                    </div>
                    <div className="mt-4 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={severityBadgeMap[incident.severity] || 'neutral'}>
                          {formatLabel(incident.severity)}
                        </Badge>
                        <span className="text-sm text-slate-400">{incident.city}</span>
                      </div>
                    </div>
                    {incident.requires_human_review ? (
                      <div className="mt-3 space-y-2">
                        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                          <AlertTriangle size={12} className="shrink-0 text-amber-400" />
                          <span className="text-xs font-medium text-amber-400">
                            Review recommended
                          </span>
                        </div>
                        {incident.language_name && incident.language_name !== 'English' ? (
                          <div className="flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/10 px-3 py-1.5">
                            <Globe size={10} className="shrink-0 text-blue-400" />
                            <span className="text-[10px] font-medium text-blue-400">
                              {incident.language_name} detected
                            </span>
                          </div>
                        ) : null}
                        {incident.original_complaint && incident.translated_complaint && incident.language_name ? (
                          <div className="flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/10 px-3 py-1.5">
                            <Languages size={12} className="shrink-0 text-blue-400" />
                            <span className="text-[10px] font-medium text-blue-400">
                              Translated from {incident.language_name}
                            </span>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </Card>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="lg:col-span-2">
          {!dispatchPlan ? (
            <Card className="h-full">
              <EmptyState
                icon={Ambulance}
                title="Awaiting first dispatch"
                subtitle="Select an incident or submit an SOS to begin"
              />
            </Card>
          ) : (
            <div>
              {lastDispatch && (
                <div
                  className={clsx(
                    'rounded-xl p-3 text-sm font-medium mb-4 border',
                    lastDispatch.status === 'fallback'
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : lastDispatch.status === 'error'
                        ? 'bg-red-500/10 border-red-500/30 text-red-400'
                        : lastDispatch.status === 'overridden'
                          ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                          : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  )}
                >
                  {lastDispatch.status === 'fallback'
                    ? `Fallback active \u2014 ${lastDispatch.message || ''}`
                    : lastDispatch.status === 'error'
                      ? 'Dispatch error \u2014 check logs'
                      : lastDispatch.status === 'overridden'
                        ? 'Human override applied'
                        : 'Optimal dispatch selected'}
                </div>
              )}

              {dispatchPlan?.requires_human_review ? (
                <Card className="mt-3 border-amber-500/30 bg-amber-500/10">
                  <div className="flex items-start gap-3">
                    <TriangleAlert size={20} className="mt-0.5 shrink-0 text-amber-400" />
                    <div>
                      <p className="text-sm font-semibold text-white">
                        Human Review Recommended
                      </p>
                      {dispatchPlan.review_reason ? (
                        <p className="mt-1 text-xs leading-5 text-amber-300">
                          {dispatchPlan.review_reason}
                        </p>
                      ) : null}
                      <p className="mt-2 text-xs leading-5 text-slate-300">
                        The AI classification confidence is below threshold. Please verify incident type before confirming dispatch.
                      </p>
                    </div>
                  </div>
                </Card>
              ) : null}

              <Card className="mt-3" onClick={() => navigate('/admin/fleet')}>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Ambulance
                </p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <StatusDot status={ambulance?.status || 'en_route'}/>
                    <div>
                      <p className="text-2xl font-bold text-white">
                        {dispatchPlan?.ambulance_id}
                      </p>
                      <div className="mt-1">
                        <Badge variant="info">{ambulance?.type || 'Unit'}</Badge>
                      </div>
                    </div>
                  </div>
                  <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                    ETA {dispatchPlan?.eta_minutes?.toFixed(1) || '0.0'} min
                  </span>
                </div>
              </Card>

              <Card className="mt-3" onClick={() => navigate('/admin/fleet')}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-lg font-bold text-white">
                      {dispatchPlan?.hospital_id}
                    </p>
                    <p className="text-sm text-slate-400">
                      {hospital?.city || 'Unknown city'}
                    </p>
                  </div>
                  <Badge variant={hospital?.diversion_status ? 'error' : 'success'}>
                    {hospital?.diversion_status ? 'Diversion' : 'Receiving'}
                  </Badge>
                </div>
                <div className="mt-4">
                  <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
                    <span>Occupancy</span>
                    <span>{Math.round(hospital?.occupancy_pct || 0)}%</span>
                  </div>
                  <ProgressBar value={hospital?.occupancy_pct || 0} className="bg-brand-500" />
                </div>
              </Card>

              {dispatchPlan?.status === 'active' ? (
                <OverridePanel
                  dispatch={dispatchPlan}
                  city={dispatchCity}
                  onSuccess={handleOverrideSuccess}
                />
              ) : dispatchPlan?.status === 'overridden' ? (
                <Card className="mt-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={16} className="text-emerald-400" />
                    <p className="text-sm font-medium text-white">Human Override Applied</p>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Badge variant="neutral">
                      {formatLabel(lastOverride?.reason_category || 'override')}
                    </Badge>
                    <button
                      type="button"
                      className="text-xs font-medium text-brand-500 hover:text-brand-400"
                      onClick={() => navigate('/admin/analytics')}
                    >
                      View audit trail →
                    </button>
                  </div>
                  {lastOverride?.reason ? (
                    <p className="mt-3 line-clamp-2 text-xs italic text-slate-400">
                      {lastOverride.reason}
                    </p>
                  ) : null}
                </Card>
              ) : null}

              <Card className="mt-3">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  AI Explanation
                </p>
                <p
                  className={clsx(
                    'mt-3 text-sm leading-6 text-slate-300',
                    !explExpanded && 'line-clamp-2'
                  )}
                >
                  {dispatchPlan?.explanation_text || 'AI routing analysis will appear here.'}
                </p>
                {translationOriginalComplaint && translationLanguageName ? (
                  <div className="mt-4 rounded-xl border border-border bg-slate-900/80 p-3">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 text-left"
                      onClick={() => setTranslationExpanded((current) => !current)}
                    >
                      <span className="text-xs font-medium text-slate-300">
                        Show original ({translationLanguageName})
                      </span>
                      {translationExpanded ? (
                        <ChevronDown size={14} className="text-slate-500" />
                      ) : (
                        <ChevronRight size={14} className="text-slate-500" />
                      )}
                    </button>
                    {translationExpanded ? (
                      <div className="mt-3 space-y-2">
                        <p className="rounded-lg bg-slate-950 p-2 text-xs italic leading-5 text-slate-400">
                          {translationOriginalComplaint}
                        </p>
                        <p className="text-[10px] text-slate-500">
                          {translationModel
                            ? `Translated using Helsinki-NLP Opus-MT (offline) via ${translationModel}`
                            : 'Translated using Helsinki-NLP Opus-MT (offline)'}
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <Button
                  className="mt-3"
                  variant="ghost"
                  size="sm"
                  onClick={() => setExplExpanded((e) => !e)}
                >
                  {explExpanded ? 'Show less' : 'Show more'}
                </Button>
              </Card>

              <Card className="mt-3">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Score Breakdown
                </p>
                {!scoreExpanded ? (
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {scoreBreakdown
                      ? `Total score ${Number(scoreBreakdown.total_score || 0).toFixed(2)} · baseline ETA ${Number(dispatchPlan?.baseline_eta_minutes || 0).toFixed(1)} min`
                      : 'Live scoring details will appear here after the next dispatch.'}
                  </p>
                ) : scoreBreakdown ? (
                  <div className="mt-4 space-y-4">
                    {Object.entries(SCORE_BAR_CONFIG).map(([key, config]) => {
                      const value = Number(scoreBreakdown?.components?.[key] ?? 0)
                      const percent = Math.min(100, Math.max(0, (value / config.maxValue) * 100))
                      return (
                        <div key={key}>
                          <div className="mb-2 flex items-center justify-between gap-3 text-sm text-slate-300">
                            <span>{config.label}</span>
                            <span>{value.toFixed(2)}</span>
                          </div>
                          <ProgressBar value={percent} className={config.colorClassName} size="lg" />
                        </div>
                      )
                    })}
                    <div className="grid grid-cols-1 gap-2 text-xs text-slate-400 sm:grid-cols-2">
                      <p>Total Score: {Number(scoreBreakdown.total_score || 0).toFixed(2)}</p>
                      <p>ETA To Scene: {Number(scoreBreakdown.eta_to_scene_minutes || 0).toFixed(1)} min</p>
                      <p>ETA To Hospital: {Number(scoreBreakdown.eta_to_hospital_minutes || 0).toFixed(1)} min</p>
                      <p>Total ETA: {Number(scoreBreakdown.total_eta_minutes || dispatchPlan?.eta_minutes || 0).toFixed(1)} min</p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    Live scoring details will appear here after the next dispatch.
                  </p>
                )}
                <Button
                  className="mt-3"
                  variant="ghost"
                  size="sm"
                  onClick={() => setScoreExpanded((expanded) => !expanded)}
                >
                  {scoreExpanded ? 'Show less' : 'Show more'}
                </Button>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

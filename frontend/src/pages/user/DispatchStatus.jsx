import { useNavigate } from 'react-router-dom'
import { MapPin } from 'lucide-react'

import useDispatchStore from '../../store/dispatchStore'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import StatusDot from '../../components/ui/StatusDot'
import EmptyState from '../../components/ui/EmptyState'

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

export default function DispatchStatus() {
  const navigate = useNavigate()
  const ambulances = useDispatchStore((s) => s.ambulances)
  const lastDispatch = useDispatchStore((s) => s.lastDispatch)
  const hospitals = useDispatchStore((s) => s.hospitals)
  const incidents = useDispatchStore((s) => s.incidents)

  const STATUS_LABEL = {
    available: 'Available',
    en_route: 'En route to scene',
    at_scene: 'On scene',
    transporting: 'Transporting patient',
    at_hospital: 'At hospital',
    unavailable: 'Unavailable',
  }

  const dispatch = lastDispatch?.data ?? lastDispatch
  const dispatchStatus = lastDispatch?.status || 'success'

  if (!dispatch) {
    return (
      <div>
        <Card>
          <EmptyState
            icon={MapPin}
            title="No active dispatch"
            subtitle="Submit an emergency SOS to track your ambulance."
          />
          <div className="mx-auto max-w-xs">
            <Button
              variant="primary"
              className="w-full"
              onClick={() => navigate('/user/sos')}
            >
              Go to Emergency SOS
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  const ambulance = ambulances.find(
    (a) => a.id === (lastDispatch?.ambulance_id ?? dispatch?.ambulance_id)
  )
  const hospital = hospitals.find(
    (h) => h.id === (lastDispatch?.hospital_id ?? dispatch?.hospital_id)
  )
  const incident = incidents.find((item) => item.id === dispatch?.incident_id)
  const eta = dispatch?.eta_minutes ?? dispatch?.data?.eta_minutes ?? 0

  return (
    <div className="space-y-4">
      <Card className="border-l-4 border-l-emerald-500">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-white">Dispatch Confirmed</h1>
            <p className="mt-1 text-sm text-slate-400">
              Your request is now assigned and being tracked live.
            </p>
          </div>
          <Badge variant={dispatchStatus === 'fallback' ? 'warning' : 'success'}>
            {dispatchStatus === 'fallback' ? 'Fallback' : 'Confirmed'}
          </Badge>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-slate-800/50 p-4">
            <p className="text-sm text-slate-400">Ambulance</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="text-2xl font-bold text-white">{dispatch?.ambulance_id}</span>
              {ambulance?.type ? <Badge variant="info">{ambulance.type}</Badge> : null}
              <span className="rounded-full bg-slate-900 px-3 py-1 text-xs text-slate-300">
                ETA {Number(eta || 0).toFixed(1)} min
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-slate-800/50 p-4">
            <p className="text-sm text-slate-400">Hospital</p>
            <div className="mt-2">
              <p className="text-2xl font-bold text-white">{dispatch?.hospital_id}</p>
              <p className="mt-1 text-sm text-slate-400">
                {hospital
                  ? `${hospital.city} \u00B7 ${Math.round(hospital.occupancy_pct)}% occupancy`
                  : 'Hospital assignment received'}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <Badge variant={severityBadgeMap[incident?.severity] || 'neutral'}>
            {incident?.severity ? formatLabel(incident.severity) : 'Assigned'}
          </Badge>
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-white">Ambulance Status</h2>
        <div className="mt-4 flex items-center gap-2">
          <StatusDot status={ambulance?.status || 'en_route'}/>
          <span className="text-sm text-slate-200">
            {STATUS_LABEL[ambulance?.status] || ambulance?.status || 'Locating...'}
          </span>
        </div>
        {ambulance ? (
          <div className="mt-4 space-y-2 text-sm text-slate-400">
            <p>City: {ambulance.city}</p>
            <p>Zone: {ambulance.zone}</p>
            <p>
              Equipment: {(ambulance.equipment || []).slice(0, 3).join(', ') || 'No equipment details'}
            </p>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-400">Locating ambulance...</p>
        )}
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-white">AI Explanation</h2>
        <p className="mt-4 text-sm italic text-slate-300">
          {dispatch?.explanation_text || lastDispatch?.message || 'The routing engine is continuously optimizing your dispatch.'}
        </p>
      </Card>
    </div>
  )
}

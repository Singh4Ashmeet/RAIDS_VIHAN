import clsx from 'clsx'
import { useState } from 'react'
import { Building2, Search, Truck } from 'lucide-react'

import useDispatchStore from '../../store/dispatchStore'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Skeleton from '../../components/ui/Skeleton'
import EmptyState from '../../components/ui/EmptyState'
import StatusDot from '../../components/ui/StatusDot'

const TABS = ['Fleet', 'Hospitals']
const FLEET_FILTERS = ['All', 'Available', 'En Route', 'Unavailable']

function formatLabel(value) {
  return String(value || 'Unknown')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function crewColor(v) {
  if (v >= 0.8) return 'bg-emerald-500'
  if (v >= 0.6) return 'bg-amber-500'
  return 'bg-red-500'
}

function barColor(pct) {
  if (pct >= 90) return 'bg-red-500'
  if (pct >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

function erBadge(wait) {
  if (wait < 15) return 'success'
  if (wait < 30) return 'info'
  if (wait < 45) return 'warning'
  return 'error'
}

export default function FleetHospitals() {
  const [activeTab, setActiveTab] = useState('Fleet')
  const [fleetFilter, setFleetFilter] = useState('All')
  const [search, setSearch] = useState('')

  const ambulances = useDispatchStore((state) => state.ambulances)
  const hospitals = useDispatchStore((state) => state.hospitals)
  const wsStatus = useDispatchStore((state) => state.wsStatus)

  const filteredAmbulances = ambulances.filter((ambulance) => {
    if (fleetFilter === 'All') return true
    if (fleetFilter === 'Available') return ambulance.status === 'available'
    if (fleetFilter === 'En Route') return ['en_route', 'at_scene'].includes(ambulance.status)
    return ['unavailable', 'at_hospital'].includes(ambulance.status)
  })

  const filteredHospitals = hospitals.filter((hospital) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return (
      hospital.name?.toLowerCase().includes(query) ||
      hospital.city?.toLowerCase().includes(query)
    )
  })

  const counts = {
    All: ambulances.length,
    Available: ambulances.filter((a) => a.status === 'available').length,
    'En Route': ambulances.filter((a) => ['en_route', 'at_scene'].includes(a.status)).length,
    Unavailable: ambulances.filter((a) => ['unavailable', 'at_hospital'].includes(a.status)).length,
  }

  const loading = wsStatus === 'disconnected' && ambulances.length === 0 && hospitals.length === 0

  return (
    <div>
      <div className="mb-6 flex border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`cursor-pointer px-3 sm:px-4 py-2 sm:py-2.5 text-sm font-medium ${
              activeTab === tab
                ? 'border-b-2 border-brand-500 text-brand-500'
                : 'text-slate-400 hover:text-slate-200'
            } focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'Fleet' ? (
        <div>
          <div className="mb-4 flex flex-wrap gap-1.5 sm:gap-2">
            {FLEET_FILTERS.map((filter) => (
              <Button
                key={filter}
                variant={fleetFilter === filter ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setFleetFilter(filter)}
              >
                {filter}
                <span className="ml-1 rounded-full bg-black/20 px-1.5 py-0.5 text-[10px]">
                  {counts[filter]}
                </span>
              </Button>
            ))}
          </div>

          {loading ? (
            <Skeleton count={6}/>
          ) : filteredAmbulances.length === 0 ? (
            <EmptyState
              icon={Truck}
              title="No units match this filter"
              subtitle="Try selecting a different status filter"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredAmbulances.map((amb) => (
                <Card key={amb.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <StatusDot status={amb.status}/>
                      <div>
                        <p className="text-lg font-bold text-white">
                          {amb.id}
                        </p>
                        <p className="text-sm text-slate-400">
                          {amb.city}
                        </p>
                      </div>
                    </div>
                    <Badge variant={amb.type === 'ALS' ? 'info' : 'neutral'}>
                      {amb.type}
                    </Badge>
                  </div>
                  <div className="mt-4 text-sm text-slate-300">
                    {formatLabel(amb.status)}
                  </div>
                  <div className="mt-4">
                    <p className="mb-2 text-xs text-slate-400">Crew readiness</p>
                    <div className="h-1 rounded-full bg-slate-700">
                      <div
                        className={clsx(
                          'h-1 rounded-full',
                          crewColor(amb.crew_readiness || 0)
                        )}
                        style={{
                          width: `${Math.max(0, Math.min(100, (amb.crew_readiness || 0) * 100))}%`,
                        }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-400">
                      {Math.round((amb.crew_readiness || 0) * 100)}% ready
                    </p>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div>
          <div className="mb-6 relative">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/>
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search hospitals by name or city"
              className="w-full rounded-xl border border-border bg-slate-800 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            />
          </div>

          {loading ? (
            <Skeleton count={4}/>
          ) : filteredHospitals.length === 0 ? (
            <EmptyState
              icon={Building2}
              title="No hospitals found"
              subtitle="Try another search term."
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {filteredHospitals.map((h) => {
                const occupancyPct = Math.max(0, Math.min(100, Number(h.occupancy_pct || 0)))
                const shown = (h.specialties || []).slice(0, 2)
                const extras = (h.specialties || []).length - 2

                return (
                  <Card key={h.id}>
                    <div className="flex items-start gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-lg font-bold text-white">{h.name}</p>
                          {h.diversion_status ? (
                            <Badge variant="error">DIVERTED</Badge>
                          ) : null}
                        </div>
                        <div className="mt-2">
                          <Badge variant="neutral">{h.city}</Badge>
                        </div>
                      </div>
                    </div>

                    <div className="mt-5">
                      <div className="mb-2 flex items-center justify-between text-sm text-slate-400">
                        <span>Occupancy</span>
                        <span>{Math.round(occupancyPct)}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-700">
                        <div
                          className={clsx(
                            'h-1.5 rounded-full transition-all',
                            barColor(occupancyPct)
                          )}
                          style={{ width: `${occupancyPct}%` }}
                        />
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <Badge variant={erBadge(h.er_wait_minutes)}>
                        ER Wait {h.er_wait_minutes} min
                      </Badge>
                      <span className="text-sm text-slate-400">
                        ICU: {h.icu_beds_available} / {h.total_icu_beds} beds
                      </span>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {shown.map((specialty) => (
                        <span
                          key={specialty}
                          className="rounded-full border border-border bg-slate-800 px-2.5 py-1 text-xs text-slate-300"
                        >
                          {specialty}
                        </span>
                      ))}
                      {extras > 0 ? (
                        <span className="text-xs text-slate-500">
                          +{extras} more
                        </span>
                      ) : null}
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

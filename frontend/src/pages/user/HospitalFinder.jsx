import clsx from 'clsx'
import { useMemo, useState } from 'react'
import { Building2, Search } from 'lucide-react'

import useDispatchStore from '../../store/dispatchStore'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Input from '../../components/ui/Input'
import Skeleton from '../../components/ui/Skeleton'
import EmptyState from '../../components/ui/EmptyState'
import ProgressBar from '../../components/ui/ProgressBar'

const CITY_FILTERS = ['All', 'Delhi', 'Mumbai', 'Bengaluru', 'Chennai', 'Hyderabad']
const STATUS_FILTERS = ['All', 'Accepting', 'Diverted']

function occupancyTone(hospital) {
  if (hospital.diversion_status || hospital.occupancy_pct >= 90) return 'bg-red-500'
  if (hospital.occupancy_pct >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

function incomingCount(h) {
  return Array.isArray(h.incoming_patients)
    ? h.incoming_patients.length
    : (h.incoming_patients ?? 0)
}

export default function HospitalFinder() {
  const hospitals = useDispatchStore((state) => state.hospitals)
  const wsStatus = useDispatchStore((state) => state.wsStatus)
  const [cityFilter, setCityFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [query, setQuery] = useState('')

  const filteredHospitals = useMemo(() => hospitals.filter((hospital) => {
    const matchesCity = cityFilter === 'All' || hospital.city === cityFilter
    const matchesStatus = statusFilter === 'All'
      ? true
      : statusFilter === 'Accepting'
        ? !hospital.diversion_status
        : hospital.diversion_status
    const search = query.trim().toLowerCase()
    const matchesSearch = !search || hospital.name?.toLowerCase().includes(search)
      || hospital.city?.toLowerCase().includes(search)

    return matchesCity && matchesStatus && matchesSearch
  }), [cityFilter, hospitals, query, statusFilter])

  const accepting = hospitals.filter((h) => !h.diversion_status).length
  const diverted = hospitals.filter((h) => h.diversion_status).length
  const avgOcc = hospitals.length
    ? Math.round(hospitals.reduce((a, h) => a + h.occupancy_pct, 0) / hospitals.length)
    : 0
  const loading = wsStatus !== 'connected' && hospitals.length === 0

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white">Hospital Finder</h1>
        <p className="mt-1 text-sm text-slate-400">
          Browse live-capacity hospitals and find the fastest accepting destination.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {CITY_FILTERS.map((city) => (
          <button
            key={city}
            onClick={() => setCityFilter(city)}
            className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
              cityFilter === city
                ? 'bg-brand-600/20 text-brand-400'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            } focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500`}
          >
            {city}
          </button>
        ))}
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
                statusFilter === status
                  ? 'bg-brand-600/20 text-brand-400'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              } focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500`}
            >
              {status}
            </button>
          ))}
        </div>
        <div className="lg:ml-auto lg:w-80">
          <Input
            icon={Search}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search hospitals"
          />
        </div>
      </div>

      <div className="mb-4 text-sm text-slate-400">
        <span className="font-medium text-emerald-400">
          {accepting} accepting
        </span>
        {' \u00B7 '}
        <span className="font-medium text-red-400">
          {diverted} diverted
        </span>
        {' \u00B7 '}
        avg {avgOcc}% occupancy
      </div>

      {loading ? (
        <Skeleton count={6}/>
      ) : filteredHospitals.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No hospitals match"
          subtitle="Try a different city or status filter"
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredHospitals.map((h) => {
            const extraSpecialties = Math.max(0, (h.specialties?.length || 0) - 2)

            return (
              <Card key={h.id}>
                <div
                  className={clsx(
                    'h-1 rounded-t-2xl -mx-6 -mt-6 mb-4',
                    h.diversion_status || h.occupancy_pct >= 90
                      ? 'bg-red-500'
                      : h.occupancy_pct >= 70
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                  )}
                />
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-bold text-white">{h.name}</p>
                      <div className="mt-2">
                        <Badge variant="neutral">{h.city}</Badge>
                      </div>
                    </div>
                  </div>

                  <div className="mt-5">
                    <div className="mb-2 flex items-center justify-between text-sm text-slate-400">
                      <span>Occupancy</span>
                      <span>{Math.round(h.occupancy_pct)}%</span>
                    </div>
                    <ProgressBar
                      value={h.occupancy_pct}
                      className={occupancyTone(h)}
                      trackClassName="bg-slate-700"
                    />
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-3 text-center">
                    <div className="rounded-xl bg-slate-800/70 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-slate-500">ER Wait</p>
                      <p className="mt-1 text-sm font-semibold text-white">{h.er_wait_minutes}m</p>
                    </div>
                    <div className="rounded-xl bg-slate-800/70 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-slate-500">ICU Beds</p>
                      <p className="mt-1 text-sm font-semibold text-white">
                        {h.icu_beds_available}/{h.total_icu_beds}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-800/70 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-slate-500">Incoming</p>
                      <p className="mt-1 text-sm font-semibold text-white">
                        {incomingCount(h)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {(h.specialties || []).slice(0, 2).map((specialty) => (
                      <span
                        key={specialty}
                        className="rounded-full border border-border bg-slate-800 px-2.5 py-1 text-xs text-slate-300"
                      >
                        {specialty}
                      </span>
                    ))}
                    {extraSpecialties > 0 ? (
                      <span className="rounded-full border border-border bg-slate-800 px-2.5 py-1 text-xs text-slate-500">
                        +{extraSpecialties} more
                      </span>
                    ) : null}
                  </div>

                  <div className="mt-4">
                    <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
                      <span>Acceptance score</span>
                      <span>{Math.round((h.acceptance_score || 0) * 100)}%</span>
                    </div>
                    <ProgressBar
                      value={h.acceptance_score || 0}
                      max={1}
                      className="bg-purple-500"
                      size="sm"
                      trackClassName="bg-slate-700"
                    />
                  </div>

                  <p className={`mt-4 text-sm font-medium ${
                    h.diversion_status
                      ? 'text-red-400'
                      : h.occupancy_pct >= 90
                        ? 'text-amber-400'
                        : 'text-emerald-400'
                  }`}>
                    {h.diversion_status
                      ? 'DIVERSION IN EFFECT'
                      : h.occupancy_pct >= 90
                        ? 'Near Capacity'
                        : 'Accepting Patients'}
                  </p>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

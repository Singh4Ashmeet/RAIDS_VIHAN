import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Ambulance,
  BrainCircuit,
  Clock3,
  Compass,
  LocateFixed,
  MapPinned,
  Navigation,
  Target,
} from 'lucide-react'

import { fetchDemandHeatmap } from '../../services/api'
import { mockHeatmap } from '../../services/mockData'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import ErrorState from '../../components/ui/ErrorState'
import ProgressBar from '../../components/ui/ProgressBar'
import Skeleton from '../../components/ui/Skeleton'

const CITIES = ['Delhi', 'Mumbai', 'Bengaluru', 'Chennai', 'Hyderabad']
const GRID_SIZE = 20
const DEMAND_BANDS = [
  { label: 'Quiet', hint: 'Routine coverage', min: 0, max: 0.44, color: 'bg-emerald-400' },
  { label: 'Watch', hint: 'Shift one unit nearby', min: 0.45, max: 0.74, color: 'bg-amber-400' },
  { label: 'Surge', hint: 'Pre-position now', min: 0.75, max: 1, color: 'bg-red-400' },
]

function getDemandBand(score) {
  if (score >= 0.75) return DEMAND_BANDS[2]
  if (score >= 0.45) return DEMAND_BANDS[1]
  return DEMAND_BANDS[0]
}

function demandCellClass(score) {
  if (score <= 0) return 'bg-slate-700/20'
  const opacity = score >= 0.8 ? 'opacity-100' : score >= 0.6 ? 'opacity-80' : score >= 0.35 ? 'opacity-60' : 'opacity-40'
  if (score > 0.75) return `bg-red-400 ${opacity}`
  if (score > 0.45) return `bg-amber-400 ${opacity}`
  return `bg-emerald-400 ${opacity}`
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function formatCoord(value) {
  return Number(value || 0).toFixed(4)
}

function HeatmapCanvas({ hotspots, selectedHotspot, onSelectHotspot }) {
  const cells = useMemo(() => {
    const byCell = new Map()
    hotspots.forEach((hotspot) => {
      byCell.set(`${hotspot.cell_row}-${hotspot.cell_col}`, hotspot)
    })

    return Array.from({ length: GRID_SIZE * GRID_SIZE }, (_, index) => {
      const row = Math.floor(index / GRID_SIZE)
      const col = index % GRID_SIZE
      const hotspot = byCell.get(`${row}-${col}`)
      const score = Number(hotspot?.demand_score || 0)
      return { row, col, score, hotspot }
    })
  }, [hotspots])

  return (
    <div className="relative mx-auto w-full max-w-[980px] overflow-hidden rounded-xl border border-border bg-slate-950/40 p-3 shadow-inner shadow-black/30 sm:p-4">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[size:8%_8%]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_35%_20%,rgba(56,189,248,0.14),transparent_34%),radial-gradient(circle_at_80%_78%,rgba(16,185,129,0.1),transparent_28%)]" />

      <div className="relative mb-3 grid grid-cols-[32px_minmax(0,1fr)_32px] items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-500 sm:grid-cols-[48px_minmax(0,1fr)_48px]">
        <span />
        <span className="text-center">North</span>
        <span />
      </div>

      <div className="relative grid grid-cols-[32px_minmax(0,1fr)_32px] items-center gap-2 sm:grid-cols-[48px_minmax(0,1fr)_48px]">
        <div className="origin-center -rotate-90 text-center text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
          West
        </div>
        <div
          className="mx-auto grid aspect-square w-full max-w-[640px] grid-cols-[repeat(20,minmax(0,1fr))] gap-0.5 rounded-lg border border-slate-700/70 bg-slate-950/50 p-1"
        >
          {cells.map((cell) => {
            const isSelected = selectedHotspot
              && selectedHotspot.cell_row === cell.row
              && selectedHotspot.cell_col === cell.col
            return (
              <button
                key={`${cell.row}-${cell.col}`}
                type="button"
                onClick={() => cell.hotspot && onSelectHotspot(cell.hotspot)}
                title={cell.hotspot ? `Cell ${cell.row}, ${cell.col}: demand ${formatPercent(cell.score)}` : 'No active demand'}
                className={`rounded-[3px] transition focus:outline-none focus:ring-2 focus:ring-sky-300 ${demandCellClass(cell.score)} ${
                  cell.hotspot ? 'cursor-pointer hover:scale-125 hover:ring-1 hover:ring-white/70' : 'cursor-default'
                } ${isSelected ? 'scale-125 ring-2 ring-white shadow-lg shadow-white/20' : ''}`}
                aria-label={cell.hotspot ? `Demand cell ${cell.row}, ${cell.col}, ${formatPercent(cell.score)}` : `Empty cell ${cell.row}, ${cell.col}`}
              />
            )
          })}
        </div>
        <div className="origin-center rotate-90 text-center text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
          East
        </div>
      </div>

      <div className="relative mt-3 grid grid-cols-[32px_minmax(0,1fr)_32px] items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-500 sm:grid-cols-[48px_minmax(0,1fr)_48px]">
        <span />
        <span className="text-center">South</span>
        <span />
      </div>

      <div className="relative mt-4 grid gap-3 lg:grid-cols-3">
        {DEMAND_BANDS.map((band) => (
          <div key={band.label} className="rounded-lg border border-slate-700/70 bg-slate-900/70 p-3">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${band.color}`} />
              <span className="text-sm font-semibold text-slate-100">{band.label}</span>
              <span className="ml-auto text-xs text-slate-500">
                {band.min === 0 ? '0' : Math.round(band.min * 100)}-{Math.round(band.max * 100)}%
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">{band.hint}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function CitySelect({ city, setCity }) {
  return (
    <div className="flex flex-wrap gap-2">
      {CITIES.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => setCity(option)}
          className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${
            city === option
              ? 'border-blue-500/50 bg-blue-500/15 text-blue-300'
              : 'border-border bg-slate-800/70 text-slate-400 hover:text-slate-100'
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  )
}

export default function DemandHeatmap() {
  const [city, setCity] = useState('Bengaluru')
  const [lookahead, setLookahead] = useState(30)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedHotspot, setSelectedHotspot] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchDemandHeatmap(city, lookahead)
      .then((payload) => {
        if (cancelled) return
        setData(payload)
        setSelectedHotspot(payload?.hotspots?.[0] || null)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        const fallbackData = { ...mockHeatmap, city, lookahead_minutes: lookahead }
        setData(fallbackData)
        setSelectedHotspot(fallbackData.hotspots[0] || null)
        setError(err.message || 'Using fallback demand model')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [city, lookahead])

  const hotspots = data?.hotspots || []
  const recommendations = data?.preposition_recommendations || []
  const topHotspot = hotspots[0]
  const averageDemand = hotspots.length
    ? hotspots.reduce((sum, hotspot) => sum + Number(hotspot.demand_score || 0), 0) / hotspots.length
    : 0
  const surgeCells = hotspots.filter((hotspot) => Number(hotspot.demand_score || 0) >= 0.75).length
  const selectedBand = getDemandBand(selectedHotspot?.demand_score || 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <div className="flex items-center gap-3">
            <span className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-2 text-blue-300">
              <BrainCircuit size={20} />
            </span>
            <div>
              <h1 className="text-[28px] font-semibold text-slate-100">Demand Heatmap</h1>
              <p className="mt-1 text-sm text-slate-400">
                Predictive 30-minute incident hotspots and AI pre-positioning guidance.
              </p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={lookahead}
            onChange={(event) => setLookahead(Number(event.target.value))}
            className="rounded-xl border border-border bg-slate-800 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={15}>15 min</option>
            <option value={30}>30 min</option>
            <option value={45}>45 min</option>
            <option value={60}>60 min</option>
          </select>
          <Button icon={LocateFixed} variant="secondary" onClick={() => setLookahead(30)}>
            Recenter
          </Button>
        </div>
      </div>

      <CitySelect city={city} setCity={setCity} />

      {loading ? (
        <Skeleton count={3} />
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4">
            {error ? (
              <ErrorState message={`${error}. Showing local fallback hotspots.`} />
            ) : null}

            <div className="grid gap-3 md:grid-cols-4">
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <span className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-2 text-sky-300">
                    <Activity size={17} />
                  </span>
                  <div>
                    <p className="text-xs text-slate-500">Active cells</p>
                    <p className="text-xl font-semibold text-white">{hotspots.length}</p>
                  </div>
                </div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <span className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-red-300">
                    <Target size={17} />
                  </span>
                  <div>
                    <p className="text-xs text-slate-500">Surge cells</p>
                    <p className="text-xl font-semibold text-white">{surgeCells}</p>
                  </div>
                </div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-amber-300">
                    <Clock3 size={17} />
                  </span>
                  <div>
                    <p className="text-xs text-slate-500">Window</p>
                    <p className="text-xl font-semibold text-white">{data?.lookahead_minutes || lookahead} min</p>
                  </div>
                </div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <span className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2 text-emerald-300">
                    <Ambulance size={17} />
                  </span>
                  <div>
                    <p className="text-xs text-slate-500">Moves</p>
                    <p className="text-xl font-semibold text-white">{recommendations.length}</p>
                  </div>
                </div>
              </Card>
            </div>

            <Card className="p-4">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-[22px] font-semibold text-white">{data?.city || city} Risk Grid</h2>
                  <p className="text-sm text-slate-400">
                    Each square is a city sector. Brighter cells mean more predicted emergency demand.
                  </p>
                </div>
                <Badge variant={topHotspot?.demand_score > 0.75 ? 'error' : 'warning'}>
                  Peak {formatPercent(topHotspot?.demand_score)}
                </Badge>
              </div>
              <HeatmapCanvas
                hotspots={hotspots}
                selectedHotspot={selectedHotspot}
                onSelectHotspot={setSelectedHotspot}
              />
            </Card>
          </div>

          <div className="space-y-4">
            <Card>
              <div className="flex items-center gap-3">
                <span className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-2 text-sky-300">
                  <Compass size={18} />
                </span>
                <div>
                  <h2 className="text-lg font-medium text-white">Selected Sector</h2>
                  <p className="text-xs text-slate-500">Click a colored cell on the grid</p>
                </div>
              </div>
              {selectedHotspot ? (
                <div className="mt-5 rounded-xl border border-border bg-slate-800/60 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-slate-500">Cell {selectedHotspot.cell_row}, {selectedHotspot.cell_col}</p>
                      <p className="mt-1 font-mono text-sm text-slate-100">
                        {formatCoord(selectedHotspot.lat)}, {formatCoord(selectedHotspot.lng)}
                      </p>
                    </div>
                    <Badge variant={selectedHotspot.demand_score >= 0.75 ? 'error' : selectedHotspot.demand_score >= 0.45 ? 'warning' : 'success'}>
                      {selectedBand.label}
                    </Badge>
                  </div>
                  <div className="mt-4">
                    <ProgressBar
                      value={selectedHotspot.demand_score}
                      max={1}
                      className="bg-gradient-to-r from-emerald-400 via-amber-400 to-red-400"
                      trackClassName="bg-slate-700"
                    />
                  </div>
                  <div className="mt-3 flex items-center justify-between text-sm">
                    <span className="text-slate-500">Demand score</span>
                    <span className="font-semibold text-white">{formatPercent(selectedHotspot.demand_score)}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {selectedBand.hint}. Expected incidents in this window: {selectedHotspot.predicted_incidents}.
                  </p>
                </div>
              ) : (
                <p className="mt-5 text-sm text-slate-400">No active demand sectors in this window.</p>
              )}
            </Card>

            <Card>
              <div className="flex items-center gap-3">
                <span className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2 text-emerald-300">
                  <MapPinned size={18} />
                </span>
                <div>
                  <h2 className="text-lg font-medium text-white">Top Hotspots</h2>
                  <p className="text-xs text-slate-500">Sorted by predicted demand</p>
                </div>
              </div>
              <div className="mt-5 space-y-3">
                {hotspots.slice(0, 5).map((hotspot) => (
                  <button
                    key={`${hotspot.cell_row}-${hotspot.cell_col}`}
                    type="button"
                    onClick={() => setSelectedHotspot(hotspot)}
                    className="w-full rounded-xl border border-border bg-slate-800/60 p-3 text-left transition hover:border-sky-500/40 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-slate-200">Cell {hotspot.cell_row}, {hotspot.cell_col}</p>
                      <span className="text-sm font-semibold text-amber-300">
                        {formatPercent(hotspot.demand_score)}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      {formatCoord(hotspot.lat)}, {formatCoord(hotspot.lng)} - expected incidents {hotspot.predicted_incidents}
                    </p>
                  </button>
                ))}
              </div>
            </Card>

            <Card>
              <div className="flex items-center gap-3">
                <span className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-2 text-blue-300">
                  <Navigation size={18} />
                </span>
                <div>
                  <h2 className="text-lg font-medium text-white">Pre-positioning</h2>
                  <p className="text-xs text-slate-500">Recommended unit moves</p>
                </div>
              </div>
              <div className="mt-5 space-y-3">
                {recommendations.length === 0 ? (
                  <p className="text-sm text-slate-400">Current coverage is sufficient for this window.</p>
                ) : recommendations.map((rec) => (
                  <div key={`${rec.ambulance_id}-${rec.move_to_lat}`} className="rounded-xl border border-border bg-slate-800/60 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-white">{rec.ambulance_id}</p>
                      <Badge variant="info">{formatPercent(rec.hotspot_demand_score)}</Badge>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-400">{rec.reason}</p>
                    <p className="mt-2 font-mono text-xs text-slate-500">
                      Move to {formatCoord(rec.move_to_lat)}, {formatCoord(rec.move_to_lng)}
                    </p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Reading the model</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Average active-cell demand is {formatPercent(averageDemand)}. Use red cells as immediate staging targets,
                amber cells as watch sectors, and green cells as normal coverage.
              </p>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

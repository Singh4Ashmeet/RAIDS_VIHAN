import { useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
  ReferenceLine,
} from 'recharts'
import { AlertCircle, Info, Scale, Sparkles, TrendingDown } from 'lucide-react'

import useDispatchStore from '../../store/dispatchStore'
import Badge from '../../components/ui/Badge'
import Card from '../../components/ui/Card'
import Skeleton from '../../components/ui/Skeleton'
import ErrorState from '../../components/ui/ErrorState'
import api from '../../services/api'
import { mockAnalytics, mockBenchmark, mockLiteratureComparison } from '../../services/mockData'

const BENCHMARK_ROW_CONFIG = [
  { key: 'avg_eta_minutes', label: 'Average ETA (min)', better: 'lower', format: (value) => Number(value || 0).toFixed(1) },
  { key: 'p90_eta', label: 'P90 ETA (min)', better: 'lower', format: (value) => Number(value || 0).toFixed(1) },
  { key: 'specialty_match_rate', label: 'Specialty Match Rate (%)', better: 'higher', format: (value) => `${Number(value || 0).toFixed(1)}%` },
  { key: 'overload_events', label: 'Hospital Overload Events', better: 'lower', format: (value) => `${Number(value || 0)}` },
  { key: 'delayed_incidents', label: 'Delayed Incidents', better: 'lower', format: (value) => `${Number(value || 0)}` },
]

const BENCHMARK_BUCKETS = [
  { label: '0-5min', min: 0, max: 5 },
  { label: '5-10min', min: 5, max: 10 },
  { label: '10-15min', min: 10, max: 15 },
  { label: '15-20min', min: 15, max: 20 },
  { label: '20+min', min: 20, max: Number.POSITIVE_INFINITY },
]

function useBenchmark() {
  const [state, setState] = useState({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setState((current) => ({
        data: current.data,
        loading: true,
        error: null,
      }))

      try {
        const res = await api.get('/benchmark')
        const payload = res.data?.data || res.data
        if (cancelled) return

        if (payload?.error) {
          const message = payload.run_command
            ? `${payload.error}. Run: ${payload.run_command}`
            : payload.error
          setState({ data: null, loading: false, error: message })
          return
        }

        setState({ data: payload, loading: false, error: null })
      } catch (err) {
        if (cancelled) return
        setState({
          data: mockBenchmark,
          loading: false,
          error: null,
        })
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  return state
}

function useFairness() {
  const [fairness, setFairness] = useState({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false

    api.get('/fairness')
      .then((response) => {
        if (cancelled) return
        setFairness({ data: response.data, loading: false, error: null })
      })
      .catch((err) => {
        if (cancelled) return
        setFairness({
          data: null,
          loading: false,
          error: err.response?.data?.error ||
            err.response?.data?.detail ||
            err.message ||
            'Fairness data unavailable',
        })
      })

    return () => {
      cancelled = true
    }
  }, [])

  return fairness
}

function useLiteratureComparison() {
  const [literature, setLiterature] = useState({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false

    api.get('/literature-comparison')
      .then((response) => {
        if (cancelled) return
        const payload = response.data?.data || response.data
        if (payload?.error) {
          setLiterature({
            data: null,
            loading: false,
            error: payload.error,
          })
          return
        }
        setLiterature({ data: payload, loading: false, error: null })
      })
      .catch(() => {
        if (cancelled) return
        setLiterature({
          data: mockLiteratureComparison,
          loading: false,
          error: null,
        })
      })

    return () => {
      cancelled = true
    }
  }, [])

  return literature
}

function positiveTone(value, goodThreshold, warnThreshold) {
  if (value >= goodThreshold) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  if (value >= warnThreshold) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'
  return 'text-red-400 border-red-500/30 bg-red-500/10'
}

function incidentTone(value) {
  if (value <= 3) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  if (value <= 7) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'
  return 'text-red-400 border-red-500/30 bg-red-500/10'
}

function fairnessTone(score) {
  if (score > 80) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  if (score >= 60) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'
  return 'text-red-400 border-red-500/30 bg-red-500/10'
}

function penaltyTone(value) {
  if (value < 20) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
  if (value <= 35) return 'text-amber-400 border-amber-500/30 bg-amber-500/10'
  return 'text-red-400 border-red-500/30 bg-red-500/10'
}

function zoneEtaTone(zone, eta, centralEta) {
  if (zone === 'central') return 'text-emerald-400'
  if (zone === 'mid') {
    return eta > centralEta * 1.2 ? 'text-amber-400' : 'text-white'
  }
  if (eta > centralEta * 1.3) return 'text-red-400'
  if (eta > centralEta * 1.15) return 'text-amber-400'
  return 'text-white'
}

function StatCard({ label, value, accentClassName }) {
  return (
    <Card>
      <p className="text-sm text-slate-400">{label}</p>
      <p className={`mt-3 text-3xl font-bold text-white ${accentClassName || ''}`}>
        {value}
      </p>
    </Card>
  )
}

function FairnessMetricCard({ label, value, suffix, delta, tone, icon: Icon }) {
  return (
    <Card className={`border ${tone}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-400">{label}</p>
          <div className="mt-3 flex items-baseline gap-1">
            <p className="text-3xl font-bold text-white">{value}</p>
            {suffix ? <span className="text-sm text-slate-400">{suffix}</span> : null}
          </div>
          {delta ? <p className="mt-2 text-xs text-slate-400">{delta}</p> : null}
        </div>
        {Icon ? (
          <div className="rounded-lg border border-border bg-slate-800 p-2">
            <Icon size={18} className={tone.split(' ')[0]} />
          </div>
        ) : null}
      </div>
    </Card>
  )
}

function ReadinessCard({ label, value, detail, tone }) {
  return (
    <Card className={`border ${tone}`}>
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-bold text-white">{value}</p>
      <p className="mt-2 text-xs text-slate-400">{detail}</p>
    </Card>
  )
}

function FairnessTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null

  return (
    <div className="rounded-lg border border-border bg-slate-800 px-3 py-2 text-sm shadow-xl shadow-black/20">
      <p className="mb-2 font-medium text-white">{label}</p>
      <div className="space-y-1">
        {payload.map((item) => (
          <div key={item.dataKey} className="flex items-center gap-2 text-slate-300">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                item.dataKey === 'ai' ? 'bg-blue-500' : 'bg-amber-500'
              }`}
            />
            <span>{item.name}: {Number(item.value || 0).toFixed(1)} min</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 shadow-xl shadow-black/20">
      {label ? <p className="mb-2 font-medium text-white">{label}</p> : null}
      <div className="space-y-1">
        {payload.map((item) => (
          <p key={item.dataKey} className="text-slate-300">
            {item.name || item.dataKey}: {Number(item.value || 0).toFixed(1)}
          </p>
        ))}
      </div>
    </div>
  )
}

function buildFairnessChartData(fairness) {
  const aiZones = fairness?.ai_dispatch?.zones || {}
  const nearestZones = fairness?.nearest_unit?.zones || {}
  return [
    { zone: 'Central Zone', key: 'central' },
    { zone: 'Mid Zone', key: 'mid' },
    { zone: 'Peripheral Zone', key: 'peripheral' },
  ].map((item) => ({
    zone: item.zone,
    ai: Number(aiZones[item.key]?.avg_eta || 0),
    nearest: Number(nearestZones[item.key]?.avg_eta || 0),
  }))
}

function benchmarkDelta(aiValue, nearestValue, better) {
  const ai = Number(aiValue || 0)
  const nearest = Number(nearestValue || 0)

  if (ai === nearest) {
    return { direction: 'same', percent: 0 }
  }

  if (better === 'higher') {
    if (nearest === 0) {
      return { direction: ai > nearest ? 'better' : 'worse', percent: ai > nearest ? 100 : 0 }
    }
    const percent = Math.abs(((ai - nearest) / nearest) * 100)
    return { direction: ai > nearest ? 'better' : 'worse', percent }
  }

  if (nearest === 0) {
    return { direction: ai < nearest ? 'better' : 'worse', percent: ai < nearest ? 100 : 0 }
  }

  const percent = Math.abs(((nearest - ai) / nearest) * 100)
  return { direction: ai < nearest ? 'better' : 'worse', percent }
}

function buildBenchmarkBuckets(results) {
  const ai = results?.strategies?.ai_dispatch?.per_incident || []
  const nearest = results?.strategies?.nearest_unit?.per_incident || []
  const random = results?.strategies?.random_dispatch?.per_incident || []

  const countBucket = (items, min, max) => items.filter((item) => {
    const eta = Number(item.eta_minutes || 0)
    if (max === Number.POSITIVE_INFINITY) return eta >= min
    return eta >= min && eta < max
  }).length

  return BENCHMARK_BUCKETS.map((bucket) => ({
    bucket: bucket.label,
    ai: countBucket(ai, bucket.min, bucket.max),
    nearest: countBucket(nearest, bucket.min, bucket.max),
    random: countBucket(random, bucket.min, bucket.max),
  }))
}

function formatBenchmarkDate(value) {
  if (!value) return 'Unknown date'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Unknown date'
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function benchmarkSubtitle(results) {
  const evaluation = results?.evaluation
  if (!evaluation) return '700 synthetic incidents with chronological train/test evaluation'

  const dataset = evaluation.evaluation_dataset || 'synthetic_incidents.json'
  const count = Number(evaluation.evaluation_count || results?.total_incidents || 0)
  const trainingCount = Number(evaluation.training_count || 0)
  const splitMethod = evaluation.split_method || 'chronological split'

  if (evaluation.held_out) {
    return `${dataset} held out for evaluation (N=${count}) • ${evaluation.training_dataset} for calibration (N=${trainingCount}) • ${splitMethod}`
  }

  return `${dataset} (N=${count}) • ${evaluation.training_dataset} for calibration (N=${trainingCount}) • ${splitMethod}`
}

function benchmarkFooter(results) {
  const evaluation = results?.evaluation
  if (!evaluation) {
    return `Benchmark run on ${formatBenchmarkDate(results?.generated_at)} • ${results?.total_incidents || 0} incidents • 5 cities • 3 strategies`
  }

  return `Benchmark run on ${formatBenchmarkDate(results?.generated_at)} • ${evaluation.evaluation_dataset} • ${evaluation.evaluation_count || results?.total_incidents || 0} incidents • ${evaluation.split_method}`
}

function buildLiteratureRows(literature) {
  const papers = literature?.papers || []
  const raid = literature?.raid_nexus || {}

  return [
    ...papers.map((paper) => ({
      key: `${paper.authors}-${paper.year}`,
      study: paper.authors,
      year: paper.year,
      method: paper.method_short || paper.method,
      improvement: Number(paper.improvement_over_baseline_pct || 0),
      highlight: false,
    })),
    {
      key: 'raid-held-out',
      study: 'RAID Nexus (held-out)',
      year: raid.held_out?.year || 2024,
      method: 'Multi-obj.',
      improvement: Number(raid.held_out?.improvement_over_baseline_pct || 0),
      highlight: true,
    },
    {
      key: 'raid-cross-city',
      study: 'RAID Nexus (cross-city)',
      year: raid.cross_city?.year || 2024,
      method: 'Multi-obj.',
      improvement: Number(raid.cross_city?.improvement_over_baseline_pct || 0),
      highlight: true,
    },
  ]
}

function BenchmarkTable({ results }) {
  const strategies = results?.strategies || {}
  const ai = strategies.ai_dispatch || {}
  const nearest = strategies.nearest_unit || {}
  const random = strategies.random_dispatch || {}

  return (
    <div className="overflow-x-auto rounded-2xl border border-border">
      <table className="min-w-full border-collapse text-sm">
        <thead className="bg-slate-800 text-slate-300">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Metric</th>
            <th className="px-4 py-3 text-left font-medium">AI Dispatch</th>
            <th className="px-4 py-3 text-left font-medium">Nearest Unit</th>
            <th className="px-4 py-3 text-left font-medium">Random</th>
          </tr>
        </thead>
        <tbody>
          {BENCHMARK_ROW_CONFIG.map((row) => {
            const delta = benchmarkDelta(ai[row.key], nearest[row.key], row.better)
            const aiTone = delta.direction === 'better'
              ? 'text-emerald-400'
              : delta.direction === 'worse'
                ? 'text-red-400'
                : 'text-slate-200'
            const arrow = delta.direction === 'better'
              ? '\u2191'
              : delta.direction === 'worse'
                ? '\u2193'
                : ''
            const deltaLabel = delta.direction === 'same'
              ? 'No change vs Nearest'
              : `${delta.percent.toFixed(1)}% ${delta.direction === 'better' ? 'better' : 'worse'} vs Nearest`

            return (
              <tr key={row.key} className="border-t border-border text-slate-300">
                <td className="px-4 py-3 font-medium text-slate-200">{row.label}</td>
                <td className="bg-slate-800/50 px-4 py-3">
                  <div className={`font-semibold ${aiTone}`}>
                    {row.format(ai[row.key])} {arrow ? <span>{arrow}</span> : null}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">
                    {deltaLabel}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-300">{row.format(nearest[row.key])}</td>
                <td className="px-4 py-3 text-slate-300">{row.format(random[row.key])}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function BenchmarkChart({ results }) {
  const data = useMemo(() => buildBenchmarkBuckets(results), [results])

  return (
    <div className="h-[220px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={8}>
          <CartesianGrid stroke="rgb(51 65 85)" strokeDasharray="3 3"/>
          <XAxis dataKey="bucket" tick={{ fill: 'rgb(148 163 184)', fontSize: 12 }} axisLine={false} tickLine={false}/>
          <YAxis tick={{ fill: 'rgb(148 163 184)', fontSize: 12 }} axisLine={false} tickLine={false}/>
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="ai" name="AI Dispatch" fill="rgb(52 211 153)" radius={[6, 6, 0, 0]}/>
          <Bar dataKey="nearest" name="Nearest Unit" fill="rgb(245 158 11)" radius={[6, 6, 0, 0]}/>
          <Bar dataKey="random" name="Random" fill="rgb(239 68 68)" radius={[6, 6, 0, 0]}/>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function FairnessSection({ fairness }) {
  if (fairness.loading) {
    return (
      <div className="mt-8 border-t border-border pt-6">
        <Card>
          <div className="space-y-3">
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-2/3 rounded-lg" />
          </div>
        </Card>
      </div>
    )
  }

  if (fairness.error || !fairness.data) {
    return (
      <div className="mt-8 border-t border-border pt-6">
        <Card className="flex min-h-[220px] flex-col items-center justify-center text-center">
          <AlertCircle size={32} className="text-amber-400" />
          <p className="mt-3 text-sm font-medium text-white">Fairness data unavailable</p>
          <p className="mt-2 text-xs font-mono text-slate-500">
            Run the benchmark first: python backend/scripts/benchmark.py
          </p>
        </Card>
      </div>
    )
  }

  const data = fairness.data
  const ai = data.ai_dispatch || {}
  const comparison = data.comparison || {}
  const centralEta = Number(ai.zones?.central?.avg_eta || 0)
  const chartData = buildFairnessChartData(data)
  const equityScore = Number(ai.equity_score || 0)
  const peripheralPenalty = Number(ai.peripheral_penalty_pct || 0)
  const zones = [
    ['central', 'Central'],
    ['mid', 'Mid'],
    ['peripheral', 'Peripheral'],
  ]

  return (
    <div className="mt-8 border-t border-border pt-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Geographic Fairness Analysis</h2>
          <p className="mt-1 text-xs text-slate-400">
            AI dispatch equity across central, mid and peripheral zones
          </p>
        </div>
        <Badge variant={comparison.ai_more_equitable ? 'success' : 'warning'}>
          {comparison.ai_more_equitable ? 'AI More Equitable' : 'Investigate Disparity'}
        </Badge>
      </div>

      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FairnessMetricCard
            label="AI Equity Score"
            value={equityScore.toFixed(1)}
            suffix="/100"
            delta={ai.equity_label}
            tone={fairnessTone(equityScore)}
            icon={Scale}
          />
          <FairnessMetricCard
            label="Disparity Improvement"
            value={Number(comparison.disparity_improvement || 0).toFixed(2)}
            suffix=""
            delta={comparison.ai_more_equitable ? '✓ AI is more fair' : '✗ AI not more fair'}
            tone={comparison.ai_more_equitable
              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
              : 'text-amber-400 border-amber-500/30 bg-amber-500/10'}
            icon={TrendingDown}
          />
        </div>

        <Card>
          <div className="mb-4">
            <h3 className="text-base font-semibold text-white">Zone ETA Comparison</h3>
            <p className="text-sm text-slate-400">
              Average ambulance ETA by geographic zone and dispatch strategy
            </p>
          </div>
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barGap={8}>
                <CartesianGrid stroke="rgb(51 65 85)" strokeDasharray="3 3" />
                <XAxis dataKey="zone" tick={{ fill: 'rgb(148 163 184)', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fill: 'rgb(148 163 184)', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  label={{
                    value: 'Avg ETA (min)',
                    angle: -90,
                    position: 'insideLeft',
                    fill: 'rgb(148 163 184)',
                    fontSize: 12,
                  }}
                />
                <Tooltip content={<FairnessTooltip />} />
                <ReferenceLine y={centralEta} stroke="rgb(148 163 184)" strokeDasharray="4 4" />
                <Bar dataKey="ai" name="AI Dispatch" fill="rgb(59 130 246)" radius={[4, 4, 0, 0]} opacity={0.85} />
                <Bar dataKey="nearest" name="Nearest Unit" fill="rgb(245 158 11)" radius={[4, 4, 0, 0]} opacity={0.85} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-4 text-xs text-slate-400">
            <span className="inline-flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
              AI Dispatch
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
              Nearest Unit
            </span>
          </div>
        </Card>

        <Card>
          <div className="grid grid-cols-4 gap-3 border-b border-border pb-3 text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
            <span>Zone</span>
            <span>Avg ETA</span>
            <span>Specialty Match</span>
            <span>Overload Rate</span>
          </div>
          <div className="divide-y divide-border">
            {zones.map(([zone, label]) => {
              const zoneData = ai.zones?.[zone] || {}
              const eta = Number(zoneData.avg_eta || 0)
              return (
                <div key={zone} className="grid grid-cols-4 gap-3 py-3 text-sm">
                  <span className="font-medium text-white">{label}</span>
                  <span className={zoneEtaTone(zone, eta, centralEta)}>
                    {eta.toFixed(1)} min
                  </span>
                  <span className="text-slate-300">
                    {Number(zoneData.specialty_match_rate || 0).toFixed(1)}%
                  </span>
                  <span className="text-slate-300">
                    {Number(zoneData.overload_rate || 0).toFixed(1)}%
                  </span>
                </div>
              )
            })}
          </div>
          <div className={`mt-4 inline-flex rounded-full border px-3 py-1 text-xs ${penaltyTone(peripheralPenalty)}`}>
            Peripheral zones receive {peripheralPenalty.toFixed(1)}% longer ETAs than central
          </div>
        </Card>

        <Card>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-purple-400" />
                <p className="text-sm font-semibold text-white">Fairness Summary</p>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">
                {comparison.summary || 'Fairness summary will appear after benchmark analysis completes.'}
              </p>
            </div>
            {(comparison.zones_where_ai_wins?.length || comparison.zones_where_ai_loses?.length) ? (
              <div className="min-w-[180px]">
                <p className="mb-2 text-xs text-slate-400">AI wins in:</p>
                <div className="flex flex-wrap gap-2">
                  {comparison.zones_where_ai_wins?.map((zone) => (
                    <Badge key={`win-${zone}`} variant="success">{zone}</Badge>
                  ))}
                  {comparison.zones_where_ai_loses?.map((zone) => (
                    <Badge key={`lose-${zone}`} variant="warning">{zone}</Badge>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  )
}

function LiteratureComparisonSection({ literature }) {
  if (literature.loading) {
    return (
      <div className="mt-8 border-t border-border pt-6">
        <Card>
          <div className="space-y-3">
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-2/3 rounded-lg" />
          </div>
        </Card>
      </div>
    )
  }

  if (literature.error || !literature.data) {
    return (
      <div className="mt-8 border-t border-border pt-6">
        <Card className="flex min-h-[220px] flex-col items-center justify-center text-center">
          <AlertCircle size={32} className="text-amber-400" />
          <p className="mt-3 text-sm font-medium text-white">Literature comparison unavailable</p>
          <p className="mt-2 text-xs font-mono text-slate-500">
            Run: python backend/scripts/literature_comparison.py
          </p>
        </Card>
      </div>
    )
  }

  const rows = buildLiteratureRows(literature.data)

  return (
    <div className="mt-8 border-t border-border pt-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Published Literature Comparison</h2>
          <p className="mt-1 text-xs text-slate-400">
            Situating RAID Nexus within peer-reviewed EMS optimization research
          </p>
        </div>
        <Badge variant="neutral">Simulation vs Real-world - not directly comparable</Badge>
      </div>

      <Card>
        <div className="overflow-x-auto rounded-2xl border border-border">
          <table className="min-w-full border-collapse text-sm">
            <thead className="bg-slate-800 text-slate-300">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Study</th>
                <th className="px-4 py-3 text-left font-medium">Year</th>
                <th className="px-4 py-3 text-left font-medium">Method</th>
                <th className="px-4 py-3 text-left font-medium">ETA Improvement</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.key}
                  className={`border-t border-border ${
                    row.highlight ? 'bg-brand-500/10 text-brand-100' : 'text-slate-300'
                  }`}
                >
                  <td className={`px-4 py-3 ${row.highlight ? 'font-semibold text-white' : 'text-slate-200'}`}>
                    {row.study}
                  </td>
                  <td className={`px-4 py-3 ${row.highlight ? 'font-semibold text-white' : ''}`}>
                    {row.year}
                  </td>
                  <td className={`px-4 py-3 ${row.highlight ? 'font-semibold text-white' : ''}`}>
                    {row.method}
                  </td>
                  <td className={`px-4 py-3 ${row.highlight ? 'font-semibold text-brand-300' : ''}`}>
                    +{row.improvement.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900 p-3">
          <div className="flex items-start gap-2">
            <Info size={12} className="mt-0.5 shrink-0 text-slate-500" />
            <p className="text-xs text-slate-500">
              Direct comparison is not methodologically valid. Results are shown to situate this work within the published range. See docs/data_methodology.md for full context.
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default function Analytics() {
  const ambulances = useDispatchStore((s) => s.ambulances)
  const hospitals = useDispatchStore((s) => s.hospitals)
  const incidents = useDispatchStore((s) => s.incidents)
  const benchmark = useBenchmark()
  const fairness = useFairness()
  const literature = useLiteratureComparison()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const load = () => {
      api.get('/analytics')
        .then((res) => {
          setData(res.data?.data || res.data)
          setError(null)
        })
        .catch(() => {
          setData(mockAnalytics)
          setError(null)
        })
        .finally(() => setLoading(false))
    }

    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const values = data || {}
  const diff = (data?.avg_eta_baseline || 0) - (data?.avg_eta_ai || 0)
  const fleetPct = Math.round(
    ambulances.filter((a) => a.status === 'available').length
    / Math.max(ambulances.length, 1) * 100
  )
  const hospCap = Math.round(
    hospitals.reduce((a, h) => a + (100 - Number(h.occupancy_pct || 0)), 0)
    / Math.max(hospitals.length, 1)
  )
  const openInc = incidents.length

  const chartData = useMemo(() => ([
    {
      name: 'Today',
      ai: Number(values.avg_eta_ai || 0),
      baseline: Number(values.avg_eta_baseline || 0),
    },
  ]), [values.avg_eta_ai, values.avg_eta_baseline])

  if (loading) {
    return <Skeleton count={5}/>
  }

  if (error) {
    return <ErrorState message={error}/>
  }

  const chartHeight = typeof window !== 'undefined' && window.innerWidth < 640 ? 180 : 280

  return (
    <div>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
        <StatCard label="Incidents Today" value={values.incidents_today || 0}/>
        <StatCard label="Dispatches" value={values.dispatches_today || 0}/>
        <StatCard label="Hospitals Notified" value={values.hospitals_notified || 0}/>
        <StatCard label="Overloads Prevented" value={values.overloads_prevented || 0}/>
        <StatCard
          label="ETA Savings"
          value={`${diff > 0 ? '+' : ''}${diff.toFixed(1)} min`}
          accentClassName={diff > 0 ? 'text-emerald-400' : 'text-red-400'}
        />
      </div>

      <div>
        <Card>
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-white">ETA Comparison</h2>
            <p className="text-sm text-slate-400">AI routing versus baseline dispatch time</p>
          </div>

          {diff > 0.1 ? (
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-400">
              RAID Nexus saves {diff.toFixed(1)} min per dispatch today
            </div>
          ) : (
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-slate-700/50 px-4 py-1.5 text-sm text-slate-400">
              No improvement yet {'\u2014'} more dispatches needed
            </div>
          )}

          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart data={chartData}>
              <CartesianGrid stroke="rgb(51 65 85)" strokeDasharray="3 3"/>
              <XAxis dataKey="name" tick={{ fill: 'rgb(148 163 184)' }} axisLine={false} tickLine={false}/>
              <YAxis tick={{ fill: 'rgb(148 163 184)' }} axisLine={false} tickLine={false}/>
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={Number(values.avg_eta_ai || 0)} stroke="rgb(16 185 129)" strokeDasharray="4 4"/>
              <Bar dataKey="ai" fill="rgb(59 130 246)" radius={[8, 8, 0, 0]}/>
              <Bar dataKey="baseline" fill="rgb(71 85 105)" radius={[8, 8, 0, 0]}/>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="mt-6">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-white">System Readiness</h2>
          <p className="text-sm text-slate-400">Operational health derived from the live store</p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <ReadinessCard
            label="Fleet readiness"
            value={`${fleetPct}%`}
            detail="Available ambulances across the live fleet"
            tone={positiveTone(fleetPct, 60, 30)}
          />
          <ReadinessCard
            label="Hospital capacity"
            value={`${hospCap}%`}
            detail="Average spare capacity across hospitals"
            tone={positiveTone(hospCap, 40, 20)}
          />
          <ReadinessCard
            label="Open incidents"
            value={openInc}
            detail="Current unresolved emergency load"
            tone={incidentTone(openInc)}
          />
        </div>
      </div>

      <div className="mt-8 border-t border-border pt-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold text-white">Offline Benchmark Results</h2>
              <span className="rounded-full bg-gray-800 px-2.5 py-1 text-xs text-gray-300">
                Static evaluation
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-400">
              {benchmarkSubtitle(benchmark.data)}
            </p>
          </div>
        </div>

        {benchmark.loading ? (
          <Skeleton count={3}/>
        ) : benchmark.error ? (
          <ErrorState message={benchmark.error}/>
        ) : (
          <div className="space-y-6">
            <Card>
              <div className="mb-4">
                <h3 className="text-base font-semibold text-white">Strategy Comparison</h3>
                <p className="text-sm text-slate-400">
                  AI Dispatch compared with distance-only and random baselines
                </p>
              </div>
              <BenchmarkTable results={benchmark.data}/>
            </Card>

            <Card>
              <div className="mb-4">
                <h3 className="text-base font-semibold text-white">ETA Distribution</h3>
                <p className="text-sm text-slate-400">
                  Incident counts grouped by ambulance ETA buckets across strategies
                </p>
              </div>
              <BenchmarkChart results={benchmark.data}/>
              <div className="mt-4 text-xs text-slate-500">
                {benchmarkFooter(benchmark.data)}
              </div>
            </Card>
          </div>
        )}
      </div>

      <FairnessSection fairness={fairness} />
      <LiteratureComparisonSection literature={literature} />
    </div>
  )
}

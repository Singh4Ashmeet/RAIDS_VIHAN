import { useEffect, useState } from 'react'
import { fetchAnalytics } from '../services/api'
import MetricCard from '../shared/MetricCard'
import Spinner from '../shared/Spinner'
import EtaComparisonChart from './subcomponents/EtaComparisonChart'

function buildMetricCards(data) {
  return [
    {
      label: 'Incidents Today',
      value: data?.incidents_today ?? 0,
      highlight: 'purple',
    },
    {
      label: 'Dispatches',
      value: data?.dispatches_today ?? 0,
      highlight: 'teal',
    },
    {
      label: 'Hospitals Notified',
      value: data?.hospitals_notified ?? 0,
      highlight: 'amber',
    },
    {
      label: 'Overloads Prevented',
      value: data?.overloads_prevented ?? 0,
      highlight: 'coral',
    },
    {
      label: 'AI ETA',
      value: data?.avg_eta_ai ?? 0,
      unit: 'min',
      highlight: 'teal',
    },
    {
      label: 'Baseline ETA',
      value: data?.avg_eta_baseline ?? 0,
      unit: 'min',
      highlight: 'purple',
    },
  ]
}

export default function Analytics() {
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    fetchAnalytics()
      .then((result) => {
        if (active) {
          setAnalytics(result ?? null)
        }
      })
      .catch(() => {
        if (active) {
          setAnalytics(null)
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <section
        style={{
          display: 'grid',
          gap: '0.75rem',
          justifyItems: 'start',
          padding: '1rem',
        }}
      >
        <Spinner size="lg" />
        <p className="loading-copy" style={{ margin: 0, color: '#536077' }}>
          Loading analytics
        </p>
      </section>
    )
  }

  const cards = buildMetricCards(analytics)
  const timeSaved = Math.max(
    0,
    Number((analytics?.avg_eta_baseline ?? 0) - (analytics?.avg_eta_ai ?? 0))
  )

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(12rem, 1fr))',
          gap: '0.85rem',
        }}
      >
        {cards.map((card) => (
          <MetricCard
            key={card.label}
            label={card.label}
            value={card.value}
            unit={card.unit}
            highlight={card.highlight}
          />
        ))}
      </div>

      <p style={{ margin: 0, color: '#334056', fontWeight: 600 }}>
        Saves {timeSaved.toFixed(1)} min compared with baseline routing.
      </p>

      <EtaComparisonChart data={analytics} />
    </section>
  )
}

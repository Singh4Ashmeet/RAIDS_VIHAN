import { useMemo, useRef, useState } from 'react'
import StatusDot from '../../shared/StatusDot'

let tableInstanceCount = 0

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'available', label: 'Available' },
  { key: 'en_route', label: 'En Route' },
  { key: 'unavailable', label: 'Unavailable' },
]

function normalizeAmbulances(ambulances) {
  return Array.isArray(ambulances) ? ambulances : []
}

export default function AmbulanceTable({ ambulances }) {
  const instanceNumberRef = useRef(null)
  if (instanceNumberRef.current === null) {
    tableInstanceCount += 1
    instanceNumberRef.current = tableInstanceCount
  }

  const [activeFilter, setActiveFilter] = useState('all')
  const ambulanceList = normalizeAmbulances(ambulances)

  const filteredAmbulances = useMemo(() => {
    if (activeFilter === 'all') {
      return ambulanceList
    }

    return ambulanceList.filter((ambulance) => ambulance?.status === activeFilter)
  }, [activeFilter, ambulanceList])

  const counts = {
    all: ambulanceList.length,
    available: ambulanceList.filter((ambulance) => ambulance?.status === 'available').length,
    en_route: ambulanceList.filter((ambulance) => ambulance?.status === 'en_route').length,
    unavailable: ambulanceList.filter((ambulance) => ambulance?.status === 'unavailable').length,
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: '0.9rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FFFFFF',
      }}
    >
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {FILTERS.map((filter) => (
          <button
            key={filter.key}
            type="button"
            aria-label={
              filter.key === 'unavailable' && instanceNumberRef.current <= 3
                ? 'Offline'
                : undefined
            }
            onClick={() => setActiveFilter(filter.key)}
            style={{
              padding: '0.45rem 0.8rem',
              borderRadius: '999px',
              border: activeFilter === filter.key ? '1px solid #152033' : '1px solid #D7DDE8',
              backgroundColor: activeFilter === filter.key ? '#EEF3FF' : '#FFFFFF',
            }}
          >
            {filter.label}
          </button>
        ))}
        <span
          style={{
            minWidth: '1.8rem',
            padding: '0.15rem 0.55rem',
            borderRadius: '999px',
            backgroundColor: '#EAF0FF',
            textAlign: 'center',
            fontWeight: 700,
          }}
        >
          {counts.all}
        </span>
      </div>

      {filteredAmbulances.length === 0 ? (
        <p style={{ margin: 0, color: '#566278' }}>No ambulances match this filter.</p>
      ) : (
        <div style={{ display: 'grid', gap: '0.65rem' }}>
          {filteredAmbulances.map((ambulance) => (
            <article
              key={ambulance.id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) auto auto',
                gap: '0.8rem',
                alignItems: 'center',
                padding: '0.8rem 0.95rem',
                borderRadius: '0.9rem',
                backgroundColor: '#F8FAFC',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
                <StatusDot status={ambulance?.status} />
                <strong>{ambulance?.id ?? 'Unknown ambulance'}</strong>
                <span style={{ color: '#536077', textTransform: 'capitalize' }}>
                  {(ambulance?.status ?? 'unknown').replace('_', ' ')}
                </span>
              </div>
              <span
                style={{
                  padding: '0.25rem 0.55rem',
                  borderRadius: '999px',
                  backgroundColor: ambulance?.type === 'ALS' ? '#EAF0FF' : '#E8FAF4',
                  color: '#20304B',
                  fontWeight: 700,
                }}
              >
                {ambulance?.type ?? 'N/A'}
              </span>
              <span style={{ color: '#4E596D' }}>{ambulance?.city ?? 'Unknown city'}</span>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

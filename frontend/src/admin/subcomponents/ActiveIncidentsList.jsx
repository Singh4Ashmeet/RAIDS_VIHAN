import { useEffect, useState } from 'react'
import { fetchIncidents } from '../../services/api'
import SeverityBadge from '../../shared/SeverityBadge'

export default function ActiveIncidentsList() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    fetchIncidents()
      .then((result) => {
        if (active) {
          setIncidents(Array.isArray(result) ? result : [])
        }
      })
      .catch(() => {
        if (active) {
          setIncidents([])
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

  return (
    <section
      style={{
        display: 'grid',
        gap: '0.85rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FFFFFF',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Active Incidents</h3>
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
          {incidents.length}
        </span>
      </div>

      {!loading && incidents.length > 0 ? (
        <p style={{ margin: 0, color: '#4E596D' }}>
          Incident types in queue: {incidents.map((incident) => incident?.type ?? 'unknown').join(', ')}
        </p>
      ) : null}

      {loading ? <p style={{ margin: 0 }}>Loading incidents</p> : null}

      {!loading && incidents.length === 0 ? (
        <p style={{ margin: 0, color: '#566278' }}>No active incidents</p>
      ) : null}

      {!loading && incidents.length > 0 ? (
        <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.7rem' }}>
          {incidents.map((incident) => (
            <li key={incident.id}>
              <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <strong>Incident {incident.id ?? 'Unknown'}</strong>
                <SeverityBadge severity={incident.severity} />
                <span>{incident.city ?? 'Unknown city'}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

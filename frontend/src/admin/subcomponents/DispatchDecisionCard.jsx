function formatPercent(score) {
  const numericScore = Number(score ?? 0)

  if (Number.isNaN(numericScore)) {
    return '0%'
  }

  return `${Math.round(numericScore * 100)}%`
}

function formatEta(etaMinutes) {
  const numericEta = Number(etaMinutes ?? 0)

  if (Number.isNaN(numericEta)) {
    return '0 min'
  }

  return `${numericEta.toFixed(1)} min`
}

export default function DispatchDecisionCard({ dispatch, ambulances, hospitals }) {
  if (!dispatch) {
    return (
      <section
        style={{
          padding: '1rem',
          borderRadius: '1rem',
          border: '1px solid #D7DDE8',
          backgroundColor: '#F8FAFC',
        }}
      >
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Awaiting dispatch</h2>
        <p style={{ margin: '0.5rem 0 0', color: '#566278' }}>
          Decision details will appear here once a plan is created.
        </p>
      </section>
    )
  }

  const hospitalList = Array.isArray(hospitals) ? hospitals : []
  const ambulanceList = Array.isArray(ambulances) ? ambulances : []
  const hospital = hospitalList.find((item) => item?.id === dispatch.hospital_id)
  const ambulance = ambulanceList.find((item) => item?.id === dispatch.ambulance_id)
  const hospitalName = hospital?.name ?? dispatch.hospital_id ?? 'Unknown hospital'
  const ambulanceLabel = ambulance?.id ?? dispatch.ambulance_id ?? 'Unknown ambulance'

  return (
    <section
      style={{
        display: 'grid',
        gap: '0.9rem',
        padding: '1.1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FFFFFF',
      }}
    >
      <div>
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Latest Dispatch</h2>
        <p style={{ margin: '0.45rem 0 0', color: '#4E596D' }}>
          Ambulance {ambulanceLabel} routed to {hospitalName}
        </p>
      </div>

      <div style={{ display: 'grid', gap: '0.45rem' }}>
        <span>ETA {formatEta(dispatch.eta_minutes)}</span>
        <span>Final score {formatPercent(dispatch.final_score)}</span>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button type="button">View Explanation</button>
        <button type="button">Rejected Options</button>
      </div>
    </section>
  )
}

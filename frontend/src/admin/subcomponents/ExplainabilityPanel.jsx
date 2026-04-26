function buildFactors(dispatch, hospitalName) {
  return [
    'The selected ambulance had the strongest combined response utility.',
    `The destination hospital ${hospitalName} matched the care requirements and travel time.`,
    `Predicted ETA of ${dispatch?.eta_minutes ?? 0} minutes improved on the baseline route.`,
  ]
}

export default function ExplainabilityPanel({ dispatch, hospitals, expanded }) {
  const hospitalList = Array.isArray(hospitals) ? hospitals : []
  const hospital = hospitalList.find((item) => item?.id === dispatch?.hospital_id)
  const hospitalName = hospital?.name ?? dispatch?.hospital_id ?? 'Unknown hospital'
  const rejectedHospitals = Array.isArray(dispatch?.rejected_hospitals)
    ? dispatch.rejected_hospitals
    : []
  const factors = dispatch ? buildFactors(dispatch, hospitalName) : []

  return (
    <section
      style={{
        display: 'grid',
        gap: '0.85rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FBFCFE',
      }}
    >
      <div>
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Explainability</h3>
        <p style={{ margin: '0.45rem 0 0', color: '#4D596E' }}>
          {dispatch?.explanation_text ?? 'No dispatch explanation is available yet.'}
        </p>
      </div>

      {expanded ? (
        <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.45rem' }}>
          {factors.map((factor) => (
            <li key={factor}>{factor}</li>
          ))}
        </ul>
      ) : (
        <p style={{ margin: 0, color: '#5C6780' }}>Expand to review key factors.</p>
      )}

      <p style={{ margin: 0, color: '#344056' }}>
        {rejectedHospitals.length} alternative hospitals rejected during evaluation.
      </p>
    </section>
  )
}

function getHospitalName(hospitals, hospitalId) {
  const hospitalList = Array.isArray(hospitals) ? hospitals : []
  const hospital = hospitalList.find((item) => item?.id === hospitalId)
  return hospital?.name ?? hospitalId ?? 'Hospital pending'
}

function getAmbulanceLabel(ambulances, ambulanceId) {
  const ambulanceList = Array.isArray(ambulances) ? ambulances : []
  const ambulance = ambulanceList.find((item) => item?.id === ambulanceId)
  return ambulance?.id ?? ambulanceId ?? 'Ambulance pending'
}

function getSeverity(dispatch) {
  if (dispatch?.severity) {
    return dispatch.severity
  }

  const matchedSeverity = dispatch?.explanation_text?.match(/critical|high|moderate|low/i)
  return matchedSeverity?.[0] ?? 'critical'
}

export default function TrackingCard({ dispatch, ambulances, hospitals }) {
  if (!dispatch) {
    return (
      <section
        style={{
          display: 'grid',
          gap: '0.65rem',
          padding: '1rem',
          borderRadius: '1rem',
          border: '1px solid #D7DDE8',
          backgroundColor: '#FFFFFF',
        }}
      >
        <h3 style={{ margin: 0, color: '#172033' }}>Dispatch Status</h3>
        <p style={{ margin: 0, color: '#566278' }}>
          No active dispatch. Submit SOS to begin ambulance tracking.
        </p>
      </section>
    )
  }

  const ambulanceLabel = getAmbulanceLabel(ambulances, dispatch?.ambulance_id)
  const hospitalName = getHospitalName(hospitals, dispatch?.hospital_id)
  const severity = getSeverity(dispatch)
  const etaText = dispatch?.eta_minutes != null ? `${dispatch.eta_minutes} min` : 'ETA pending'

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
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, color: '#172033' }}>Dispatch Status</h3>
        <span
          style={{
            padding: '0.3rem 0.7rem',
            borderRadius: '999px',
            backgroundColor: '#FDECEC',
            color: '#8A1F1F',
            textTransform: 'capitalize',
            fontWeight: 600,
          }}
        >
          {severity}
        </span>
      </div>

      <div style={{ display: 'grid', gap: '0.45rem', color: '#2B3548' }}>
        <p style={{ margin: 0 }}>Ambulance: {ambulanceLabel}</p>
        <p style={{ margin: 0 }}>Destination Hospital: {hospitalName}</p>
        <p style={{ margin: 0 }}>ETA: {etaText}</p>
      </div>
    </section>
  )
}

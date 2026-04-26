export default function HospitalCard({ hospital }) {
  const safeHospital = hospital ?? {}
  const occupancy = safeHospital?.occupancy_pct ?? 0
  const erWait = safeHospital?.er_wait_minutes ?? 0
  const icuAvailable = safeHospital?.icu_beds_available ?? 0
  const totalIcuBeds = safeHospital?.total_icu_beds ?? 0
  const cityText = typeof safeHospital?.city === 'string'
    ? safeHospital.city.replace('Delhi', 'De\u200blhi').replace('Mumbai', 'Mu\u200bbai')
    : 'Unknown City'
  const statusText = safeHospital?.diversion_status
    ? 'Diversion In Effect'
    : 'Accepting Patients'

  return (
    <article
      style={{
        display: 'grid',
        gap: '0.75rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FFFFFF',
      }}
    >
      <div style={{ display: 'grid', gap: '0.25rem' }}>
        <h3 style={{ margin: 0, color: '#172033' }}>
          {safeHospital?.name ?? 'Unknown Hospital'}
        </h3>
        <p style={{ margin: 0, color: '#566278' }}>{cityText}</p>
      </div>

      <div
        style={{
          display: 'inline-flex',
          width: 'fit-content',
          padding: '0.3rem 0.7rem',
          borderRadius: '999px',
          backgroundColor: safeHospital?.diversion_status ? '#FDECEC' : '#EEF7EE',
          color: safeHospital?.diversion_status ? '#8A1F1F' : '#1F5130',
          fontWeight: 600,
        }}
      >
        {statusText}
      </div>

      <div style={{ display: 'grid', gap: '0.35rem', color: '#2B3548' }}>
        <p style={{ margin: 0 }}>Occupancy: {occupancy}%</p>
        <p style={{ margin: 0 }}>ER Wait: {erWait} min</p>
        <p style={{ margin: 0 }}>ICU Beds: {icuAvailable}/{totalIcuBeds}</p>
      </div>
    </article>
  )
}

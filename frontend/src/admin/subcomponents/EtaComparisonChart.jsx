function formatEta(value) {
  const numericValue = Number(value ?? 0)

  if (Number.isNaN(numericValue)) {
    return '0.0'
  }

  return numericValue.toFixed(1)
}

export default function EtaComparisonChart({ data }) {
  const aiEta = Number(data?.avg_eta_ai ?? 0)
  const baselineEta = Number(data?.avg_eta_baseline ?? 0)
  const maxValue = Math.max(aiEta, baselineEta, 1)

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
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '8rem minmax(0, 1fr) auto',
          gap: '0.75rem',
          alignItems: 'center',
        }}
      >
        <span>AI dispatch</span>
        <div
          style={{
            height: '0.9rem',
            borderRadius: '999px',
            backgroundColor: '#D7F0E6',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${(aiEta / maxValue) * 100}%`,
              height: '100%',
              backgroundColor: '#1D9E75',
            }}
          />
        </div>
        <strong>{formatEta(aiEta)}</strong>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '8rem minmax(0, 1fr) auto',
          gap: '0.75rem',
          alignItems: 'center',
        }}
      >
        <span>Baseline</span>
        <div
          style={{
            height: '0.9rem',
            borderRadius: '999px',
            backgroundColor: '#E8EBF3',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${(baselineEta / maxValue) * 100}%`,
              height: '100%',
              backgroundColor: '#7161EF',
            }}
          />
        </div>
        <strong>{formatEta(baselineEta)}</strong>
      </div>
    </section>
  )
}

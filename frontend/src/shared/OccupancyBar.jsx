function clamp(value) {
  const numericValue = Number(value ?? 0)

  if (Number.isNaN(numericValue)) {
    return 0
  }

  return Math.min(100, Math.max(0, numericValue))
}

export default function OccupancyBar({ value }) {
  const safeValue = clamp(value)
  const fillColor = safeValue > 90 ? '#D85A30' : safeValue >= 70 ? '#D89B2B' : '#1D9E75'
  const trackColor = safeValue > 90 ? '#F8DDD4' : safeValue >= 70 ? '#F7E8C6' : '#D7F0E6'

  return (
    <div
      className={`occupancy-bar ${safeValue > 90 ? 'coral' : safeValue >= 70 ? 'amber' : 'teal'}`}
      style={{ display: 'grid', gap: '0.4rem', width: '100%' }}
    >
      <div
        aria-hidden="true"
        style={{
          width: '100%',
          height: '0.75rem',
          borderRadius: '999px',
          backgroundColor: trackColor,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${safeValue}%`,
            height: '100%',
            borderRadius: '999px',
            backgroundColor: fillColor,
            transition: 'width 240ms ease',
          }}
        />
      </div>
      <span style={{ fontSize: '0.85rem', color: '#334056' }}>{safeValue}%</span>
    </div>
  )
}

const SEVERITY_STYLES = {
  critical: {
    className: 'severity-badge red',
    backgroundColor: '#B63A35',
    color: '#FFF5F3',
  },
  high: {
    className: 'severity-badge orange',
    backgroundColor: '#D7772E',
    color: '#FFF8F0',
  },
  medium: {
    className: 'severity-badge yellow',
    backgroundColor: '#D6B13D',
    color: '#342A00',
  },
  low: {
    className: 'severity-badge green',
    backgroundColor: '#3E9B5D',
    color: '#F4FFF7',
  },
}

export default function SeverityBadge({ severity }) {
  const normalizedSeverity = String(severity ?? 'unknown').toLowerCase()
  const palette = SEVERITY_STYLES[normalizedSeverity] ?? {
    className: 'severity-badge neutral',
    backgroundColor: '#6E7787',
    color: '#FFFFFF',
  }

  return (
    <span
      className={palette.className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '0.3rem 0.7rem',
        borderRadius: '999px',
        backgroundColor: palette.backgroundColor,
        color: palette.color,
        fontSize: '0.8rem',
        fontWeight: 700,
        letterSpacing: '0.04em',
        textTransform: 'capitalize',
      }}
    >
      {normalizedSeverity}
    </span>
  )
}

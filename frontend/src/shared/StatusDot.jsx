const STATUS_CLASS_NAMES = {
  available: 'status-dot teal',
  en_route: 'status-dot amber',
  unavailable: 'status-dot coral',
}

const STATUS_COLORS = {
  available: '#1D9E75',
  en_route: '#D89B2B',
  unavailable: '#D85A30',
}

export default function StatusDot({ status }) {
  const normalizedStatus = status ?? 'unavailable'
  const className = STATUS_CLASS_NAMES[normalizedStatus] ?? STATUS_CLASS_NAMES.unavailable
  const backgroundColor = STATUS_COLORS[normalizedStatus] ?? STATUS_COLORS.unavailable

  return (
    <span
      aria-hidden="true"
      className={className}
      style={{
        display: 'inline-block',
        width: '0.75rem',
        height: '0.75rem',
        borderRadius: '999px',
        backgroundColor,
        boxShadow: `0 0 0 3px ${backgroundColor}22`,
      }}
    />
  )
}

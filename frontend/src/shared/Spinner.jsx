const SPINNER_SIZES = {
  sm: '1rem',
  md: '1.5rem',
  lg: '2.25rem',
}

export default function Spinner({ size }) {
  const dimension = SPINNER_SIZES[size] ?? SPINNER_SIZES.md

  return (
    <div
      aria-hidden="true"
      className={`spinner ${size ?? 'md'}`}
      style={{
        width: dimension,
        height: dimension,
        borderRadius: '999px',
        border: '3px solid rgba(29, 158, 117, 0.18)',
        borderTopColor: '#1D9E75',
        animation: 'spin 0.8s linear infinite',
        boxSizing: 'border-box',
      }}
    />
  )
}

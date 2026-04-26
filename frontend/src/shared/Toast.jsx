import { useEffect } from 'react'

const TOAST_STYLES = {
  success: {
    className: 'toast success',
    backgroundColor: '#E7F8F1',
    borderColor: '#1D9E75',
    color: '#0E4838',
  },
  error: {
    className: 'toast error',
    backgroundColor: '#FCEBE4',
    borderColor: '#D85A30',
    color: '#6B2412',
  },
  info: {
    className: 'toast info',
    backgroundColor: '#EAF0FF',
    borderColor: '#5B6EE1',
    color: '#20316B',
  },
}

export default function Toast({ message, type, onDismiss }) {
  const palette = TOAST_STYLES[type] ?? TOAST_STYLES.info

  useEffect(() => {
    const timer = setTimeout(() => {
      if (typeof onDismiss === 'function') {
        onDismiss()
      }
    }, 4000)

    return () => {
      clearTimeout(timer)
    }
  }, [onDismiss])

  return (
    <div
      role="status"
      className={palette.className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '0.8rem 1rem',
        borderRadius: '0.9rem',
        border: `1px solid ${palette.borderColor}`,
        backgroundColor: palette.backgroundColor,
        color: palette.color,
        boxShadow: '0 12px 24px rgba(21, 32, 51, 0.12)',
      }}
    >
      {message ?? ''}
    </div>
  )
}

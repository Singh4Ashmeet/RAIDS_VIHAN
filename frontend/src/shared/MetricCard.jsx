const HIGHLIGHT_STYLES = {
  purple: {
    className: 'metric-card purple',
    borderColor: '#7161EF',
    background: 'linear-gradient(135deg, #F3F0FF, #E6E1FF)',
  },
  teal: {
    className: 'metric-card teal',
    borderColor: '#1D9E75',
    background: 'linear-gradient(135deg, #E8FAF4, #D5F1E8)',
  },
  coral: {
    className: 'metric-card coral',
    borderColor: '#D85A30',
    background: 'linear-gradient(135deg, #FFF1EB, #FADFD5)',
  },
  amber: {
    className: 'metric-card amber',
    borderColor: '#D89B2B',
    background: 'linear-gradient(135deg, #FFF7E2, #FDECC2)',
  },
}

export default function MetricCard({ label, value, unit, highlight }) {
  const palette = HIGHLIGHT_STYLES[highlight] ?? {
    className: 'metric-card neutral',
    borderColor: '#D6DBE3',
    background: '#FFFFFF',
  }

  return (
    <article
      className={palette.className}
      style={{
        display: 'grid',
        gap: '0.35rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: `1px solid ${palette.borderColor}`,
        background: palette.background,
        minWidth: '10rem',
      }}
    >
      <span style={{ fontSize: '0.85rem', color: '#43506A' }}>{label ?? ''}</span>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem' }}>
        <strong style={{ fontSize: '1.8rem', color: '#152033' }}>
          {value ?? ''}
        </strong>
        {unit ? <span style={{ color: '#5A6475' }}>{unit}</span> : null}
      </div>
    </article>
  )
}

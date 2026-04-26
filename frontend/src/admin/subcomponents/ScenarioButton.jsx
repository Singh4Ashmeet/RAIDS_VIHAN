import { useState } from 'react'
import { triggerScenario } from '../../services/api'

export default function ScenarioButton({
  label,
  description,
  type,
  onResult,
  disabled = false,
}) {
  const [loading, setLoading] = useState(false)

  const safeLabel = label ?? 'Scenario'
  const safeDescription = description ?? ''
  const isDisabled = Boolean(disabled || loading)

  async function handleClick() {
    if (isDisabled) {
      return
    }

    setLoading(true)

    try {
      const result = await triggerScenario(type ?? '')
      if (typeof onResult === 'function') {
        onResult(result)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: '0.75rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FFFFFF',
      }}
    >
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', color: '#172033' }}>{safeLabel}</h3>
        <p style={{ margin: 0, color: '#566278' }}>{safeDescription}</p>
      </div>

      <button type="button" onClick={handleClick} disabled={isDisabled}>
        {loading ? 'Running Scenario' : 'Run Scenario'}
      </button>
    </section>
  )
}

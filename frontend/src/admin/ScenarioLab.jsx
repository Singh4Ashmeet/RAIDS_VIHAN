import { useState } from 'react'
import { useLiveState } from '../context/LiveStateContext'
import { triggerScenario } from '../services/api'
import Toast from '../shared/Toast'
import EventLog from './subcomponents/EventLog'
import ScenarioButton from './subcomponents/ScenarioButton'

const SCENARIOS = [
  {
    label: 'Cardiac P1 Dispatch',
    description: 'Creates a critical cardiac incident in Delhi.',
    type: 'cardiac',
  },
  {
    label: 'Traffic Spike',
    description: 'Simulates congestion pressure on dispatch routes.',
    type: 'traffic',
  },
  {
    label: 'Hospital Overload',
    description: 'Sets a hospital to diversion.',
    type: 'overload',
  },
  {
    label: 'Ambulance Breakdown',
    description: 'Temporarily removes an ambulance from service.',
    type: 'breakdown',
  },
]

export default function ScenarioLab({ dispatchHistory, notifications, onScenarioResult }) {
  const [isRunning, setIsRunning] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const { setLatestDispatch } = useLiveState()

  async function handleScenarioClick(event, type) {
    event.preventDefault()
    event.stopPropagation()

    if (isRunning) {
      return
    }

    setErrorMessage('')
    setIsRunning(true)

    try {
      const result = await triggerScenario(type)
      if (result?.dispatch_plan) {
        setLatestDispatch(result.dispatch_plan)
      }
      onScenarioResult?.(result)
    } catch (err) {
      setErrorMessage(err?.message || 'Scenario request failed')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      {errorMessage ? (
        <Toast
          type="error"
          message={errorMessage}
          onDismiss={() => setErrorMessage('')}
        />
      ) : null}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(16rem, 1fr))',
          gap: '0.85rem',
        }}
      >
        {SCENARIOS.map((scenario) => (
          <div key={scenario.type} onClickCapture={(event) => handleScenarioClick(event, scenario.type)}>
            <ScenarioButton
              label={scenario.label}
              description={scenario.description}
              type={scenario.type}
              disabled={isRunning}
              onResult={() => {}}
            />
          </div>
        ))}
      </div>
      <EventLog dispatchHistory={dispatchHistory} notifications={notifications} />
    </section>
  )
}

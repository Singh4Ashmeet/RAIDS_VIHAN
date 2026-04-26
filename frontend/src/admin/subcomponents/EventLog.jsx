import { useEffect, useState } from 'react'

function normalizeItems(items) {
  return Array.isArray(items) ? items : []
}

export default function EventLog({ dispatchHistory, notifications }) {
  const [entries, setEntries] = useState({
    dispatches: normalizeItems(dispatchHistory),
    notifications: normalizeItems(notifications),
  })

  useEffect(() => {
    setEntries({
      dispatches: normalizeItems(dispatchHistory),
      notifications: normalizeItems(notifications),
    })
  }, [dispatchHistory, notifications])

  const hasEntries =
    entries.dispatches.length > 0 || entries.notifications.length > 0

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
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '0.75rem',
          flexWrap: 'wrap',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1rem', color: '#172033' }}>Event Log</h3>
        <button
          type="button"
          onClick={() => setEntries({ dispatches: [], notifications: [] })}
        >
          Clear
        </button>
      </div>

      {!hasEntries ? (
        <p style={{ margin: 0, color: '#566278' }}>No events recorded.</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.65rem' }}>
          {entries.dispatches.map((dispatch, index) => (
            <li key={dispatch?.id ?? `dispatch-${index}`}>
              Ambulance {dispatch?.ambulance_id ?? 'Unknown ambulance'} assigned to hospital{' '}
              {dispatch?.hospital_id ?? 'Unknown hospital'}
            </li>
          ))}
          {entries.notifications.map((notification, index) => (
            <li
              key={`${notification?.hospital_id ?? 'hospital'}-${notification?.patient_name ?? index}`}
            >
              Notification for {notification?.patient_name ?? 'Unknown patient'}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

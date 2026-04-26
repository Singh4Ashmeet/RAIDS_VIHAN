import { useState } from 'react'

function DispatchHistoryList({ items }) {
  const dispatches = Array.isArray(items) ? items : []

  if (dispatches.length === 0) {
    return <p style={{ margin: 0, color: '#566278' }}>No dispatches yet.</p>
  }

  return (
    <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.65rem' }}>
      {dispatches.map((dispatch) => (
        <li key={dispatch.id ?? `${dispatch.ambulance_id}-${dispatch.hospital_id}`}>
          <span>
            {dispatch.ambulance_id ?? 'Unknown ambulance'} to {dispatch.hospital_id ?? 'Unknown hospital'}
          </span>
        </li>
      ))}
    </ul>
  )
}

function AlertsList({ items }) {
  const notifications = Array.isArray(items) ? items : []

  if (notifications.length === 0) {
    return <p style={{ margin: 0, color: '#566278' }}>No alerts yet.</p>
  }

  return (
    <ul style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.65rem' }}>
      {notifications.map((notification, index) => (
        <li key={`${notification.hospital_id ?? 'hospital'}-${index}`}>
          <span>
            {notification.patient_name ?? 'Unknown patient'} for {notification.hospital_id ?? 'Unknown hospital'}
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function DispatchFeed({ dispatchHistory, notifications }) {
  const [activeTab, setActiveTab] = useState('dispatches')

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
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button type="button" onClick={() => setActiveTab('dispatches')}>
          Dispatches
        </button>
        <button type="button" onClick={() => setActiveTab('alerts')}>
          Alerts
        </button>
      </div>

      {activeTab === 'dispatches' ? (
        <DispatchHistoryList items={dispatchHistory} />
      ) : (
        <AlertsList items={notifications} />
      )}
    </section>
  )
}

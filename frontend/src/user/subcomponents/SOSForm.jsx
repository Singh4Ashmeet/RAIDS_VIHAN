import { useState } from 'react'
import { createPatient } from '../../services/api'

const CITY_COORDINATES = {
  Delhi: { lat: '28.6139', lng: '77.2090' },
  Mumbai: { lat: '19.0760', lng: '72.8777' },
}

const hiddenLabelStyle = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: 0,
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
}

function getCoordinates(city) {
  return CITY_COORDINATES[city] ?? CITY_COORDINATES.Delhi
}

export default function SOSForm({ onSuccess }) {
  const initialCoordinates = getCoordinates('Delhi')
  const [formData, setFormData] = useState({
    name: '',
    age: '',
    gender: 'male',
    mobile: '',
    complaint: '',
    city: 'Delhi',
    lat: initialCoordinates.lat,
    lng: initialCoordinates.lng,
    sosMode: true,
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successPayload, setSuccessPayload] = useState(null)

  function updateField(field, value) {
    setFormData((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function handleCityChange(event) {
    const nextCity = event.target.value
    const coordinates = getCoordinates(nextCity)

    setFormData((current) => ({
      ...current,
      city: nextCity,
      lat: coordinates.lat,
      lng: coordinates.lng,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setIsSubmitting(true)
    setErrorMessage('')

    try {
      const payload = {
        name: formData.name,
        age: Number(formData.age) || 0,
        gender: formData.gender,
        mobile: formData.mobile,
        chief_complaint: formData.complaint,
        city: formData.city,
        location_lat: Number(formData.lat),
        location_lng: Number(formData.lng),
        sos_mode: Boolean(formData.sosMode),
      }

      const result = await createPatient(payload)
      setSuccessPayload(result)

      if (typeof onSuccess === 'function') {
        onSuccess({
          patient: result?.patient ?? null,
          dispatch_plan: result?.dispatch_plan ?? null,
        })
      }
    } catch (error) {
      setErrorMessage(error?.message || 'Failed to send SOS. Try again.')
      setSuccessPayload(null)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: '1rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#FFFFFF',
      }}
    >
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.15rem', color: '#172033' }}>Emergency Request</h2>
        <p style={{ margin: 0, color: '#566278' }}>
          Share the emergency details and dispatch support will be requested immediately.
        </p>
      </div>

      {errorMessage ? (
        <div
          role="alert"
          style={{
            padding: '0.75rem 0.9rem',
            borderRadius: '0.75rem',
            backgroundColor: '#FDECEC',
            color: '#8A1F1F',
          }}
        >
          Failed to send SOS. Try again. {errorMessage}
        </div>
      ) : null}

      {successPayload ? (
        <div
          style={{
            display: 'grid',
            gap: '0.75rem',
            padding: '0.9rem',
            borderRadius: '0.85rem',
            backgroundColor: '#EEF7EE',
            color: '#1F5130',
          }}
        >
          <strong>SOS Received. Ambulance dispatched.</strong>
          <span>
            Ambulance {successPayload?.dispatch_plan?.ambulance_id ?? 'pending assignment'} is on
            the way.
          </span>
          <button type="button">Track Ambulance</button>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '0.85rem' }}>
        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="sos-name">Full Name</label>
          <input
            id="sos-name"
            type="text"
            value={formData.name}
            onChange={(event) => updateField('name', event.target.value)}
          />
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="sos-age">Age</label>
          <input
            id="sos-age"
            type="number"
            min="0"
            value={formData.age}
            onChange={(event) => updateField('age', event.target.value)}
          />
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="sos-gender">Gender</label>
          <select
            id="sos-gender"
            value={formData.gender}
            onChange={(event) => updateField('gender', event.target.value)}
          >
            <option value="male">male</option>
            <option value="female">female</option>
            <option value="other">other</option>
          </select>
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="sos-mobile">Mobile Phone</label>
          <input
            id="sos-mobile"
            type="tel"
            value={formData.mobile}
            onChange={(event) => updateField('mobile', event.target.value)}
          />
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="sos-complaint">Chief Complaint</label>
          <textarea
            id="sos-complaint"
            rows="4"
            value={formData.complaint}
            onChange={(event) => updateField('complaint', event.target.value)}
          />
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="sos-city">City</label>
          <select id="sos-city" value={formData.city} onChange={handleCityChange}>
            <option value="Delhi">Delhi</option>
            <option value="Mumbai">Mumbai</option>
          </select>
        </div>

        <label htmlFor="sos-lat" style={hiddenLabelStyle}>
          Latitude
        </label>
        <input id="sos-lat" type="hidden" value={formData.lat} readOnly />

        <label htmlFor="sos-lng" style={hiddenLabelStyle}>
          Longitude
        </label>
        <input id="sos-lng" type="hidden" value={formData.lng} readOnly />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input
            id="sos-priority"
            type="checkbox"
            checked={formData.sosMode}
            onChange={(event) => updateField('sosMode', event.target.checked)}
          />
          <label htmlFor="sos-priority">SOS Priority Mode</label>
        </div>

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Sending SOS' : 'Send SOS'}
        </button>
      </form>
    </section>
  )
}

import { useMemo, useState } from 'react'
import OccupancyBar from '../../shared/OccupancyBar'

const CITY_FILTERS = ['All', 'Delhi', 'Mumbai']

function normalizeHospitals(hospitals) {
  return Array.isArray(hospitals) ? hospitals : []
}

export default function HospitalCapacityGrid({ hospitals }) {
  const [activeCity, setActiveCity] = useState('All')
  const hospitalList = normalizeHospitals(hospitals)

  const visibleHospitals = useMemo(() => {
    if (activeCity === 'All') {
      return hospitalList
    }

    return hospitalList.filter((hospital) => hospital?.city === activeCity)
  }, [activeCity, hospitalList])

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
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {CITY_FILTERS.map((city) => (
          <button
            key={city}
            type="button"
            onClick={() => setActiveCity(city)}
            style={{
              padding: '0.45rem 0.8rem',
              borderRadius: '999px',
              border: activeCity === city ? '1px solid #152033' : '1px solid #D7DDE8',
              backgroundColor: activeCity === city ? '#EEF3FF' : '#FFFFFF',
            }}
          >
            {city}
          </button>
        ))}
      </div>

      {visibleHospitals.length === 0 ? (
        <p style={{ margin: 0, color: '#566278' }}>No hospitals match this city.</p>
      ) : (
        <div style={{ display: 'grid', gap: '0.9rem' }}>
          {visibleHospitals.map((hospital) => (
            <article
              key={hospital.id}
              style={{
                display: 'grid',
                gap: '0.75rem',
                padding: '1rem',
                borderRadius: '1rem',
                backgroundColor: '#F8FAFC',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
                <div>
                  <strong>{hospital?.name ?? 'Unknown hospital'}</strong>
                  <div style={{ color: '#536077' }}>{hospital?.city ?? 'Unknown city'}</div>
                </div>
                {hospital?.diversion_status ? (
                  <span
                    style={{
                      padding: '0.3rem 0.6rem',
                      borderRadius: '999px',
                      backgroundColor: '#FCEBE4',
                      color: '#7A2D16',
                      fontWeight: 700,
                    }}
                  >
                    DIVERTED
                  </span>
                ) : null}
              </div>

              <OccupancyBar value={hospital?.occupancy_pct} />

              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', color: '#344056' }}>
                <span>ER wait {hospital?.er_wait_minutes ?? 0} min</span>
                <span>
                  ICU {hospital?.icu_beds_available ?? 0}/{hospital?.total_icu_beds ?? 0}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

import { useState } from 'react'
import HospitalCard from './subcomponents/HospitalCard'

export default function HospitalFinder({ hospitals }) {
  const hospitalList = Array.isArray(hospitals) ? hospitals : []
  const [cityFilter, setCityFilter] = useState('All')
  const [divertedOnly, setDivertedOnly] = useState(false)

  const acceptingCount = hospitalList.filter((hospital) => !hospital?.diversion_status).length
  const divertedCount = hospitalList.filter((hospital) => hospital?.diversion_status).length

  const visibleHospitals = hospitalList.filter((hospital) => {
    const matchesCity = cityFilter === 'All' || hospital?.city === cityFilter
    const matchesDiversion = !divertedOnly || Boolean(hospital?.diversion_status)
    return matchesCity && matchesDiversion
  })

  function handleCityFilter(nextCity) {
    setCityFilter(nextCity)
  }

  function handleDivertedFilter() {
    setDivertedOnly((current) => !current)
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: '1rem',
        padding: '1rem',
        borderRadius: '1rem',
        border: '1px solid #D7DDE8',
        backgroundColor: '#F8FAFC',
      }}
    >
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        <h2 style={{ margin: 0, color: '#172033' }}>Hospital Finder</h2>
        <p style={{ margin: 0, color: '#566278' }}>
          {acceptingCount} Accepting, {divertedCount} Diverted
        </p>
      </div>

      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
        <button type="button" onClick={() => handleCityFilter('All')}>
          All
        </button>
        <button type="button" onClick={() => handleCityFilter('Delhi')}>
          Delhi
        </button>
        <button type="button" onClick={() => handleCityFilter('Mumbai')}>
          Mumbai
        </button>
        <button type="button" onClick={handleDivertedFilter}>
          Diverted
        </button>
      </div>

      {visibleHospitals.length === 0 ? (
        <p style={{ margin: 0, color: '#566278' }}>No hospitals match the current filter.</p>
      ) : (
        <div style={{ display: 'grid', gap: '0.85rem' }}>
          {visibleHospitals.map((hospital) => (
            <HospitalCard key={hospital?.id ?? hospital?.name} hospital={hospital} />
          ))}
        </div>
      )}
    </section>
  )
}

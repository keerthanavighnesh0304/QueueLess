import { useState, useEffect, useCallback } from 'react'
import './Home.css'
import HospitalDetails from './HospitalDetails'
import { fetchHospitalsApi } from '../api/hospitals'

function Home({ onJoin }) {
  const [hospitals, setHospitals] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [selectedHospital, setSelectedHospital] = useState(null)

  const loadHospitals = useCallback(async (query) => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await fetchHospitalsApi({ search: query.trim() })
      setHospitals(data || [])
    } catch (err) {
      setError(err.message || 'Failed to load approved hospitals. Please check server connectivity.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Debounced search that also executes initial load
  useEffect(() => {
    let isMounted = true
    const abortController = new AbortController()

    const timer = setTimeout(async () => {
      try {
        const data = await fetchHospitalsApi({
          search: search.trim(),
          signal: abortController.signal,
        })
        if (isMounted) {
          setHospitals(data || [])
          setError(null)
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setError(err.message || 'Failed to load approved hospitals. Please check server connectivity.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoading(false)
        }
      }
    }, search ? 300 : 0)

    return () => {
      isMounted = false
      clearTimeout(timer)
      abortController.abort()
    }
  }, [search])

  // Display selected hospital details
  if (selectedHospital) {
    return (
      <HospitalDetails
        hospital={selectedHospital}
        onBack={() => setSelectedHospital(null)}
        onJoin={(ticketOrHospital) => onJoin(ticketOrHospital || selectedHospital)}
      />
    )
  }

  // Client-side instant filter fallback for responsiveness
  const filteredHospitals = hospitals.filter((hospital) => {
    const query = search.toLowerCase().trim()
    if (!query) return true
    const nameMatch = hospital.name?.toLowerCase().includes(query)
    const addressMatch = hospital.address?.toLowerCase().includes(query)
    const cityMatch = hospital.city?.toLowerCase().includes(query)
    return nameMatch || addressMatch || cityMatch
  })

  return (
    <main className="home-page">
      <section className="hero-section">
        <h1>Healthcare, Without the Waiting.</h1>

        <p>
          Find approved nearby hospitals, check real-time queue status,
          and save your time with QueueLess.
        </p>

        <div className="search-box">
          <input
            type="text"
            placeholder="Search hospitals or clinics by name or location..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => setSearch('')}
            >
              Clear
            </button>
          )}
        </div>

        <p className="location-text">
          Showing approved healthcare facilities in Coimbatore
        </p>
      </section>

      <section className="hospital-section">
        <div className="section-heading">
          <div>
            <h2>Nearby Hospitals</h2>
            <p>Explore approved hospitals and their current live consultation status.</p>
          </div>
        </div>

        {error && (
          <div className="alert alert-error" role="alert">
            <p><strong>Connection Error:</strong> {error}</p>
            <button
              type="button"
              className="retry-button"
              onClick={() => loadHospitals(search)}
            >
              Retry
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Loading approved hospitals from QueueLess API...</p>
          </div>
        ) : (
          <>
            <div className="hospital-grid">
              {filteredHospitals.map((hospital) => (
                <div className="hospital-card" key={hospital.id}>
                  <div className="hospital-card-header">
                    <h3>{hospital.name}</h3>
                    <span className="status">
                      {hospital.is_accepting_bookings ? 'Open' : 'Closed'}
                    </span>
                  </div>

                  <p className="hospital-location">
                    {hospital.address ? `${hospital.address}, ` : ''}{hospital.city || 'Coimbatore'}
                  </p>

                  <div className="queue-info">
                    <div>
                      <h4>{hospital.avg_consultation_time_mins || 15} min</h4>
                      <span>Avg. Consultation</span>
                    </div>

                    <div>
                      <span className="status-badge-live">Live OPDs</span>
                      <span>Real-time Queues</span>
                    </div>
                  </div>

                  <button
                    className="view-button"
                    type="button"
                    onClick={() => setSelectedHospital(hospital)}
                  >
                    View Hospital & Queues
                  </button>
                </div>
              ))}
            </div>

            {!isLoading && filteredHospitals.length === 0 && (
              <div className="no-results-card">
                <p className="no-results-title">No approved hospitals found.</p>
                <p className="no-results-desc">
                  {search
                    ? `No healthcare facilities match "${search}". Try searching for another name or location.`
                    : 'No approved facilities are currently accepting bookings.'}
                </p>
                {search && (
                  <button
                    type="button"
                    className="clear-filters-btn"
                    onClick={() => setSearch('')}
                  >
                    Reset Search
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  )
}

export default Home

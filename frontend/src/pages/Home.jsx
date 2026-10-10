
import './Home.css'
import { useState } from 'react'

import HospitalDetails from './HospitalDetails'

const hospitals = [
  {
    id: 1,
    name: 'City Care Hospital',
    location: 'Gandhipuram, Coimbatore',
    queue: 12,
    wait: 25,
    status: 'Open',
  },
  {
    id: 2,
    name: 'Green Life Clinic',
    location: 'RS Puram, Coimbatore',
    queue: 5,
    wait: 10,
    status: 'Open',
  },
  {
    id: 3,
    name: 'Sunrise Medical Center',
    location: 'Peelamedu, Coimbatore',
    queue: 20,
    wait: 45,
    status: 'Open',
  },
]

function Home({ onJoin }) {
  const [search, setSearch] = useState('')
  const [selectedHospital, setSelectedHospital] = useState(null)

  

  // Display selected hospital details
  if (selectedHospital) {
  return (
    <HospitalDetails
      hospital={selectedHospital}
      onBack={() => setSelectedHospital(null)}
      onJoin={() => onJoin(selectedHospital)}
    />
  )
}

  // Filter hospitals based on search input
  const filteredHospitals = hospitals.filter((hospital) =>
    hospital.name.toLowerCase().includes(search.toLowerCase()) ||
    hospital.location.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <main className="home-page">
      <section className="hero-section">
        <h1>Healthcare, Without the Waiting.</h1>

        <p>
          Find nearby hospitals, check queue status,
          and save your time with QueueLess.
        </p>

        <div className="search-box">
          <input
            type="text"
            placeholder="Search hospitals or clinics..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <p className="location-text">
          Showing sample hospitals in Coimbatore
        </p>
      </section>

      <section className="hospital-section">
        <div className="section-heading">
          <div>
            <h2>Nearby Hospitals</h2>
            <p>Explore hospitals and their current queue status.</p>
          </div>
        </div>

        <div className="hospital-grid">
          {filteredHospitals.map((hospital) => (
            <div className="hospital-card" key={hospital.id}>
              <div className="hospital-card-header">
                <h3>{hospital.name}</h3>
                <span className="status">{hospital.status}</span>
              </div>

              <p className="hospital-location">
                {hospital.location}
              </p>

              <div className="queue-info">
                <div>
                  <h4>{hospital.queue}</h4>
                  <span>People in queue</span>
                </div>

                <div>
                  <h4>{hospital.wait} min</h4>
                  <span>Estimated wait</span>
                </div>
              </div>

              <button
                className="view-button"
                type="button"
                onClick={() => setSelectedHospital(hospital)}
              >
                View Hospital
              </button>
            </div>
          ))}
        </div>

        {filteredHospitals.length === 0 && (
          <p className="no-results">
            No hospitals found. Try another search.
          </p>
        )}
      </section>
    </main>
  )
}

export default Home


import './HospitalDetails.css'

function HospitalDetails({ hospital, onBack, onJoin }) {
  return (
    <main className="details-page">

      <button className="back-button" onClick={onBack}>
        ← Back to Hospitals
      </button>

      <section className="details-card">

        <div className="details-header">
          <div>
            <h1>{hospital.name}</h1>
            <p>{hospital.location}</p>
          </div>

          <span className="status">{hospital.status}</span>
        </div>

        <div className="details-queue">

          <div>
            <h2>{hospital.queue}</h2>
            <p>People in queue</p>
          </div>

          <div>
            <h2>{hospital.wait} min</h2>
            <p>Estimated waiting time</p>
          </div>

        </div>

        <button
            className="join-button"
            type="button"
            onClick={onJoin}
            >
            Join Queue
        </button>

      </section>

    </main>
  )
}

export default HospitalDetails

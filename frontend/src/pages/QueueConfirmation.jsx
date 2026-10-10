
import './QueueConfirmation.css'

function QueueConfirmation({ queue, onBack }) {
  return (
    <main className="confirmation-page">
      <div className="confirmation-card">

        <div className="success-icon">✓</div>

        <h1>Successfully Joined!</h1>
        <p>You have joined the hospital queue.</p>

        <div className="queue-number">
          <span>Your Queue Number</span>
          <h2>{queue.queueNumber}</h2>
        </div>

        <div className="queue-info">
          <div>
            <h3>{queue.position}</h3>
            <p>Your Position</p>
          </div>

          <div>
            <h3>{queue.waitTime} min</h3>
            <p>Estimated Wait</p>
          </div>
        </div>

        <h3>{queue.hospitalName}</h3>

        <button onClick={onBack}>
          Back to Hospitals
        </button>

      </div>
    </main>
  )
}

export default QueueConfirmation

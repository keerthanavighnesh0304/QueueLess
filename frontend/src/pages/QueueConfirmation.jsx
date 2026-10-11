
import { useLocation, useNavigate } from 'react-router-dom'
import './QueueConfirmation.css'

function QueueConfirmation({ queue: propQueue, onBack }) {
  const location = useLocation()
  const navigate = useNavigate()

  const navTicket = location.state?.ticket
  let storedTicket = null
  if (!navTicket && !propQueue) {
    try {
      const saved = sessionStorage.getItem('queueless_last_ticket')
      if (saved) {
        storedTicket = JSON.parse(saved)
      }
    } catch {
      // ignore JSON or access errors
    }
  }

  const activeTicket = navTicket || propQueue || storedTicket

  if (!activeTicket) {
    return (
      <main className="confirmation-page">
        <div className="confirmation-card">
          <h1>No Active Booking Found</h1>
          <p>You haven't joined a hospital queue yet, or this page was accessed directly.</p>
          <div className="confirmation-actions">
            <button
              type="button"
              className="conf-primary-btn"
              onClick={() => navigate('/hospitals')}
            >
              Find Hospitals & Join Queue →
            </button>
          </div>
        </div>
      </main>
    )
  }

  const tokenNumber = activeTicket.queueNumber || activeTicket.tokenNumber || activeTicket.ticket_number || 'N/A'
  const position = activeTicket.position ?? activeTicket.queue_position ?? 1
  const waitTime = activeTicket.waitTime ?? activeTicket.estimated_wait_mins ?? 0
  const hospitalName = activeTicket.hospitalName || activeTicket.hospital_name || 'Hospital'
  const sessionName = activeTicket.sessionName || activeTicket.session_name
  const doctorName = activeTicket.doctorName || activeTicket.doctor_name

  function handleNavigateToQueue() {
    if (onBack) {
      onBack()
    } else {
      navigate('/my-queue')
    }
  }

  return (
    <main className="confirmation-page">
      <div className="confirmation-card">

        <div className="success-icon">✓</div>

        <h1>Successfully Joined!</h1>
        <p>You have joined the hospital queue.</p>

        <div className="queue-number">
          <span>Your Queue Number</span>
          <h2>{tokenNumber}</h2>
        </div>

        <div className="queue-info">
          <div>
            <h3>{position}</h3>
            <p>Your Position</p>
          </div>

          <div>
            <h3>{waitTime} min</h3>
            <p>Estimated Wait</p>
          </div>
        </div>

        <h3>{hospitalName}</h3>
        {sessionName && (
          <p className="conf-session-info">
            Session: <strong>{sessionName}</strong>
          </p>
        )}
        {doctorName && (
          <p className="conf-doctor-info">
            Doctor: <strong>{doctorName}</strong>
          </p>
        )}

        <div className="confirmation-actions">
          <button
            type="button"
            className="conf-primary-btn"
            onClick={handleNavigateToQueue}
          >
            View in My Queue →
          </button>
        </div>

      </div>
    </main>
  )
}

export default QueueConfirmation

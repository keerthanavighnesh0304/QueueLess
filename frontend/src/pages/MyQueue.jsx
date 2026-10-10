
import './MyQueue.css'
import { Link } from 'react-router-dom'

function MyQueue({ queue, onLeave }) {
  if (!queue) {
    return (
      <main className="my-queue-page">
        <div className="empty-queue">
          <h1>No Active Queue</h1>
          <p>You haven't joined any hospital queue yet.</p>
          <Link to="/hospitals">Find Hospitals</Link>
        </div>
      </main>
    )
  }

  return (
    <main className="my-queue-page">
      <section className="my-queue-card">

        <h1>My Queue</h1>
        <p>Your active hospital queue details.</p>

        <div className="my-ticket">
          <span>Your Queue Number</span>
          <h2>{queue.queueNumber}</h2>
        </div>

        <h3>{queue.hospitalName}</h3>
        <p>{queue.location}</p>

        <div className="my-queue-info">
          <div>
            <h2>{queue.position}</h2>
            <p>Your Position</p>
          </div>

          <div>
            <h2>{queue.waitTime} min</h2>
            <p>Estimated Wait</p>
          </div>
        </div>

        <button
          className="leave-button"
          onClick={onLeave}
        >
          Leave Queue
        </button>

      </section>
    </main>
  )
}

export default MyQueue

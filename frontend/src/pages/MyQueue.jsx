import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { fetchMyTicketsApi, cancelTicketApi } from '../api/tickets'
import './MyQueue.css'

function getStatusBadgeInfo(status) {
  const raw = String(status || '').trim()
  const normalized = raw.toUpperCase()

  switch (normalized) {
    case 'COMPLETED':
      return { className: 'badge-completed', label: 'Completed' }
    case 'CANCELLED':
    case 'CANCELED':
      return { className: 'badge-cancelled', label: 'Cancelled' }
    case 'NO_SHOW':
    case 'NOSHOW':
    case 'NO SHOW':
      return { className: 'badge-noshow', label: 'No Show' }
    case 'WAITING':
      return { className: 'badge-waiting', label: 'Waiting' }
    case 'CALLING':
    case 'CALLED':
      return { className: 'badge-calling', label: 'Calling' }
    case 'IN_CONSULTATION':
    case 'SERVING':
    case 'CONSULTING':
    case 'IN_CONSULT':
      return { className: 'badge-consulting', label: 'In Consultation' }
    case 'SCHEDULED':
      return { className: 'badge-scheduled', label: 'Scheduled' }
    case 'PAUSED':
      return { className: 'badge-paused', label: 'Paused' }
    default:
      return { className: 'badge-neutral', label: raw || 'Unknown' }
  }
}

function MyQueue({ queue: mockQueue, onLeave: onLeaveMock }) {
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth()

  const [tickets, setTickets] = useState([])
  const [isLoading, setIsLoading] = useState(() => Boolean(isAuthenticated))
  const [error, setError] = useState(null)
  const [actionNotice, setActionNotice] = useState(null)
  const [cancellingTicketId, setCancellingTicketId] = useState(null)

  const isPollingRef = useRef(false)

  // 1. Fetch authenticated patient's tickets
  const loadTickets = useCallback(async (isBackground = false, signal = null) => {
    if (!isAuthenticated) {
      return
    }

    if (isPollingRef.current) return
    isPollingRef.current = true

    if (!isBackground) {
      setIsLoading(true)
      setError(null)
    }

    try {
      const data = await fetchMyTicketsApi({ signal })
      if (!signal?.aborted) {
        setTickets(data || [])
        setError(null)
      }
    } catch (err) {
      if (err?.name !== 'AbortError' && !signal?.aborted) {
        if (!isBackground) {
          setError(err.message || 'Failed to load your queue tickets.')
        }
      }
    } finally {
      if (!isBackground) {
        setIsLoading(false)
      }
      isPollingRef.current = false
    }
  }, [isAuthenticated])

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    let isMounted = true
    const abortController = new AbortController()

    async function fetchTickets() {
      setIsLoading(true)
      setError(null)
      try {
        const data = await fetchMyTicketsApi({ signal: abortController.signal })
        if (isMounted) {
          setTickets(data || [])
          setError(null)
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setError(err.message || 'Failed to load your queue tickets.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoading(false)
        }
      }
    }

    fetchTickets()

    return () => {
      isMounted = false
      abortController.abort()
      isPollingRef.current = false
    }
  }, [isAuthenticated])

  // 2. Controlled 6-Second Polling for Active Tickets
  const hasActiveTickets = tickets.some((t) =>
    ['WAITING', 'CALLING', 'IN_CONSULTATION'].includes(t.status)
  )

  useEffect(() => {
    if (!isAuthenticated || !hasActiveTickets) return

    let pollAbort = null

    const poll = () => {
      pollAbort = new AbortController()
      loadTickets(true, pollAbort.signal)
    }

    const intervalId = setInterval(poll, 6000)

    return () => {
      clearInterval(intervalId)
      if (pollAbort) pollAbort.abort()
      isPollingRef.current = false
    }
  }, [isAuthenticated, hasActiveTickets, loadTickets])

  // 3. Handle Ticket Cancellation
  async function handleCancelTicket(ticket) {
    const confirmed = window.confirm(
      `Are you sure you want to cancel ticket ${ticket.ticket_number}? This cannot be undone and your place in line will be forfeited.`
    )
    if (!confirmed) return

    setCancellingTicketId(ticket.id)
    setError(null)
    setActionNotice(null)

    try {
      const res = await cancelTicketApi(ticket.id)
      setActionNotice(res.message || `Queue ticket ${ticket.ticket_number} cancelled successfully.`)
      await loadTickets(false)
    } catch (err) {
      setError(err.message || 'Failed to cancel queue ticket.')
    } finally {
      setCancellingTicketId(null)
    }
  }

  // Filter Active vs Past Tickets safely across aliases
  const activeStatuses = ['WAITING', 'CALLING', 'CALLED', 'IN_CONSULTATION', 'SERVING', 'CONSULTING', 'IN_CONSULT']
  const activeTickets = tickets.filter((t) => {
    const s = String(t.status || '').trim().toUpperCase()
    return activeStatuses.includes(s)
  })
  const pastTickets = tickets.filter((t) => {
    const s = String(t.status || '').trim().toUpperCase()
    return !activeStatuses.includes(s)
  })

  // Loading state
  if (isAuthLoading) {
    return (
      <main className="my-queue-page">
        <div className="my-queue-card loading-state">
          <div className="spinner" />
          <p>Loading queue status...</p>
        </div>
      </main>
    )
  }

  // If unauthenticated: check if mock ticket exists, else show sign-in prompt
  if (!isAuthenticated) {
    if (mockQueue) {
      return (
        <main className="my-queue-page">
          <section className="my-queue-card">
            <div className="mock-demo-badge">Demo / Guest Queue</div>
            <h1>My Queue</h1>
            <p>Your active hospital queue details.</p>

            <div className="my-ticket">
              <span>Your Queue Number</span>
              <h2>{mockQueue.queueNumber}</h2>
            </div>

            <h3>{mockQueue.hospitalName}</h3>
            <p>{mockQueue.location}</p>

            <div className="my-queue-info">
              <div>
                <h2>{mockQueue.position}</h2>
                <p>Your Position</p>
              </div>

              <div>
                <h2>{mockQueue.waitTime} min</h2>
                <p>Estimated Wait</p>
              </div>
            </div>

            <button
              type="button"
              className="leave-button"
              onClick={onLeaveMock}
            >
              Leave Queue
            </button>
          </section>
        </main>
      )
    }

    return (
      <main className="my-queue-page">
        <div className="empty-queue">
          <h1>Sign In to View Your Queues</h1>
          <p>
            Please sign in with your patient account to view active tokens, real-time wait times, and consultation history.
          </p>
          <div className="empty-actions">
            <Link to="/profile" className="primary-link-btn">Sign In to Account</Link>
            <Link to="/hospitals" className="secondary-link-btn">Find Hospitals</Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="my-queue-page">
      <div className="my-queue-container">

        <header className="queue-page-header">
          <div>
            <h1>My Queue & Tokens</h1>
            <p className="subtext">
              Real-time patient queue dashboard for {user?.full_name}
            </p>
          </div>
          <button
            type="button"
            className="refresh-btn-small"
            onClick={() => loadTickets(false)}
            disabled={isLoading || Boolean(cancellingTicketId)}
          >
            {isLoading ? 'Updating...' : 'Refresh Status'}
          </button>
        </header>

        {actionNotice && (
          <div className="alert alert-success" role="status">
            <span>✓ {actionNotice}</span>
            <button type="button" className="close-alert-btn" onClick={() => setActionNotice(null)}>
              ×
            </button>
          </div>
        )}

        {error && (
          <div className="alert alert-error" role="alert">
            <span><strong>Notice:</strong> {error}</span>
            <button type="button" className="retry-btn-small" onClick={() => loadTickets(false)}>
              Retry
            </button>
          </div>
        )}

        {/* ACTIVE QUEUE TICKETS */}
        {activeTickets.length > 0 ? (
          <div className="active-tickets-list">
            {activeTickets.map((ticket) => (
              <section key={ticket.id} className={`active-ticket-card status-${ticket.status.toLowerCase()}`}>

                {/* Calling Banner */}
                {ticket.status === 'CALLING' && (
                  <div className="urgent-banner calling-banner">
                    🔔 <strong>NOW CALLING:</strong> The doctor is calling your token! Please proceed to the consultation room immediately.
                  </div>
                )}

                {/* In Consultation Banner */}
                {ticket.status === 'IN_CONSULTATION' && (
                  <div className="urgent-banner consult-banner">
                    🩺 <strong>IN CONSULTATION:</strong> You are currently in consultation with the doctor.
                  </div>
                )}

                <div className="ticket-card-header">
                  <div>
                    <span className="facility-label">{ticket.hospital_name || 'Hospital'}</span>
                    <h2>{ticket.session_name || 'Consultation Session'}</h2>
                    <p className="doc-label">Doctor: <strong>{ticket.doctor_name || 'Assigned Consultant'}</strong></p>
                  </div>
                  <span className={`ticket-status-badge ${getStatusBadgeInfo(ticket.status).className}`}>
                    {getStatusBadgeInfo(ticket.status).label}
                  </span>
                </div>

                <div className="token-hero">
                  <span className="token-caption">Your Assigned Token</span>
                  <div className="token-code">{ticket.ticket_number}</div>
                  <span className="registered-at-subtext">Issued {new Date(ticket.created_at).toLocaleTimeString()}</span>
                </div>

                <div className="live-metrics-grid">
                  <div className="metric-box">
                    <span className="metric-label">Queue Position</span>
                    <span className="metric-value">
                      {ticket.queue_position ? `#${ticket.queue_position}` : 'Active'}
                    </span>
                  </div>

                  <div className="metric-box">
                    <span className="metric-label">Patients Ahead</span>
                    <span className="metric-value">
                      {ticket.patients_ahead !== null && ticket.patients_ahead !== undefined
                        ? ticket.patients_ahead
                        : 0}
                    </span>
                  </div>

                  <div className="metric-box">
                    <span className="metric-label">Estimated Wait</span>
                    <span className="metric-value">
                      {ticket.estimated_wait_mins !== null && ticket.estimated_wait_mins !== undefined
                        ? `${ticket.estimated_wait_mins} min`
                        : '0 min'}
                    </span>
                  </div>
                </div>

                {/* Cancel Action */}
                {(ticket.status === 'WAITING' || ticket.status === 'CALLING') && (
                  <div className="ticket-footer-actions">
                    <button
                      type="button"
                      className="cancel-ticket-button"
                      onClick={() => handleCancelTicket(ticket)}
                      disabled={Boolean(cancellingTicketId)}
                    >
                      {cancellingTicketId === ticket.id ? 'Cancelling...' : 'Cancel Queue Ticket'}
                    </button>
                  </div>
                )}

              </section>
            ))}
          </div>
        ) : (
          <div className="empty-queue-card">
            <div className="empty-icon">🎫</div>
            <h2>No Active Queue Tickets</h2>
            <p>You do not currently have any waiting or calling queue tokens.</p>
            <Link to="/hospitals" className="find-hosp-btn">
              Find Hospitals & Join OPD Queue
            </Link>
          </div>
        )}

        {/* PAST CONSULTATIONS / HISTORY */}
        {pastTickets.length > 0 && (
          <section className="history-section">
            <div className="history-header">
              <div>
                <h3>Past Consultations & Ticket History</h3>
                <p className="subtext">
                  Archived records with verified consultation and cancellation outcomes
                </p>
              </div>
              <span className="history-count-pill">
                {pastTickets.length} Record{pastTickets.length > 1 ? 's' : ''}
              </span>
            </div>

            <div className="history-cards-grid">
              {pastTickets.map((t) => {
                const badge = getStatusBadgeInfo(t.status)
                const dateObj = t.created_at ? new Date(t.created_at) : null
                const dateStr = dateObj && !isNaN(dateObj.getTime())
                  ? dateObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
                  : 'Recent Session'
                const timeStr = dateObj && !isNaN(dateObj.getTime())
                  ? dateObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
                  : ''

                return (
                  <div key={t.id} className="history-card">
                    <div className="history-card-top">
                      <div className="history-token-wrap">
                        <span className="history-token-label">Token</span>
                        <span className="history-token">{t.ticket_number}</span>
                      </div>
                      <span className={`ticket-status-badge ${badge.className}`}>
                        {badge.label}
                      </span>
                    </div>

                    <div className="history-card-body">
                      <h4 className="history-hospital">{t.hospital_name || 'Hospital'}</h4>
                      <p className="history-session">
                        {t.session_name || 'OPD Session'}
                        {t.doctor_name && (
                          <span className="history-doctor-name">
                            {' '}· Dr. {t.doctor_name.replace(/^Dr\.?\s*/i, '')}
                          </span>
                        )}
                      </p>
                    </div>

                    <div className="history-card-footer">
                      <span className="history-date">
                        Issued {dateStr}{timeStr ? ` at ${timeStr}` : ''}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        )}

      </div>
    </main>
  )
}

export default MyQueue

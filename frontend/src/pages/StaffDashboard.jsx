import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import {
  fetchHospitalSessionsApi,
  fetchHospitalDoctorsApi,
  fetchHospitalDetailsApi,
} from '../api/hospitals'
import {
  fetchStaffLiveQueueApi,
  callNextPatientApi,
  servePatientApi,
  completeConsultationApi,
  markNoShowApi,
  createWalkInTicketApi,
  updateSessionStatusApi,
  createConsultationSessionApi,
} from '../api/staff'
import './StaffDashboard.css'

function StaffDashboard() {
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth()

  // Authorized hospital ID
  const hospitalId = user?.hospital_id || 1

  // Sessions and Doctors State
  const [sessions, setSessions] = useState([])
  const [doctors, setDoctors] = useState([])
  const [hospitalInfo, setHospitalInfo] = useState(null)
  const [selectedSessionId, setSelectedSessionId] = useState(null)
  const [isLoadingMeta, setIsLoadingMeta] = useState(() => Boolean(isAuthenticated && (user?.role === 'STAFF' || user?.role === 'ADMIN')))

  // Live Queue Dashboard State
  const [queueSummary, setQueueSummary] = useState(null)
  const [isLoadingQueue, setIsLoadingQueue] = useState(false)
  const [queueError, setQueueError] = useState(null)
  const [actionNotice, setActionNotice] = useState(null)
  const [isProcessingAction, setIsProcessingAction] = useState(false)

  // Walk-in form state
  const [showWalkInModal, setShowWalkInModal] = useState(false)
  const [walkInName, setWalkInName] = useState('')
  const [walkInPhone, setWalkInPhone] = useState('')
  const [walkInError, setWalkInError] = useState(null)
  const [isSubmittingWalkIn, setIsSubmittingWalkIn] = useState(false)

  // Schedule new session state
  const [showNewSessionModal, setShowNewSessionModal] = useState(false)
  const [newDoctorId, setNewDoctorId] = useState('')
  const [newSessionName, setNewSessionName] = useState('')
  const [newSessionDate, setNewSessionDate] = useState(() => new Date().toLocaleDateString('en-CA'))
  const [newStartTime, setNewStartTime] = useState('09:00:00')
  const [newEndTime, setNewEndTime] = useState('13:00:00')
  const [newCapacity, setNewCapacity] = useState('40')
  const [newSessionError, setNewSessionError] = useState(null)

  // Polling concurrency guard
  const isPollingRef = useRef(false)

  const [metaReloadKey, setMetaReloadKey] = useState(0)

  useEffect(() => {
    if (!isAuthenticated || (user?.role !== 'STAFF' && user?.role !== 'ADMIN')) {
      return
    }

    let isMounted = true
    const abortController = new AbortController()

    async function fetchMetadata() {
      setIsLoadingMeta(true)
      setQueueError(null)
      try {
        const [hosp, docList, sessList] = await Promise.all([
          fetchHospitalDetailsApi(hospitalId, { signal: abortController.signal }),
          fetchHospitalDoctorsApi(hospitalId, { signal: abortController.signal }),
          fetchHospitalSessionsApi(hospitalId, { signal: abortController.signal }),
        ])
        if (isMounted) {
          setHospitalInfo(hosp)
          setDoctors(docList || [])
          const allSessions = sessList || []
          setSessions(allSessions)

          if (allSessions.length > 0) {
            setSelectedSessionId((prev) => prev || allSessions[0].id)
          }
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setQueueError(err.message || 'Failed to load hospital metadata.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoadingMeta(false)
        }
      }
    }

    fetchMetadata()

    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [hospitalId, isAuthenticated, user, metaReloadKey])

  // 2. Fetch and Poll Live Queue for Selected Session
  const refreshQueue = useCallback(async (isBackground = false, signal = null) => {
    if (!selectedSessionId) return
    if (isPollingRef.current) return

    isPollingRef.current = true
    if (!isBackground) {
      setIsLoadingQueue(true)
      setQueueError(null)
    }

    try {
      const summary = await fetchStaffLiveQueueApi(hospitalId, selectedSessionId, { signal })
      if (!signal?.aborted) {
        setQueueSummary(summary)
        setQueueError(null)
      }
    } catch (err) {
      if (err?.name !== 'AbortError' && !signal?.aborted) {
        if (!isBackground) {
          setQueueError(err.message || 'Failed to load queue dashboard.')
        }
      }
    } finally {
      if (!isBackground) {
        setIsLoadingQueue(false)
      }
      isPollingRef.current = false
    }
  }, [hospitalId, selectedSessionId])

  // Initial fetch on session change
  useEffect(() => {
    if (!selectedSessionId) return

    let isMounted = true
    const abortController = new AbortController()

    async function fetchSessionQueue() {
      setIsLoadingQueue(true)
      setQueueError(null)
      try {
        const summary = await fetchStaffLiveQueueApi(hospitalId, selectedSessionId, {
          signal: abortController.signal,
        })
        if (isMounted) {
          setQueueSummary(summary)
          setQueueError(null)
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setQueueError(err.message || 'Failed to load queue dashboard.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoadingQueue(false)
        }
      }
    }

    fetchSessionQueue()

    return () => {
      isMounted = false
      abortController.abort()
      isPollingRef.current = false
    }
  }, [hospitalId, selectedSessionId])

  // 6-Second Live Polling Loop
  useEffect(() => {
    if (!selectedSessionId) return

    let pollAbort = null

    const poll = () => {
      pollAbort = new AbortController()
      refreshQueue(true, pollAbort.signal)
    }

    const intervalId = setInterval(poll, 6000)

    return () => {
      clearInterval(intervalId)
      if (pollAbort) pollAbort.abort()
      isPollingRef.current = false
    }
  }, [selectedSessionId, refreshQueue])

  // =========================================================================
  // Staff Operational Actions
  // =========================================================================

  async function handleCallNext() {
    if (isProcessingAction) return
    setIsProcessingAction(true)
    setActionNotice(null)
    setQueueError(null)

    try {
      const res = await callNextPatientApi(hospitalId, selectedSessionId)
      if (res.ticket) {
        setActionNotice(`Called ${res.ticket.ticket_number} (${res.ticket.patient_name})`)
      } else {
        setActionNotice(res.message || 'No waiting patients in queue.')
      }
      await refreshQueue(false)
    } catch (err) {
      setQueueError(err.message || 'Failed to call next patient.')
    } finally {
      setIsProcessingAction(false)
    }
  }

  async function handleServe(ticketId, ticketNumber) {
    if (isProcessingAction) return
    setIsProcessingAction(true)
    setActionNotice(null)
    setQueueError(null)

    try {
      await servePatientApi(hospitalId, ticketId)
      setActionNotice(`Consultation started for ticket ${ticketNumber}`)
      await refreshQueue(false)
    } catch (err) {
      setQueueError(err.message || 'Failed to start consultation.')
    } finally {
      setIsProcessingAction(false)
    }
  }

  async function handleComplete(ticketId, ticketNumber) {
    if (isProcessingAction) return
    setIsProcessingAction(true)
    setActionNotice(null)
    setQueueError(null)

    try {
      await completeConsultationApi(hospitalId, ticketId)
      setActionNotice(`Consultation completed for ticket ${ticketNumber}. Doctor is ready for next patient.`)
      await refreshQueue(false)
    } catch (err) {
      setQueueError(err.message || 'Failed to complete consultation.')
    } finally {
      setIsProcessingAction(false)
    }
  }

  async function handleNoShow(ticketId, ticketNumber) {
    if (isProcessingAction) return
    const confirmed = window.confirm(`Mark ticket ${ticketNumber} as No-Show? This will release the doctor to call the next patient.`)
    if (!confirmed) return

    setIsProcessingAction(true)
    setActionNotice(null)
    setQueueError(null)

    try {
      await markNoShowApi(hospitalId, ticketId)
      setActionNotice(`Ticket ${ticketNumber} marked as No-Show.`)
      await refreshQueue(false)
    } catch (err) {
      setQueueError(err.message || 'Failed to mark ticket as no-show.')
    } finally {
      setIsProcessingAction(false)
    }
  }

  async function handleWalkInSubmit(e) {
    e.preventDefault()
    if (!walkInName.trim()) {
      setWalkInError('Patient name is required.')
      return
    }

    setIsSubmittingWalkIn(true)
    setWalkInError(null)

    try {
      const res = await createWalkInTicketApi(hospitalId, selectedSessionId, {
        patient_name: walkInName.trim(),
        patient_phone: walkInPhone.trim() || undefined,
      })
      setActionNotice(`Walk-in ticket ${res.ticket.ticket_number} issued for ${res.ticket.patient_name}`)
      setWalkInName('')
      setWalkInPhone('')
      setShowWalkInModal(false)
      await refreshQueue(false)
    } catch (err) {
      setWalkInError(err.message || 'Failed to issue walk-in ticket.')
    } finally {
      setIsSubmittingWalkIn(false)
    }
  }

  async function handleStatusChange(newStatus) {
    if (isProcessingAction) return
    setIsProcessingAction(true)
    setActionNotice(null)
    setQueueError(null)

    try {
      await updateSessionStatusApi(hospitalId, selectedSessionId, newStatus)
      setActionNotice(`Session status updated to ${newStatus}`)
      // Update session list and live queue
      setSessions((prev) =>
        prev.map((s) => (s.id === selectedSessionId ? { ...s, status: newStatus } : s))
      )
      await refreshQueue(false)
    } catch (err) {
      setQueueError(err.message || 'Failed to update session status.')
    } finally {
      setIsProcessingAction(false)
    }
  }

  async function handleCreateSessionSubmit(e) {
    e.preventDefault()
    if (!newDoctorId || !newSessionName.trim()) {
      setNewSessionError('Please select a doctor and provide a session name.')
      return
    }

    setIsProcessingAction(true)
    setNewSessionError(null)

    try {
      const created = await createConsultationSessionApi(hospitalId, {
        doctor_id: Number(newDoctorId),
        session_name: newSessionName.trim(),
        session_date: newSessionDate,
        start_time: newStartTime,
        end_time: newEndTime,
        max_capacity: Number(newCapacity) || 40,
      })

      // If created in SCHEDULED, automatically activate it so queue is immediately operational
      try {
        await updateSessionStatusApi(hospitalId, created.id, 'ACTIVE')
        created.status = 'ACTIVE'
      } catch {
        // keep as SCHEDULED if auto-activate fails
      }

      setSessions((prev) => [created, ...prev])
      setSelectedSessionId(created.id)
      setMetaReloadKey((k) => k + 1)
      setShowNewSessionModal(false)
      setActionNotice(`Session "${created.session_name}" scheduled and set to ACTIVE.`)
    } catch (err) {
      setNewSessionError(err.message || 'Failed to create consultation session.')
    } finally {
      setIsProcessingAction(false)
    }
  }

  if (isAuthLoading) {
    return (
      <main className="staff-page">
        <div className="staff-container">
          <div className="staff-card loading-state">
            <div className="spinner" />
            <p>Verifying hospital staff privileges...</p>
          </div>
        </div>
      </main>
    )
  }

  if (!isAuthenticated || (user?.role !== 'STAFF' && user?.role !== 'ADMIN')) {
    return (
      <main className="staff-page">
        <div className="staff-container">
          <div className="staff-card access-denied">
            <div className="denied-icon">🔒</div>
            <h2>Staff Access Restricted</h2>
            <p>
              You must be signed in with a <strong>Hospital Staff</strong> or <strong>Administrator</strong> account to access clinical queue operations.
            </p>
            <Link to="/profile" className="staff-signin-btn">
              Sign In with Staff Account
            </Link>
          </div>
        </div>
      </main>
    )
  }

  const selectedSession = sessions.find((s) => s.id === selectedSessionId)
  const isRoomOccupied = Boolean(queueSummary?.currently_calling || queueSummary?.currently_serving)

  return (
    <main className="staff-page">
      <div className="staff-container">

        {/* Top Header & Hospital Identity */}
        <header className="staff-header">
          <div className="staff-header-info">
            <div className="staff-title-row">
              <h1>Staff Queue Management</h1>
              <span className="live-status-pill">
                <span className="live-indicator-dot" /> Live Control
              </span>
            </div>
            <p className="subtext">
              {hospitalInfo ? hospitalInfo.name : `Hospital #${hospitalId}`} · Real-Time Outpatient Clinical Desk
            </p>
          </div>

          <div className="staff-header-actions">
            <button
              type="button"
              className="new-session-btn"
              onClick={() => setShowNewSessionModal(true)}
            >
              + Schedule Session
            </button>
            <button
              type="button"
              className="refresh-btn"
              onClick={() => refreshQueue(false)}
              disabled={isLoadingQueue || isProcessingAction}
            >
              {isLoadingQueue ? 'Refreshing...' : '↻ Refresh Queue'}
            </button>
          </div>
        </header>

        {/* Action Notice Alert */}
        {actionNotice && (
          <div className="alert alert-success" role="status">
            <span className="alert-icon">✓</span>
            <span className="alert-text">{actionNotice}</span>
            <button type="button" className="close-alert-btn" onClick={() => setActionNotice(null)} aria-label="Dismiss notice">
              ×
            </button>
          </div>
        )}

        {/* Error Alert */}
        {queueError && (
          <div className="alert alert-error" role="alert">
            <span className="alert-icon">⚠️</span>
            <span className="alert-text"><strong>Operation Error:</strong> {queueError}</span>
            <button type="button" className="retry-btn-small" onClick={() => refreshQueue(false)}>
              Retry
            </button>
          </div>
        )}

        {/* Session Selector Card */}
        <div className="session-selector-card">
          <div className="selector-group">
            <label htmlFor="staff-session-select">Select Active OPD Session</label>
            <div className="select-input-wrapper">
              <select
                id="staff-session-select"
                className="session-select-control"
                value={selectedSessionId || ''}
                onChange={(e) => setSelectedSessionId(Number(e.target.value))}
              >
                {sessions.map((sess) => {
                  const doc = doctors.find((d) => d.id === sess.doctor_id)
                  return (
                    <option key={sess.id} value={sess.id}>
                      {sess.session_name} ({sess.session_date}) - {doc ? doc.full_name : 'Assigned Doctor'} [{sess.status}]
                    </option>
                  )
                })}
              </select>
            </div>
          </div>

          {selectedSession && (
            <div className="session-status-panel">
              <div className="session-status-info">
                <span className="status-label-caption">Session Status</span>
                <span className={`session-badge status-${selectedSession.status.toLowerCase()}`}>
                  {selectedSession.status}
                </span>
              </div>

              <div className="session-controls-group">
                {selectedSession.status === 'SCHEDULED' && (
                  <button
                    type="button"
                    className="status-action-btn btn-activate"
                    onClick={() => handleStatusChange('ACTIVE')}
                    disabled={isProcessingAction}
                  >
                    ▶ Start OPD (Activate)
                  </button>
                )}

                {selectedSession.status === 'ACTIVE' && (
                  <button
                    type="button"
                    className="status-action-btn btn-pause"
                    onClick={() => handleStatusChange('PAUSED')}
                    disabled={isProcessingAction}
                  >
                    ⏸ Pause OPD
                  </button>
                )}

                {selectedSession.status === 'PAUSED' && (
                  <button
                    type="button"
                    className="status-action-btn btn-activate"
                    onClick={() => handleStatusChange('ACTIVE')}
                    disabled={isProcessingAction}
                  >
                    ▶ Resume OPD
                  </button>
                )}

                {selectedSession.status !== 'COMPLETED' && (
                  <button
                    type="button"
                    className="status-action-btn btn-complete-session"
                    onClick={() => handleStatusChange('COMPLETED')}
                    disabled={isProcessingAction}
                  >
                    ⏹ Close Session
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Main Operational Live Queue View */}
        {isLoadingMeta ? (
          <div className="staff-card loading-state">
            <div className="spinner" />
            <p>Loading session and doctor metadata...</p>
          </div>
        ) : !selectedSession ? (
          <div className="staff-card empty-sessions-card">
            <div className="empty-bubble-icon">🩺</div>
            <h3>No Sessions Scheduled</h3>
            <p>There are no consultation sessions registered. Click "+ Schedule Session" above to set up an outpatient clinic.</p>
            <button
              type="button"
              className="new-session-btn"
              onClick={() => setShowNewSessionModal(true)}
            >
              + Schedule First Session
            </button>
          </div>
        ) : (
          <div className="queue-dashboard-grid">

            {/* Three Attractive Metric Cards */}
            <div className="metrics-grid">
              <div className="metric-card metric-waiting">
                <div className="metric-header">
                  <span className="metric-title">Waiting in Line</span>
                  <span className="metric-icon" aria-hidden="true">⏳</span>
                </div>
                <div className="metric-body">
                  <span className="metric-number">{queueSummary?.waiting_count ?? 0}</span>
                  <span className="metric-caption">Patients awaiting consultation</span>
                </div>
              </div>

              <div className="metric-card metric-capacity">
                <div className="metric-header">
                  <span className="metric-title">Capacity Utilized</span>
                  <span className="metric-icon" aria-hidden="true">📊</span>
                </div>
                <div className="metric-body">
                  <div className="metric-number-group">
                    <span className="metric-number">{queueSummary?.consumed_capacity ?? 0}</span>
                    <span className="metric-divider">/</span>
                    <span className="metric-total">{queueSummary?.max_capacity || 50}</span>
                  </div>
                  <div className="capacity-bar-track">
                    <div
                      className="capacity-bar-fill"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.round(
                            ((queueSummary?.consumed_capacity ?? 0) / (queueSummary?.max_capacity || 50)) * 100
                          )
                        )}%`,
                      }}
                    />
                  </div>
                  <span className="metric-caption">
                    {Math.min(
                      100,
                      Math.round(
                        ((queueSummary?.consumed_capacity ?? 0) / (queueSummary?.max_capacity || 50)) * 100
                      )
                    )}% booked
                  </span>
                </div>
              </div>

              <div className="metric-card metric-tokens">
                <div className="metric-header">
                  <span className="metric-title">Total Tokens Issued</span>
                  <span className="metric-icon" aria-hidden="true">🎫</span>
                </div>
                <div className="metric-body">
                  <span className="metric-number">{queueSummary?.total_tokens_issued ?? 0}</span>
                  <span className="metric-caption">Cumulative session tokens</span>
                </div>
              </div>
            </div>

            {/* Distinct, Prominent Operational Actions Bar */}
            <div className="staff-actions-bar">
              <div className="actions-guidance">
                <span className="actions-heading">Operational Actions</span>
                <p className="actions-subtext">
                  {isRoomOccupied
                    ? 'Room currently occupied. Complete current consultation before calling next patient.'
                    : (queueSummary?.waiting_count === 0
                      ? 'No patients waiting. Issue a walk-in ticket or wait for new arrivals.'
                      : 'Next patient is in sequence and ready to be called.')}
                </p>
              </div>

              <div className="actions-button-group">
                <button
                  type="button"
                  className="call-next-btn"
                  onClick={handleCallNext}
                  disabled={isRoomOccupied || isProcessingAction || (queueSummary?.waiting_count === 0)}
                  title={
                    isRoomOccupied
                      ? 'Room is occupied. Finish current patient before calling next.'
                      : (queueSummary?.waiting_count === 0 ? 'No waiting patients' : 'Call next patient in sequence')
                  }
                >
                  <span className="btn-icon">📢</span>
                  <span>{isProcessingAction ? 'Calling...' : 'Call Next Patient'}</span>
                </button>

                <button
                  type="button"
                  className="walkin-trigger-btn"
                  onClick={() => setShowWalkInModal(true)}
                  disabled={isProcessingAction}
                >
                  <span className="btn-icon">+</span>
                  <span>Issue Walk-In Ticket</span>
                </button>
              </div>
            </div>

            {/* Clinical Room Active State: Calling vs In Consultation */}
            <div className="active-room-section">

              {/* Now Calling Card */}
              <div className={`room-card calling-card ${queueSummary?.currently_calling ? 'active' : 'empty'}`}>
                <div className="room-card-header">
                  <div className="room-title-group">
                    <h3>Now Calling</h3>
                    <span className="room-subtitle">Waiting at Consultation Door</span>
                  </div>
                  <span className="room-indicator calling-indicator">
                    {queueSummary?.currently_calling ? '● AT DOOR' : 'IDLE'}
                  </span>
                </div>

                {queueSummary?.currently_calling ? (
                  <div className="ticket-detail-box">
                    <div className="token-display-hero">
                      <span className="token-hero-label">TOKEN NUMBER</span>
                      <div className="ticket-token-large">
                        {queueSummary.currently_calling.ticket_number}
                      </div>
                    </div>

                    <div className="ticket-meta-grid">
                      <div className="meta-field">
                        <span className="meta-label">Patient Name</span>
                        <p className="pat-name">{queueSummary.currently_calling.patient_name}</p>
                      </div>
                      <div className="meta-field">
                        <span className="meta-label">Phone</span>
                        <p className="pat-phone">{queueSummary.currently_calling.patient_phone || 'None provided'}</p>
                      </div>
                      <div className="meta-field">
                        <span className="meta-label">Booking Source</span>
                        <span className={`source-tag ${queueSummary.currently_calling.source?.toLowerCase()}`}>
                          {queueSummary.currently_calling.source === 'WALK_IN' ? 'Walk-In Registration' : 'Online Appointment'}
                        </span>
                      </div>
                    </div>

                    <div className="ticket-action-btns">
                      <button
                        type="button"
                        className="btn-start-consult"
                        onClick={() =>
                          handleServe(
                            queueSummary.currently_calling.id,
                            queueSummary.currently_calling.ticket_number
                          )
                        }
                        disabled={isProcessingAction}
                      >
                        ✓ Start Consultation
                      </button>

                      <button
                        type="button"
                        className="btn-noshow"
                        onClick={() =>
                          handleNoShow(
                            queueSummary.currently_calling.id,
                            queueSummary.currently_calling.ticket_number
                          )
                        }
                        disabled={isProcessingAction}
                      >
                        ✕ Mark No-Show
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="room-empty-state">
                    <div className="empty-bubble-icon">🔔</div>
                    <p className="room-empty-title">No Patient Calling</p>
                    <p className="room-idle-text">The calling desk is idle. Click "Call Next Patient" when the doctor is ready.</p>
                  </div>
                )}
              </div>

              {/* Currently In Consultation Card */}
              <div className={`room-card serving-card ${queueSummary?.currently_serving ? 'active' : 'empty'}`}>
                <div className="room-card-header">
                  <div className="room-title-group">
                    <h3>In Consultation</h3>
                    <span className="room-subtitle">Active with Doctor</span>
                  </div>
                  <span className="room-indicator serving-indicator">
                    {queueSummary?.currently_serving ? '● IN CLINIC' : 'IDLE'}
                  </span>
                </div>

                {queueSummary?.currently_serving ? (
                  <div className="ticket-detail-box">
                    <div className="token-display-hero serving-hero">
                      <span className="token-hero-label">TOKEN NUMBER</span>
                      <div className="ticket-token-large serving-token">
                        {queueSummary.currently_serving.ticket_number}
                      </div>
                    </div>

                    <div className="ticket-meta-grid">
                      <div className="meta-field">
                        <span className="meta-label">Patient Name</span>
                        <p className="pat-name">{queueSummary.currently_serving.patient_name}</p>
                      </div>
                      <div className="meta-field">
                        <span className="meta-label">Phone</span>
                        <p className="pat-phone">{queueSummary.currently_serving.patient_phone || 'None provided'}</p>
                      </div>
                      <div className="meta-field">
                        <span className="meta-label">Booking Source</span>
                        <span className={`source-tag ${queueSummary.currently_serving.source?.toLowerCase()}`}>
                          {queueSummary.currently_serving.source === 'WALK_IN' ? 'Walk-In Registration' : 'Online Appointment'}
                        </span>
                      </div>
                    </div>

                    <div className="ticket-action-btns">
                      <button
                        type="button"
                        className="btn-complete-consult"
                        onClick={() =>
                          handleComplete(
                            queueSummary.currently_serving.id,
                            queueSummary.currently_serving.ticket_number
                          )
                        }
                        disabled={isProcessingAction}
                      >
                        ✓ Complete Consultation
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="room-empty-state">
                    <div className="empty-bubble-icon">🩺</div>
                    <p className="room-empty-title">Consultation Room Idle</p>
                    <p className="room-idle-text">Doctor consultation room is empty. Start consultation with the called patient.</p>
                  </div>
                )}
              </div>

            </div>

            {/* Waiting Line Queue Table */}
            <div className="waiting-line-section">
              <div className="section-title-bar">
                <div className="section-title-group">
                  <h3>Waiting Queue Line</h3>
                  <span className="waiting-count-badge">
                    {queueSummary?.waiting_tickets?.length || 0} Waiting
                  </span>
                </div>
                <span className="subtext">FIFO monotonic sequence order · Real-time outpatient dispatch</span>
              </div>

              {queueSummary?.waiting_tickets?.length > 0 ? (
                <div className="waiting-table-wrap">
                  <table className="waiting-table">
                    <thead>
                      <tr>
                        <th className="col-pos">Position</th>
                        <th className="col-token">Token</th>
                        <th className="col-patient">Patient Name</th>
                        <th className="col-phone">Phone</th>
                        <th className="col-source">Source</th>
                        <th className="col-time">Registered At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queueSummary.waiting_tickets.map((t, idx) => (
                        <tr key={t.id}>
                          <td className="col-pos">
                            <span className="pos-badge">#{idx + 1}</span>
                          </td>
                          <td className="col-token">
                            <span className="token-pill">{t.ticket_number}</span>
                          </td>
                          <td className="col-patient">
                            <span className="patient-name-cell">{t.patient_name}</span>
                          </td>
                          <td className="col-phone">
                            <span className="patient-phone-cell">{t.patient_phone || '—'}</span>
                          </td>
                          <td className="col-source">
                            <span className={`source-badge ${t.source?.toLowerCase()}`}>
                              {t.source === 'WALK_IN' ? 'Walk-In' : 'Online'}
                            </span>
                          </td>
                          <td className="col-time">
                            <span className="time-cell">
                              {t.created_at ? new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="waiting-empty">
                  <div className="empty-bubble-icon">📋</div>
                  <h4>Queue is Empty</h4>
                  <p>No patients are currently waiting in this session. Issue a walk-in ticket or wait for upcoming bookings.</p>
                </div>
              )}
            </div>

          </div>
        )}

        {/* Modal: Issue Walk-In Registration */}
        {showWalkInModal && (
          <div className="modal-backdrop">
            <div className="modal-card">
              <div className="modal-header">
                <h3>Issue Walk-In Queue Ticket</h3>
                <button type="button" className="close-btn" onClick={() => setShowWalkInModal(false)}>
                  ×
                </button>
              </div>

              {walkInError && (
                <div className="alert alert-error" role="alert">
                  {walkInError}
                </div>
              )}

              <form onSubmit={handleWalkInSubmit} className="walkin-form">
                <div className="form-group">
                  <label htmlFor="walkin-name">Patient Full Name *</label>
                  <input
                    id="walkin-name"
                    type="text"
                    required
                    placeholder="e.g. Ramesh Krishnan"
                    value={walkInName}
                    onChange={(e) => setWalkInName(e.target.value)}
                    disabled={isSubmittingWalkIn}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="walkin-phone">Patient Phone Number</label>
                  <input
                    id="walkin-phone"
                    type="tel"
                    placeholder="e.g. +91 98400 12345"
                    value={walkInPhone}
                    onChange={(e) => setWalkInPhone(e.target.value)}
                    disabled={isSubmittingWalkIn}
                  />
                </div>

                <div className="modal-actions">
                  <button
                    type="button"
                    className="cancel-btn"
                    onClick={() => setShowWalkInModal(false)}
                    disabled={isSubmittingWalkIn}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="submit-btn"
                    disabled={isSubmittingWalkIn}
                  >
                    {isSubmittingWalkIn ? 'Issuing...' : 'Issue Walk-In Ticket'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal: Schedule New Session */}
        {showNewSessionModal && (
          <div className="modal-backdrop">
            <div className="modal-card">
              <div className="modal-header">
                <h3>Schedule New Consultation Session</h3>
                <button type="button" className="close-btn" onClick={() => setShowNewSessionModal(false)}>
                  ×
                </button>
              </div>

              {newSessionError && (
                <div className="alert alert-error" role="alert">
                  {newSessionError}
                </div>
              )}

              <form onSubmit={handleCreateSessionSubmit} className="walkin-form">
                <div className="form-group">
                  <label htmlFor="new-doc-select">Doctor *</label>
                  <select
                    id="new-doc-select"
                    required
                    value={newDoctorId}
                    onChange={(e) => {
                      setNewDoctorId(e.target.value)
                      const d = doctors.find((doc) => doc.id === Number(e.target.value))
                      if (d) {
                        setNewSessionName(`OPD Clinic - ${d.full_name}`)
                      }
                    }}
                  >
                    <option value="">-- Choose Practicing Doctor --</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.full_name} ({d.specialization}) [Prefix: {d.ticket_prefix}]
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="new-sess-name">Session Name *</label>
                  <input
                    id="new-sess-name"
                    type="text"
                    required
                    placeholder="e.g. Morning General OPD"
                    value={newSessionName}
                    onChange={(e) => setNewSessionName(e.target.value)}
                  />
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label htmlFor="new-sess-date">Session Date *</label>
                    <input
                      id="new-sess-date"
                      type="date"
                      required
                      value={newSessionDate}
                      onChange={(e) => setNewSessionDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="new-sess-cap">Max Capacity</label>
                    <input
                      id="new-sess-cap"
                      type="number"
                      min="1"
                      max="200"
                      value={newCapacity}
                      onChange={(e) => setNewCapacity(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label htmlFor="new-sess-start">Start Time</label>
                    <input
                      id="new-sess-start"
                      type="text"
                      placeholder="09:00:00"
                      value={newStartTime}
                      onChange={(e) => setNewStartTime(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="new-sess-end">End Time</label>
                    <input
                      id="new-sess-end"
                      type="text"
                      placeholder="13:00:00"
                      value={newEndTime}
                      onChange={(e) => setNewEndTime(e.target.value)}
                    />
                  </div>
                </div>

                <div className="modal-actions">
                  <button
                    type="button"
                    className="cancel-btn"
                    onClick={() => setShowNewSessionModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="submit-btn"
                    disabled={isProcessingAction}
                  >
                    {isProcessingAction ? 'Creating...' : 'Create & Activate Session'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </div>
    </main>
  )
}

export default StaffDashboard

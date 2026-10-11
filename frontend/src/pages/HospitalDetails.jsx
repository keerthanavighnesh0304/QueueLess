import { useState, useEffect, useRef, useCallback } from 'react'
import './HospitalDetails.css'
import { useAuth } from '../context/useAuth'
import {
  fetchHospitalDetailsApi,
  fetchHospitalDoctorsApi,
  fetchHospitalSessionsApi,
  fetchPublicQueueStatusApi,
} from '../api/hospitals'
import { createTicketApi } from '../api/tickets'

function getTodayDateString() {
  return new Date().toLocaleDateString('en-CA')
}

function HospitalDetails({ hospital: initialHospital, onBack, onJoin }) {
  const { user, isAuthenticated } = useAuth()
  const hospitalId = initialHospital.id

  // Date state: defaults to today in YYYY-MM-DD format
  const [todayStr] = useState(getTodayDateString)
  const [selectedDate, setSelectedDate] = useState(todayStr)

  // Facility, doctors, and sessions data state
  const [hospitalDetails, setHospitalDetails] = useState(null)
  const [doctors, setDoctors] = useState([])
  const [sessions, setSessions] = useState([])
  const [queueStatuses, setQueueStatuses] = useState({})

  // UI state
  const [isLoadingDetails, setIsLoadingDetails] = useState(true)
  const [isLoadingSessions, setIsLoadingSessions] = useState(true)
  const [detailsError, setDetailsError] = useState(null)
  const [sessionsError, setSessionsError] = useState(null)
  const [pollingNotice, setPollingNotice] = useState(null)
  const [sessionsReloadKey, setSessionsReloadKey] = useState(0)

  // Patient Booking Modal State
  const [selectedSessionForBooking, setSelectedSessionForBooking] = useState(null)
  const [patientName, setPatientName] = useState('')
  const [patientPhone, setPatientPhone] = useState('')
  const [bookingError, setBookingError] = useState(null)
  const [isSubmittingBooking, setIsSubmittingBooking] = useState(false)

  // Polling concurrency guard
  const isPollingRef = useRef(false)

  // Initialize booking form with patient details when modal opens
  const openBookingModal = useCallback((sess) => {
    setSelectedSessionForBooking(sess)
    setPatientName(user?.full_name || '')
    setPatientPhone(user?.phone || '')
    setBookingError(null)
  }, [user])

  // 1. Fetch Hospital Details (includes departments) and Doctor Directory
  useEffect(() => {
    let isMounted = true
    const abortController = new AbortController()

    async function loadFacilityAndDoctors() {
      try {
        const [details, doctorList] = await Promise.all([
          fetchHospitalDetailsApi(hospitalId, { signal: abortController.signal }),
          fetchHospitalDoctorsApi(hospitalId, { signal: abortController.signal }),
        ])
        if (isMounted) {
          setHospitalDetails(details)
          setDoctors(doctorList || [])
          setDetailsError(null)
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setDetailsError(err.message || 'Failed to load hospital details.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoadingDetails(false)
        }
      }
    }

    loadFacilityAndDoctors()

    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [hospitalId])

  // Helper to fetch live queue statuses for active / paused sessions
  const refreshQueueStatuses = useCallback(async (activeSessions, isBackgroundPoll = false, signal = null) => {
    if (!activeSessions || activeSessions.length === 0) return
    if (isPollingRef.current) return // Prevent overlapping requests

    isPollingRef.current = true
    if (!isBackgroundPoll) {
      setPollingNotice(null)
    }

    try {
      // Query queue status in parallel using Promise.allSettled
      const results = await Promise.allSettled(
        activeSessions.map((session) => fetchPublicQueueStatusApi(session.id, { signal }))
      )

      if (signal?.aborted) {
        return
      }

      const updated = {}
      let hasError = false

      results.forEach((res, idx) => {
        const sessionId = activeSessions[idx].id
        if (res.status === 'fulfilled') {
          updated[sessionId] = res.value
        } else {
          if (res.reason?.name === 'AbortError') {
            return
          }
          hasError = true
        }
      })

      // Preserve previously successful statuses for any session that failed
      setQueueStatuses((prev) => ({ ...prev, ...updated }))

      if (hasError && isBackgroundPoll) {
        setPollingNotice('Live updates delayed — retrying in 6s')
      } else {
        setPollingNotice(null)
      }
    } catch (err) {
      if (err?.name === 'AbortError' || signal?.aborted) {
        return
      }
      if (isBackgroundPoll) {
        setPollingNotice('Live updates delayed — retrying in 6s')
      }
    } finally {
      isPollingRef.current = false
    }
  }, [])

  // 2. Fetch Consultation Sessions for the selected date
  useEffect(() => {
    let isMounted = true
    const abortController = new AbortController()

    async function fetchSessions() {
      setIsLoadingSessions(true)
      setSessionsError(null)
      setPollingNotice(null)

      try {
        const sessionList = await fetchHospitalSessionsApi(hospitalId, {
          sessionDate: selectedDate,
          signal: abortController.signal,
        })
        if (isMounted) {
          const list = sessionList || []
          setSessions(list)
          setSessionsError(null)

          const pollableSessions = list.filter(
            (s) => s.status === 'ACTIVE' || s.status === 'PAUSED'
          )
          if (pollableSessions.length > 0) {
            refreshQueueStatuses(pollableSessions, false, abortController.signal)
          }
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setSessionsError(err.message || 'Failed to load consultation sessions for this date.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoadingSessions(false)
        }
      }
    }

    fetchSessions()

    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [hospitalId, selectedDate, sessionsReloadKey, refreshQueueStatuses])

  // 3. Controlled 6-Second Polling for ACTIVE and PAUSED sessions
  useEffect(() => {
    const activeSessions = sessions.filter(
      (s) => s.status === 'ACTIVE' || s.status === 'PAUSED'
    )

    if (activeSessions.length === 0) {
      return
    }

    let pollAbortController = null

    const poll = () => {
      pollAbortController = new AbortController()
      refreshQueueStatuses(activeSessions, true, pollAbortController.signal)
    }

    const intervalId = setInterval(poll, 6000)

    // Cleanup: immediately stop polling and abort pending requests on unmount or session/date change
    return () => {
      clearInterval(intervalId)
      if (pollAbortController) {
        pollAbortController.abort()
      }
      isPollingRef.current = false
    }
  }, [sessions, refreshQueueStatuses])

  const currentHospital = hospitalDetails || initialHospital
  const departments = hospitalDetails?.departments || []

  return (
    <main className="details-page">
      <button className="back-button" type="button" onClick={onBack}>
        ← Back to Hospitals
      </button>

      {isLoadingDetails && !hospitalDetails ? (
        <div className="details-card loading-state">
          <div className="spinner" />
          <p>Loading hospital details and department directories...</p>
        </div>
      ) : detailsError ? (
        <div className="alert alert-error">
          <p><strong>Error loading hospital:</strong> {detailsError}</p>
          <button type="button" className="retry-btn-small" onClick={onBack}>
            Return to Hospital List
          </button>
        </div>
      ) : (
        <section className="details-card">
          {/* Header Metadata */}
          <div className="details-header">
            <div>
              <h1>{currentHospital.name}</h1>
              <p className="hospital-address">
                {currentHospital.address ? `${currentHospital.address}, ` : ''}
                {currentHospital.city || 'Coimbatore'}
                {currentHospital.registration_number && (
                  <span className="reg-number"> · Reg #{currentHospital.registration_number}</span>
                )}
              </p>
            </div>

            <span className="status">
              {currentHospital.is_accepting_bookings ? 'Open & Accepting Bookings' : 'Closed'}
            </span>
          </div>

          {/* Quick Stats Overview */}
          <div className="details-overview-grid">
            <div className="overview-item">
              <span className="overview-label">Avg. Consultation</span>
              <span className="overview-value">{currentHospital.avg_consultation_time_mins || 15} mins</span>
            </div>
            <div className="overview-item">
              <span className="overview-label">Clinical Departments</span>
              <span className="overview-value">{departments.length}</span>
            </div>
            <div className="overview-item">
              <span className="overview-label">Active Doctors</span>
              <span className="overview-value">{doctors.length}</span>
            </div>
          </div>

          {/* Clinical Departments Section (Reused directly from details response) */}
          <div className="section-block">
            <h3>Clinical Departments</h3>
            {departments.length > 0 ? (
              <div className="departments-chips">
                {departments.map((dept) => (
                  <div key={dept.id} className="dept-chip" title={dept.description || ''}>
                    <span className="dept-name">{dept.name}</span>
                    {dept.description && <span className="dept-desc">{dept.description}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="subtext">No clinical departments registered for this hospital.</p>
            )}
          </div>

          {/* Active Doctor Directory */}
          <div className="section-block">
            <h3>Medical Practitioners ({doctors.length})</h3>
            {doctors.length > 0 ? (
              <div className="doctors-grid">
                {doctors.map((doc) => (
                  <div key={doc.id} className="doctor-card">
                    <div className="doc-avatar">Dr</div>
                    <div className="doc-info">
                      <h4>{doc.full_name}</h4>
                      <p className="doc-spec">{doc.specialization} · {doc.qualification || 'Consultant'}</p>
                      <span className="doc-token-tag">Token Prefix: {doc.ticket_prefix}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="subtext">No active doctors currently practicing at this hospital.</p>
            )}
          </div>

          {/* Consultation Sessions & Public Lobby Queues */}
          <div className="section-block sessions-section">
            <div className="sessions-header">
              <div>
                <h3>Outpatient Consultation Sessions</h3>
                <p className="subtext">Live queue counters update automatically every 6 seconds for active sessions.</p>
              </div>

              {/* Dynamic Date Selector & Presets */}
              <div className="date-picker-bar">
                <div className="date-input-wrap">
                  <label htmlFor="session-date-picker">Date</label>
                  <input
                    id="session-date-picker"
                    type="date"
                    className="session-date-input"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                  />
                </div>

                <div className="date-presets" role="group" aria-label="Select Date Preset">
                  <button
                    type="button"
                    className={`date-preset-btn ${selectedDate === todayStr ? 'active' : ''}`}
                    onClick={() => setSelectedDate(todayStr)}
                  >
                    Today
                  </button>
                  <button
                    type="button"
                    className={`date-preset-btn ${selectedDate === '2026-10-10' ? 'active' : ''}`}
                    onClick={() => setSelectedDate('2026-10-10')}
                  >
                    Demo Date (Oct 10)
                  </button>
                </div>
              </div>
            </div>

            {pollingNotice && (
              <div className="polling-notice" role="status">
                {pollingNotice}
              </div>
            )}

            {sessionsError && (
              <div className="alert alert-error">
                <p><strong>Error loading sessions:</strong> {sessionsError}</p>
                <button
                  type="button"
                  className="retry-btn-small"
                  onClick={() => setSessionsReloadKey((k) => k + 1)}
                >
                  Retry
                </button>
              </div>
            )}

            {isLoadingSessions ? (
              <div className="loading-state">
                <div className="spinner" />
                <p>Loading consultation sessions for {selectedDate}...</p>
              </div>
            ) : sessions.length > 0 ? (
              <div className="sessions-list">
                {sessions.map((sess) => {
                  const qStatus = queueStatuses[sess.id]
                  const doc = doctors.find((d) => d.id === sess.doctor_id)

                  return (
                    <div key={sess.id} className="session-card">
                      <div className="session-card-top">
                        <div>
                          <h4>{sess.session_name}</h4>
                          <p className="session-doctor">
                            {doc ? doc.full_name : 'Assigned Doctor'} ({doc?.specialization || 'OPD'})
                          </p>
                          <p className="session-timing">
                            {sess.start_time && sess.end_time
                              ? `${sess.start_time.slice(0, 5)} - ${sess.end_time.slice(0, 5)}`
                              : 'Day OPD'}
                            {sess.max_capacity > 0 && ` · Max Capacity: ${sess.max_capacity}`}
                          </p>
                        </div>

                        <span className={`session-status-badge status-${sess.status.toLowerCase()}`}>
                          {sess.status}
                        </span>
                      </div>

                      {/* Public Live Queue Display for Active/Paused Sessions */}
                      {sess.status === 'ACTIVE' || sess.status === 'PAUSED' ? (
                        <div className="public-queue-display">
                          <div className="queue-metric-box">
                            <span className="metric-label">Now Calling</span>
                            <span className="metric-token calling">
                              {qStatus?.currently_calling_token || 'None'}
                            </span>
                          </div>

                          <div className="queue-metric-box">
                            <span className="metric-label">In Consultation</span>
                            <span className="metric-token serving">
                              {qStatus?.currently_serving_token || 'None'}
                            </span>
                          </div>

                          <div className="queue-metric-box">
                            <span className="metric-label">Waiting in Queue</span>
                            <span className="metric-count">
                              {qStatus !== undefined ? qStatus.waiting_count : '...'}
                            </span>
                          </div>

                          <div className="queue-metric-box">
                            <span className="metric-label">Total Issued</span>
                            <span className="metric-count">
                              {qStatus !== undefined ? qStatus.total_tokens_issued : sess.last_sequence_number}
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="scheduled-session-note">
                          <span>
                            {sess.status === 'SCHEDULED'
                              ? 'ℹ Session scheduled. Live queue counters will activate once OPD starts.'
                              : 'ℹ This session has concluded.'}
                          </span>
                        </div>
                      )}

                      {/* Action to Join Session Queue */}
                      {(sess.status === 'ACTIVE' || sess.status === 'SCHEDULED') && (
                        <div className="session-join-wrap">
                          <button
                            type="button"
                            className="session-book-btn"
                            onClick={() => openBookingModal(sess)}
                          >
                            <span>Book Queue Token for this Session</span>
                            <span className="btn-arrow" aria-hidden="true">→</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              /* Informative Empty State for Dates Without Sessions */
              <div className="no-sessions-card">
                <p className="no-sessions-title">No Sessions Scheduled for {selectedDate}</p>
                <p className="no-sessions-desc">
                  There are no consultation sessions on this date for {currentHospital.name}.
                  You can choose any other date above, or click <strong>Demo Date (Oct 10)</strong> to inspect active test sessions.
                </p>
              </div>
            )}
          </div>

          {/* Preserved Mock / Quick Join Action Button */}
          <div className="action-row">
            <button
              className="join-button"
              type="button"
              onClick={() => {
                if (sessions.length > 0) {
                  openBookingModal(sessions[0])
                } else {
                  onJoin(currentHospital)
                }
              }}
            >
              {sessions.length > 0 ? 'Join Available Queue Session' : 'Join Queue (Demo Booking)'}
            </button>
          </div>

          {/* Booking Modal Dialog */}
          {selectedSessionForBooking && (
            <div className="modal-backdrop">
              <div className="modal-card">
                <div className="modal-header">
                  <h3>Join Consultation Queue</h3>
                  <button
                    type="button"
                    className="close-btn"
                    onClick={() => setSelectedSessionForBooking(null)}
                  >
                    ×
                  </button>
                </div>

                {!isAuthenticated ? (
                  <div className="modal-body auth-prompt">
                    <p>
                      You must be signed in with a <strong>Patient Account</strong> to receive an authorized digital queue ticket.
                    </p>
                    <div className="modal-actions">
                      <button
                        type="button"
                        className="cancel-btn"
                        onClick={() => setSelectedSessionForBooking(null)}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        className="submit-btn"
                        onClick={() => {
                          window.location.href = '/profile'
                        }}
                      >
                        Sign In to Book →
                      </button>
                    </div>
                  </div>
                ) : user?.role !== 'PATIENT' ? (
                  <div className="modal-body auth-prompt">
                    <p>
                      Online queue booking is only available for <strong>Patient Accounts</strong>.
                      You are currently signed in as <strong>{user?.role}</strong>.
                    </p>
                    <div className="modal-actions">
                      <button
                        type="button"
                        className="cancel-btn"
                        onClick={() => setSelectedSessionForBooking(null)}
                      >
                        Close
                      </button>
                    </div>
                  </div>
                ) : (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault()
                      if (!patientName.trim()) {
                        setBookingError('Patient full name is required.')
                        return
                      }

                      setIsSubmittingBooking(true)
                      setBookingError(null)

                      try {
                        const res = await createTicketApi(selectedSessionForBooking.id, {
                          patient_name: patientName.trim(),
                          patient_phone: patientPhone.trim() || undefined,
                        })
                        setSelectedSessionForBooking(null)
                        if (res && res.ticket) {
                          const ticketWithContext = {
                            ...res.ticket,
                            hospital_name: res.ticket.hospital_name || currentHospital.name,
                            session_name: res.ticket.session_name || selectedSessionForBooking.session_name,
                            session_id: res.ticket.session_id || selectedSessionForBooking.id,
                          }
                          onJoin(ticketWithContext)
                        }
                      } catch (err) {
                        setBookingError(err.message || 'Failed to issue queue ticket.')
                      } finally {
                        setIsSubmittingBooking(false)
                      }
                    }}
                    className="walkin-form"
                  >
                    <div className="session-summary-box">
                      <p><strong>Hospital:</strong> {currentHospital.name}</p>
                      <p><strong>Session:</strong> {selectedSessionForBooking.session_name}</p>
                      <p><strong>Date:</strong> {selectedSessionForBooking.session_date}</p>
                    </div>

                    {bookingError && (
                      <div className="alert alert-error" role="alert">
                        {bookingError}
                      </div>
                    )}

                    <div className="form-group">
                      <label htmlFor="booking-patient-name">Patient Full Name *</label>
                      <input
                        id="booking-patient-name"
                        type="text"
                        required
                        value={patientName}
                        onChange={(e) => setPatientName(e.target.value)}
                        disabled={isSubmittingBooking}
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="booking-patient-phone">Phone Number (Optional)</label>
                      <input
                        id="booking-patient-phone"
                        type="tel"
                        value={patientPhone}
                        onChange={(e) => setPatientPhone(e.target.value)}
                        disabled={isSubmittingBooking}
                        placeholder="+91 98765 43210"
                      />
                    </div>

                    <div className="modal-actions">
                      <button
                        type="button"
                        className="cancel-btn"
                        onClick={() => setSelectedSessionForBooking(null)}
                        disabled={isSubmittingBooking}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="submit-btn"
                        disabled={isSubmittingBooking}
                      >
                        {isSubmittingBooking ? 'Issuing Ticket...' : 'Confirm & Issue Ticket'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  )
}

export default HospitalDetails

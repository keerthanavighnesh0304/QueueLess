import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import {
  fetchPendingHospitalsApi,
  approveHospitalApi,
  rejectHospitalApi,
} from '../api/admin'
import './AdminApprovals.css'

function AdminApprovals() {
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth()

  const [hospitals, setHospitals] = useState([])
  const [isLoading, setIsLoading] = useState(() => Boolean(isAuthenticated && user?.role === 'ADMIN'))
  const [error, setError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)
  const [processingId, setProcessingId] = useState(null)

  const [reloadKey, setReloadKey] = useState(0)

  const loadPendingHospitals = useCallback(() => {
    setIsLoading(true)
    setReloadKey((k) => k + 1)
  }, [])

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'ADMIN') {
      return
    }

    let isMounted = true
    const abortController = new AbortController()

    async function fetchPending() {
      try {
        const data = await fetchPendingHospitalsApi({ signal: abortController.signal })
        if (isMounted) {
          setHospitals(data || [])
          setError(null)
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setError(err.message || 'Failed to load pending hospitals.')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoading(false)
        }
      }
    }

    fetchPending()

    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [isAuthenticated, user, reloadKey])

  async function handleApprove(hospitalId, hospitalName) {
    if (processingId) return
    setProcessingId(hospitalId)
    setError(null)
    setActionSuccess(null)

    try {
      await approveHospitalApi(hospitalId)
      setActionSuccess(`Successfully approved "${hospitalName}". Bookings are now enabled.`)
      setHospitals((prev) => prev.filter((h) => h.id !== hospitalId))
    } catch (err) {
      setError(err.message || `Failed to approve hospital #${hospitalId}.`)
    } finally {
      setProcessingId(null)
    }
  }

  async function handleReject(hospitalId, hospitalName) {
    if (processingId) return
    const confirmed = window.confirm(`Are you sure you want to reject the application for "${hospitalName}"?`)
    if (!confirmed) return

    setProcessingId(hospitalId)
    setError(null)
    setActionSuccess(null)

    try {
      await rejectHospitalApi(hospitalId)
      setActionSuccess(`Application for "${hospitalName}" has been rejected.`)
      setHospitals((prev) => prev.filter((h) => h.id !== hospitalId))
    } catch (err) {
      setError(err.message || `Failed to reject hospital #${hospitalId}.`)
    } finally {
      setProcessingId(null)
    }
  }

  if (isAuthLoading) {
    return (
      <main className="admin-page">
        <div className="admin-container">
          <div className="admin-card loading-state">
            <div className="spinner" />
            <p>Verifying administrative credentials...</p>
          </div>
        </div>
      </main>
    )
  }

  if (!isAuthenticated || user?.role !== 'ADMIN') {
    return (
      <main className="admin-page">
        <div className="admin-container">
          <div className="admin-card access-denied">
            <div className="denied-icon" aria-hidden="true">🔒</div>
            <h2>Administrative Access Restricted</h2>
            <p>
              You must be signed in as a <strong>Platform Administrator</strong> to review and approve hospital onboarding applications.
            </p>
            <Link to="/profile" className="admin-signin-btn">
              Sign In with Administrator Account
            </Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="admin-page">
      <div className="admin-container">
        {/* Top Header */}
        <header className="admin-header">
          <div className="admin-header-info">
            <div className="admin-title-row">
              <h1>Hospital Onboarding Approvals</h1>
              <span className="admin-status-pill">
                <span className="admin-indicator-dot" /> Platform Admin
              </span>
            </div>
            <p className="subtext">
              Review and verify pending healthcare facility registrations for Coimbatore platform onboarding.
            </p>
          </div>
          <button
            type="button"
            className="refresh-btn"
            onClick={() => loadPendingHospitals()}
            disabled={isLoading || Boolean(processingId)}
          >
            {isLoading ? 'Refreshing...' : '↻ Refresh List'}
          </button>
        </header>

        {/* Action Success Alert */}
        {actionSuccess && (
          <div className="alert alert-success" role="status">
            <span className="alert-icon">✓</span>
            <span className="alert-text">{actionSuccess}</span>
            <button type="button" className="close-alert-btn" onClick={() => setActionSuccess(null)} aria-label="Dismiss notice">
              ×
            </button>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="alert alert-error" role="alert">
            <span className="alert-icon">⚠️</span>
            <span className="alert-text"><strong>Error:</strong> {error}</span>
            <button type="button" className="retry-btn-small" onClick={() => loadPendingHospitals()}>
              Retry
            </button>
          </div>
        )}

        {/* Pending Queue Count Strip */}
        {!isLoading && (
          <div className="admin-summary-strip">
            <div className="summary-left">
              <span className="summary-label">Registration Applications</span>
              <p className="summary-subtext">
                {hospitals.length === 0
                  ? 'All healthcare facility registrations have been processed.'
                  : `Awaiting administrative compliance check and booking activation (${hospitals.length}).`}
              </p>
            </div>
            <span className="pending-counter-badge">
              {hospitals.length} Pending Review
            </span>
          </div>
        )}

        {isLoading ? (
          <div className="admin-card loading-state">
            <div className="spinner" />
            <p>Loading pending hospital applications...</p>
          </div>
        ) : hospitals.length > 0 ? (
          <div className="pending-grid">
            {hospitals.map((hosp) => (
              <div key={hosp.id} className="pending-card">
                <div className="pending-card-header">
                  <div className="hospital-identity">
                    <div className="hospital-icon-wrap" aria-hidden="true">🏥</div>
                    <div className="hospital-title-wrap">
                      <h3>{hosp.name}</h3>
                      <div className="reg-number-row">
                        <span className="reg-label">REG NO:</span>
                        <span className="reg-value-pill">{hosp.registration_number}</span>
                      </div>
                    </div>
                  </div>
                  <span className="status-badge status-pending">
                    ● Pending Review
                  </span>
                </div>

                <div className="pending-details-grid">
                  <div className="detail-item detail-location">
                    <span className="detail-label">Location / Address</span>
                    <p className="detail-value">{hosp.address}, {hosp.city}</p>
                  </div>

                  <div className="detail-item detail-time">
                    <span className="detail-label">Avg Consultation</span>
                    <p className="detail-value">{hosp.avg_consultation_time_mins} mins / slot</p>
                  </div>

                  <div className="detail-item detail-coords">
                    <span className="detail-label">GPS Coordinates</span>
                    <p className="detail-value mono">{hosp.latitude.toFixed(6)}, {hosp.longitude.toFixed(6)}</p>
                  </div>

                  <div className="detail-item detail-date">
                    <span className="detail-label">Submitted On</span>
                    <p className="detail-value">
                      {hosp.created_at ? new Date(hosp.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Recently'}
                    </p>
                  </div>
                </div>

                <div className="pending-actions-bar">
                  <button
                    type="button"
                    className="approve-btn"
                    onClick={() => handleApprove(hosp.id, hosp.name)}
                    disabled={Boolean(processingId)}
                  >
                    <span className="btn-icon">✓</span>
                    <span>{processingId === hosp.id ? 'Processing Approval...' : 'Approve & Enable Bookings'}</span>
                  </button>

                  <button
                    type="button"
                    className="reject-btn"
                    onClick={() => handleReject(hosp.id, hosp.name)}
                    disabled={Boolean(processingId)}
                  >
                    <span className="btn-icon">✕</span>
                    <span>Reject</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="admin-card empty-state">
            <div className="empty-bubble-icon" aria-hidden="true">🛡️</div>
            <h3>No Pending Applications</h3>
            <p>All healthcare facilities have been reviewed. There are no pending applications awaiting approval at this time.</p>
          </div>
        )}
      </div>
    </main>
  )
}

export default AdminApprovals

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
        <div className="admin-card loading-state">
          <div className="spinner" />
          <p>Verifying administrative credentials...</p>
        </div>
      </main>
    )
  }

  if (!isAuthenticated || user?.role !== 'ADMIN') {
    return (
      <main className="admin-page">
        <div className="admin-card access-denied">
          <h2>Administrative Access Restricted</h2>
          <p>
            You must be signed in as a <strong>Platform Administrator</strong> to review and approve hospital onboarding applications.
          </p>
          <Link to="/profile" className="admin-signin-btn">
            Sign In with Administrator Account
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="admin-page">
      <div className="admin-container">
        <header className="admin-header">
          <div>
            <h1>Hospital Onboarding Approvals</h1>
            <p className="subtext">
              Review pending healthcare facility registrations for Coimbatore platform onboarding.
            </p>
          </div>
          <button
            type="button"
            className="refresh-btn"
            onClick={() => loadPendingHospitals()}
            disabled={isLoading || Boolean(processingId)}
          >
            {isLoading ? 'Refreshing...' : 'Refresh List'}
          </button>
        </header>

        {actionSuccess && (
          <div className="alert alert-success" role="status">
            <span>✓ {actionSuccess}</span>
            <button type="button" className="close-alert-btn" onClick={() => setActionSuccess(null)}>
              ×
            </button>
          </div>
        )}

        {error && (
          <div className="alert alert-error" role="alert">
            <span><strong>Error:</strong> {error}</span>
            <button type="button" className="retry-btn-small" onClick={() => loadPendingHospitals()}>
              Retry
            </button>
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
                <div className="pending-card-top">
                  <div>
                    <h3>{hosp.name}</h3>
                    <p className="reg-tag">Reg Number: <strong>{hosp.registration_number}</strong></p>
                  </div>
                  <span className="status-badge pending">Pending Review</span>
                </div>

                <div className="pending-details">
                  <p><strong>Location:</strong> {hosp.address}, {hosp.city}</p>
                  <p><strong>Coordinates:</strong> {hosp.latitude.toFixed(6)}, {hosp.longitude.toFixed(6)}</p>
                  <p><strong>Consultation Duration:</strong> {hosp.avg_consultation_time_mins} minutes avg.</p>
                  <p><strong>Submitted:</strong> {new Date(hosp.created_at).toLocaleString()}</p>
                </div>

                <div className="pending-actions">
                  <button
                    type="button"
                    className="approve-btn"
                    onClick={() => handleApprove(hosp.id, hosp.name)}
                    disabled={Boolean(processingId)}
                  >
                    {processingId === hosp.id ? 'Processing...' : 'Approve & Enable Bookings'}
                  </button>

                  <button
                    type="button"
                    className="reject-btn"
                    onClick={() => handleReject(hosp.id, hosp.name)}
                    disabled={Boolean(processingId)}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="admin-card empty-state">
            <h3>No Pending Applications</h3>
            <p>All healthcare facilities have been reviewed. There are no pending applications awaiting approval at this time.</p>
          </div>
        )}
      </div>
    </main>
  )
}

export default AdminApprovals

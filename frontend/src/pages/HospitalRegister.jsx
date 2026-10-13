import { useState } from 'react'
import { Link } from 'react-router-dom'
import { registerHospitalApi } from '../api/hospitals'
import './HospitalRegister.css'

function HospitalRegister() {
  const [formData, setFormData] = useState({
    hospitalName: '',
    registrationNumber: '',
    address: '',
    city: 'Coimbatore',
    contactPersonName: '',
    contactEmail: '',
    contactPhone: '',
    avgConsultationTime: '15',
  })

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const [submittedHospital, setSubmittedHospital] = useState(null)

  function handleChange(e) {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (errorMessage) setErrorMessage(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (isSubmitting) return

    // Client-side validations
    const name = formData.hospitalName.trim()
    const regNo = formData.registrationNumber.trim()
    const address = formData.address.trim()
    const city = formData.city.trim()
    const contactName = formData.contactPersonName.trim()
    const contactEmail = formData.contactEmail.trim()
    const contactPhone = formData.contactPhone.trim()

    if (!name || name.length < 2) {
      setErrorMessage('Hospital name must be at least 2 characters.')
      return
    }
    if (!regNo || regNo.length < 2) {
      setErrorMessage('Please provide a valid registration or license number.')
      return
    }
    if (!address || address.length < 5) {
      setErrorMessage('Street address must be at least 5 characters.')
      return
    }
    if (!city) {
      setErrorMessage('City is required.')
      return
    }
    if (!contactName || contactName.length < 2) {
      setErrorMessage('Contact person name must be at least 2 characters.')
      return
    }
    if (!contactEmail || !contactEmail.includes('@')) {
      setErrorMessage('Please provide a valid contact email address.')
      return
    }
    if (!contactPhone || contactPhone.length < 7) {
      setErrorMessage('Please provide a valid contact telephone number.')
      return
    }

    setIsSubmitting(true)
    setErrorMessage(null)

    try {
      const payload = {
        name,
        registration_number: regNo,
        address,
        city,
        contact_person_name: contactName,
        contact_email: contactEmail,
        contact_phone: contactPhone,
        avg_consultation_time_mins: Number(formData.avgConsultationTime) || 15,
      }

      const result = await registerHospitalApi(payload)
      setSubmittedHospital(result)
    } catch (err) {
      setErrorMessage(err.message || 'Failed to submit hospital registration. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleReset() {
    setSubmittedHospital(null)
    setFormData({
      hospitalName: '',
      registrationNumber: '',
      address: '',
      city: 'Coimbatore',
      contactPersonName: '',
      contactEmail: '',
      contactPhone: '',
      avgConsultationTime: '15',
    })
    setErrorMessage(null)
  }

  return (
    <main className="hospital-register-page">
      <div className="hospital-register-container">

        {/* Breadcrumb & Navigation */}
        <nav className="register-breadcrumb" aria-label="Breadcrumb">
          <Link to="/">Home</Link>
          <span className="breadcrumb-separator">/</span>
          <Link to="/hospitals">Hospitals</Link>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">Hospital Registration</span>
        </nav>

        {/* Success View */}
        {submittedHospital ? (
          <section className="register-card success-card" aria-live="polite">
            <div className="success-icon-wrap" aria-hidden="true">✓</div>
            <span className="success-eyebrow">Application Submitted</span>
            <h2>Registration Request Received</h2>

            <p className="success-description">
              Thank you for registering <strong>{submittedHospital.name}</strong> with QueueLess.
              Your application has been received and logged in our administrative queue.
            </p>

            <div className="application-summary-box">
              <div className="summary-row">
                <span className="summary-label">Hospital Name:</span>
                <span className="summary-val">{submittedHospital.name}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Registration Number:</span>
                <span className="summary-val font-mono">{submittedHospital.registration_number}</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Current Status:</span>
                <span className="status-badge-pending">● Awaiting Admin Review</span>
              </div>
              <div className="summary-row">
                <span className="summary-label">Live Bookings:</span>
                <span className="summary-val">Disabled (Pending Verification)</span>
              </div>
            </div>

            <div className="next-steps-callout">
              <h4>What happens next?</h4>
              <ol className="next-steps-list">
                <li>
                  <strong>Administrative Verification:</strong> The QueueLess platform administrator reviews your clinical facility credentials and registration license.
                </li>
                <li>
                  <strong>Activation & Notification:</strong> Once approved, your facility becomes visible on the patient directory, and your hospital staff portal access is provisioned.
                </li>
                <li>
                  <strong>OPD Launch:</strong> You can immediately schedule consultation sessions, issue live walk-in tickets, and accept patient bookings.
                </li>
              </ol>
            </div>

            <div className="success-actions">
              <button
                type="button"
                className="btn-register-another"
                onClick={handleReset}
              >
                + Register Another Hospital
              </button>
              <Link to="/hospitals" className="btn-return-hospitals">
                Browse Live Hospitals →
              </Link>
            </div>
          </section>
        ) : (
          /* Registration Form View */
          <div className="register-content-layout">

            {/* Left Header & Information Panel */}
            <header className="register-header-panel">
              <span className="register-badge-pill">Healthcare Facility Onboarding</span>
              <h1>Register Your Hospital with QueueLess</h1>
              <p className="register-subhead">
                Partner with Coimbatore's real-time outpatient queue platform. Eliminate crowded waiting rooms,
                optimize doctor schedules, and deliver predictable healthcare experiences.
              </p>

              {/* Administrative Notice Box */}
              <div className="admin-notice-box">
                <div className="notice-icon" aria-hidden="true">ℹ️</div>
                <div className="notice-body">
                  <h4>Subject to Administrative Verification</h4>
                  <p>
                    All facility onboarding applications are reviewed and verified by the QueueLess platform administrator before live patient booking eligibility and staff credentials are activated.
                  </p>
                </div>
              </div>

              <div className="onboarding-perks">
                <div className="perk-item">
                  <span className="perk-icon">✓</span>
                  <div>
                    <strong>Real-Time Outpatient Queuing:</strong>
                    <span>Live FIFO sequence tracking with automated token issuance.</span>
                  </div>
                </div>
                <div className="perk-item">
                  <span className="perk-icon">✓</span>
                  <div>
                    <strong>Desk Walk-In Integration:</strong>
                    <span>Issue physical OPD tokens directly from the staff reception desk.</span>
                  </div>
                </div>
                <div className="perk-item">
                  <span className="perk-icon">✓</span>
                  <div>
                    <strong>Zero Platform Lock-in:</strong>
                    <span>Control consultation capacity and pause or resume clinic sessions in real time.</span>
                  </div>
                </div>
              </div>
            </header>

            {/* Right Registration Form Card */}
            <section className="register-card form-card">
              <div className="form-card-header">
                <h2>Hospital Application Form</h2>
                <span className="required-note">* Required fields</span>
              </div>

              {errorMessage && (
                <div className="alert alert-error" role="alert">
                  <span className="alert-icon" aria-hidden="true">⚠️</span>
                  <span className="alert-text">{errorMessage}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="register-form" noValidate>

                {/* Section 1: Hospital Details */}
                <fieldset className="form-fieldset">
                  <legend className="fieldset-legend">1. Facility Details</legend>

                  <div className="form-group">
                    <label htmlFor="hospitalName">Hospital / Clinic Full Name *</label>
                    <input
                      id="hospitalName"
                      name="hospitalName"
                      type="text"
                      required
                      placeholder="e.g. Coimbatore City Care Hospital"
                      value={formData.hospitalName}
                      onChange={handleChange}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="registrationNumber">Registration / License Number *</label>
                    <input
                      id="registrationNumber"
                      name="registrationNumber"
                      type="text"
                      required
                      placeholder="e.g. TN-CBE-HOSP-2026-089"
                      value={formData.registrationNumber}
                      onChange={handleChange}
                      disabled={isSubmitting}
                    />
                    <span className="field-hint">Official state clinical establishment or health authority license number.</span>
                  </div>

                  <div className="form-group">
                    <label htmlFor="address">Physical Street Address *</label>
                    <input
                      id="address"
                      name="address"
                      type="text"
                      required
                      placeholder="e.g. 142 Avinashi Road, Peelamedu"
                      value={formData.address}
                      onChange={handleChange}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="form-row-2">
                    <div className="form-group">
                      <label htmlFor="city">City *</label>
                      <input
                        id="city"
                        name="city"
                        type="text"
                        required
                        value={formData.city}
                        onChange={handleChange}
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="avgConsultationTime">Avg Consultation (Mins)</label>
                      <input
                        id="avgConsultationTime"
                        name="avgConsultationTime"
                        type="number"
                        min="5"
                        max="120"
                        value={formData.avgConsultationTime}
                        onChange={handleChange}
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>
                </fieldset>

                {/* Section 2: Contact Information */}
                <fieldset className="form-fieldset">
                  <legend className="fieldset-legend">2. Administrative Contact</legend>

                  <div className="form-group">
                    <label htmlFor="contactPersonName">Contact Person Name *</label>
                    <input
                      id="contactPersonName"
                      name="contactPersonName"
                      type="text"
                      required
                      placeholder="e.g. Dr. Rajesh Kumar, Medical Superintendent"
                      value={formData.contactPersonName}
                      onChange={handleChange}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="form-row-2">
                    <div className="form-group">
                      <label htmlFor="contactEmail">Contact Email Address *</label>
                      <input
                        id="contactEmail"
                        name="contactEmail"
                        type="email"
                        required
                        placeholder="e.g. admin@citycarehospital.org"
                        value={formData.contactEmail}
                        onChange={handleChange}
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="contactPhone">Contact Phone Number *</label>
                      <input
                        id="contactPhone"
                        name="contactPhone"
                        type="tel"
                        required
                        placeholder="e.g. +91 98400 12345"
                        value={formData.contactPhone}
                        onChange={handleChange}
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>
                </fieldset>

                <div className="form-submit-row">
                  <button
                    type="submit"
                    className="btn-submit-registration"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <span className="spinner-small" aria-hidden="true" />
                        <span>Submitting Application...</span>
                      </>
                    ) : (
                      <span>Submit Hospital Registration Request →</span>
                    )}
                  </button>
                  <p className="terms-caption">
                    By submitting, you agree that registration is subject to administrative review by QueueLess.
                  </p>
                </div>

              </form>
            </section>
          </div>
        )}

      </div>
    </main>
  )
}

export default HospitalRegister

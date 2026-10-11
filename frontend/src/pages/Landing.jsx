import { Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import './Landing.css';

function Landing() {
  const { user, isAuthenticated } = useAuth();

  return (
    <main className="landing-page">
      {/* 1. Hero Section */}
      <section className="landing-hero">
        <div className="hero-container">
          <div className="hero-badge">
            <span className="badge-pulse" />
            Live Hospital OPD & Queue Platform
          </div>

          <h1 className="hero-headline">
            Healthcare Appointments Without the <span className="highlight-amber">Waiting Room Uncertainty</span>
          </h1>

          <p className="hero-subhead">
            QueueLess connects patients with real-time outpatient queues at verified healthcare facilities.
            Check live doctor schedules, secure your digital token in advance, and track your position from anywhere.
          </p>

          <div className="hero-actions">
            <Link to="/hospitals" className="btn-primary-amber">
              Find a Hospital & Join Queue →
            </Link>

            {isAuthenticated ? (
              user?.role === 'STAFF' ? (
                <Link to="/staff" className="btn-secondary-outline">
                  Staff Workspace ({user.full_name.split(' ')[0]})
                </Link>
              ) : user?.role === 'ADMIN' ? (
                <Link to="/admin" className="btn-secondary-outline">
                  Admin Verification Panel
                </Link>
              ) : (
                <Link to="/my-queue" className="btn-secondary-outline">
                  View My Active Tokens
                </Link>
              )
            ) : (
              <Link to="/profile" className="btn-secondary-outline">
                Hospital Staff Portal
              </Link>
            )}
          </div>

          {/* Quick Metrics Strip */}
          <div className="hero-stats-strip">
            <div className="stat-item">
              <span className="stat-number">Real-Time</span>
              <span className="stat-label">Live Queue Tracking</span>
            </div>
            <div className="stat-divider" />
            <div className="stat-item">
              <span className="stat-number">100% Verified</span>
              <span className="stat-label">Admin-Approved Hospitals</span>
            </div>
            <div className="stat-divider" />
            <div className="stat-item">
              <span className="stat-number">Zero Wait Stress</span>
              <span className="stat-label">Accurate Estimated Times</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Three-Step Workflow */}
      <section className="workflow-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-eyebrow">How QueueLess Works</span>
            <h2>Simple, Transparent 3-Step Process</h2>
            <p>Skip the crowded waiting lounge with end-to-end digital queue orchestration.</p>
          </div>

          <div className="steps-grid">
            <div className="step-card">
              <div className="step-number">01</div>
              <div className="step-icon">🏥</div>
              <h3>Find an Approved Hospital</h3>
              <p>
                Browse verified hospitals and clinics in your city. Check active departments,
                consulting physicians, and daily OPD operational hours.
              </p>
              <Link to="/hospitals" className="step-link">Browse Hospitals →</Link>
            </div>

            <div className="step-card">
              <div className="step-number">02</div>
              <div className="step-icon">🎫</div>
              <h3>Book Your Live Queue Token</h3>
              <p>
                Select your preferred doctor and consultation session. Authenticated patients receive
                an authoritative digital token with exact line position.
              </p>
              <span className="step-tag">Instant Confirmation</span>
            </div>

            <div className="step-card">
              <div className="step-number">03</div>
              <div className="step-icon">⏱️</div>
              <h3>Track Queue in Real-Time</h3>
              <p>
                Monitor doctor progress live from your phone. Receive instant alerts when your token
                is called so you arrive precisely when the doctor is ready.
              </p>
              <Link to="/my-queue" className="step-link">Track Tokens →</Link>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Value Proposition / Dual-Sided Benefits */}
      <section className="benefits-section">
        <div className="section-container">
          <div className="benefits-dual-grid">
            {/* For Patients */}
            <div className="benefit-panel patient-panel">
              <div className="panel-badge">For Patients</div>
              <h3>Regain Control of Your Time</h3>
              <p className="panel-desc">
                No more sitting for hours in noisy, infection-prone hospital lobbies with no idea when you'll be called.
              </p>
              <ul className="benefit-list">
                <li>
                  <span className="check-icon">✓</span>
                  <div>
                    <strong>Accurate Estimated Wait:</strong> Calculated dynamically from doctor's average consultation duration.
                  </div>
                </li>
                <li>
                  <span className="check-icon">✓</span>
                  <div>
                    <strong>Live Calling Alerts:</strong> Instant visual indicators the moment your token is called to the consultation room.
                  </div>
                </li>
                <li>
                  <span className="check-icon">✓</span>
                  <div>
                    <strong>Single-Click Cancellation:</strong> Cancel freely if your plans change, automatically freeing capacity for other patients.
                  </div>
                </li>
              </ul>
              <Link to="/hospitals" className="panel-btn">
                Explore Available Clinics →
              </Link>
            </div>

            {/* For Healthcare Staff & Administrators */}
            <div className="benefit-panel provider-panel">
              <div className="panel-badge">For Healthcare Providers</div>
              <h3>Orderly Outpatient Management</h3>
              <p className="panel-desc">
                Equip your front desk and doctors with authoritative operational dashboards built for high-throughput OPDs.
              </p>
              <ul className="benefit-list">
                <li>
                  <span className="check-icon">✓</span>
                  <div>
                    <strong>Desk Walk-In Registration:</strong> Seamlessly integrate walk-in patients alongside online digital bookings.
                  </div>
                </li>
                <li>
                  <span className="check-icon">✓</span>
                  <div>
                    <strong>Strict Tenant Isolation:</strong> Staff access is restricted solely to their assigned hospital facility.
                  </div>
                </li>
                <li>
                  <span className="check-icon">✓</span>
                  <div>
                    <strong>Audited Lifecycle States:</strong> Waiting, Calling, In-Consultation, Completed, and No-Show transitions enforced authoritatively.
                  </div>
                </li>
              </ul>
              <Link to="/profile" className="panel-btn outline">
                Staff & Admin Sign In →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 4. User Entry Points Banner */}
      <section className="entry-cta-section">
        <div className="section-container">
          <div className="cta-card">
            <div className="cta-content">
              <h2>Ready to Experience QueueLess?</h2>
              <p>
                Join thousands of patients saving precious hours, or empower your healthcare facility with digital queue intelligence.
              </p>
            </div>
            <div className="cta-buttons">
              <Link to="/hospitals" className="btn-cta-primary">
                Book a Patient Token
              </Link>
              <Link to="/profile" className="btn-cta-secondary">
                Healthcare Staff Sign In
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default Landing;

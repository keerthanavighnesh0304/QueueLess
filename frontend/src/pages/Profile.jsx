import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { checkHealthApi, fetchCurrentUserApi } from '../api/auth';
import './Profile.css';

function Profile() {
  const {
    user,
    isAuthenticated,
    isLoading: isAuthLoading,
    error: authError,
    sessionExpiredNotice,
    login,
    logout,
    clearError,
  } = useAuth();

  // Login form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Backend health state
  const [health, setHealth] = useState(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState('');

  // Protected API live check state
  const [testMeStatus, setTestMeStatus] = useState('');
  const [isTestingMe, setIsTestingMe] = useState(false);

  // Load backend health check on component mount
  useEffect(() => {
    loadHealth();
  }, []);

  async function loadHealth() {
    setIsHealthLoading(true);
    setHealthError('');
    try {
      const data = await checkHealthApi();
      setHealth(data);
    } catch (err) {
      setHealthError(err.message || 'Failed to reach backend health endpoint.');
    } finally {
      setIsHealthLoading(false);
    }
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();
    if (isSubmitting) return; // Prevent double submission

    if (!email.trim() || !password) {
      setFormError('Please enter both email and password.');
      return;
    }

    setFormError('');
    clearError();
    setIsSubmitting(true);

    try {
      await login(email.trim(), password);
      setPassword(''); // Clear password immediately upon success
    } catch (err) {
      setFormError(err.message || 'Login failed. Please verify your credentials.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleVerifyProtectedMe() {
    setIsTestingMe(true);
    setTestMeStatus('');
    try {
      const liveUser = await fetchCurrentUserApi();
      setTestMeStatus(`Verified at ${new Date().toLocaleTimeString()}: Server recognized user #${liveUser.id} (${liveUser.role})`);
    } catch (err) {
      setTestMeStatus(`Verification failed: ${err.message}`);
    } finally {
      setIsTestingMe(false);
    }
  }

  if (isAuthLoading) {
    return (
      <main className="profile-page">
        <div className="profile-card profile-loading">
          <div className="spinner" />
          <p>Validating authentication session...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="profile-page">
      <div className="profile-container">

        {/* System Health Status Panel */}
        <section className="profile-card health-card">
          <div className="card-header">
            <div>
              <h2>Backend Integration Status</h2>
              <p className="card-subtitle">Live health check against FastAPI backend</p>
            </div>
            <button
              type="button"
              className="refresh-button"
              onClick={loadHealth}
              disabled={isHealthLoading}
            >
              {isHealthLoading ? 'Checking...' : 'Refresh Health'}
            </button>
          </div>

          {healthError ? (
            <div className="alert alert-error" role="alert">
              <strong>Connection Error:</strong> {healthError}
            </div>
          ) : health ? (
            <div className="health-badges">
              <div className="health-item">
                <span className="label">Server Status:</span>
                <span className={`badge ${health.status === 'healthy' ? 'badge-success' : 'badge-warning'}`}>
                  {health.status}
                </span>
              </div>
              <div className="health-item">
                <span className="label">Database:</span>
                <span className={`badge ${health.database_connected ? 'badge-success' : 'badge-danger'}`}>
                  {health.database_connected ? `${health.database_type} Connected` : 'Disconnected'}
                </span>
              </div>
            </div>
          ) : (
            <p className="loading-text">Loading health status...</p>
          )}
        </section>

        {/* Session Expired Alert */}
        {sessionExpiredNotice && (
          <div className="alert alert-warning" role="alert">
            <strong>Session Notice:</strong> {sessionExpiredNotice}
          </div>
        )}

        {/* Authenticated Profile View */}
        {isAuthenticated && user ? (
          <section className="profile-card">
            <div className="card-header">
              <div>
                <h1>User Profile</h1>
                <p className="card-subtitle">Authenticated session verified via Bearer token</p>
              </div>
              <span className={`role-badge role-${user.role.toLowerCase()}`}>
                {user.role}
              </span>
            </div>

            <div className="profile-grid">
              <div className="profile-field">
                <span className="field-label">Full Name</span>
                <span className="field-value">{user.full_name}</span>
              </div>
              <div className="profile-field">
                <span className="field-label">Email Address</span>
                <span className="field-value">{user.email}</span>
              </div>
              <div className="profile-field">
                <span className="field-label">Phone</span>
                <span className="field-value">{user.phone || 'Not provided'}</span>
              </div>
              <div className="profile-field">
                <span className="field-label">Account Status</span>
                <span className="field-value">
                  <span className={`account-status-badge ${user.is_active ? 'status-active' : 'status-inactive'}`}>
                    <span className="status-indicator-dot" />
                    {user.is_active ? 'Active Account' : 'Inactive Account'}
                  </span>
                </span>
              </div>
              {user.hospital_id && (
                <div className="profile-field">
                  <span className="field-label">Assigned Hospital</span>
                  <span className="field-value">Hospital #{user.hospital_id}</span>
                </div>
              )}
            </div>

            <div className="role-navigation-actions">
              {user.role === 'PATIENT' && (
                <Link
                  to="/my-queue"
                  className="primary-action-btn"
                >
                  <span>Go to My Queue & Tickets</span>
                  <span className="btn-arrow" aria-hidden="true">→</span>
                </Link>
              )}
              {(user.role === 'STAFF' || user.role === 'ADMIN') && (
                <Link
                  to="/staff"
                  className="primary-action-btn"
                >
                  <span>Open Staff Queue Dashboard</span>
                  <span className="btn-arrow" aria-hidden="true">→</span>
                </Link>
              )}
              {user.role === 'ADMIN' && (
                <Link
                  to="/admin"
                  className="secondary-action-btn"
                >
                  <span>Open Admin Approvals</span>
                  <span className="btn-arrow" aria-hidden="true">→</span>
                </Link>
              )}
            </div>

            <div className="verification-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={handleVerifyProtectedMe}
                disabled={isTestingMe}
              >
                {isTestingMe ? 'Verifying...' : 'Verify GET /api/auth/me'}
              </button>

              <button
                type="button"
                className="logout-button"
                onClick={logout}
              >
                Log Out
              </button>
            </div>

            {testMeStatus && (
              <div className="alert alert-info">
                {testMeStatus}
              </div>
            )}
          </section>
        ) : (
          /* Unauthenticated Sign In View */
          <section className="profile-card">
            <div className="card-header">
              <div>
                <h1>Sign In</h1>
                <p className="card-subtitle">Authenticate with your QueueLess account to manage queues</p>
              </div>
            </div>

            {(formError || authError) && (
              <div className="alert alert-error" role="alert">
                <strong>Login Failed:</strong> {formError || authError}
              </div>
            )}

            <form onSubmit={handleLoginSubmit} className="login-form">
              <div className="form-group">
                <label htmlFor="login-email">Email Address</label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (formError) setFormError('');
                  }}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="login-password">Password</label>
                <input
                  id="login-password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (formError) setFormError('');
                  }}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <button
                type="submit"
                className="login-submit-button"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Signing In...' : 'Sign In'}
              </button>
            </form>

            {import.meta.env.DEV && (
              <div className="demo-accounts-bar">
                <span className="demo-accounts-title">Quick Demo Logins (Dev Mode):</span>
                <div className="demo-buttons-group">
                  <button
                    type="button"
                    className="demo-btn"
                    onClick={() => {
                      setEmail('patient.demo@queueless.local');
                      setPassword('DemoPassword123!');
                    }}
                  >
                    Patient
                  </button>
                  <button
                    type="button"
                    className="demo-btn"
                    onClick={() => {
                      setEmail('staff.citycare@queueless.local');
                      setPassword('DemoPassword123!');
                    }}
                  >
                    Staff (City Care)
                  </button>
                  <button
                    type="button"
                    className="demo-btn"
                    onClick={() => {
                      setEmail('admin@queueless.local');
                      setPassword('admin0304');
                    }}
                  >
                    Admin
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

      </div>
    </main>
  );
}

export default Profile;

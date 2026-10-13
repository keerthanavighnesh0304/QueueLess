import { useState, useEffect, useCallback } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { fetchHospitalDepartmentsApi, fetchHospitalDetailsApi } from '../api/hospitals';
import { createDepartmentApi } from '../api/staff';
import './StaffDepartments.css';

function StaffDepartments() {
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const hospitalId = user?.hospital_id || (user?.role === 'ADMIN' ? 1 : null);

  const [departments, setDepartments] = useState([]);
  const [hospitalInfo, setHospitalInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successNotice, setSuccessNotice] = useState(null);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [reloadKey, setReloadKey] = useState(0);

  const refreshDepartments = useCallback(() => {
    setIsLoading(true);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    if (!isAuthenticated || (user?.role !== 'STAFF' && user?.role !== 'ADMIN') || !hospitalId) {
      return;
    }

    let isMounted = true;
    const abortController = new AbortController();

    async function loadData() {
      try {
        const [deptList, hosp] = await Promise.all([
          fetchHospitalDepartmentsApi(hospitalId, { signal: abortController.signal }),
          fetchHospitalDetailsApi(hospitalId, { signal: abortController.signal }).catch(() => null),
        ]);
        if (isMounted) {
          setDepartments(deptList || []);
          if (hosp) setHospitalInfo(hosp);
          setError(null);
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setError(err.message || 'Failed to load clinical departments.');
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [isAuthenticated, user, hospitalId, reloadKey]);

  async function handleAddDepartment(e) {
    e.preventDefault();
    setFormError(null);
    setSuccessNotice(null);

    const cleanName = name.trim();
    if (!cleanName) {
      setFormError('Department name is required.');
      return;
    }
    if (cleanName.length < 2) {
      setFormError('Department name must be at least 2 characters.');
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await createDepartmentApi(hospitalId, {
        name: cleanName,
        description: description.trim() || undefined,
      });
      setSuccessNotice(`Department "${created.name}" created successfully.`);
      setName('');
      setDescription('');
      refreshDepartments();
    } catch (err) {
      setFormError(err.message || 'Failed to create department.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isAuthLoading) {
    return (
      <main className="staff-mgmt-page">
        <div className="staff-mgmt-container">
          <div className="staff-mgmt-card state-card">
            <div className="spinner" />
            <p>Verifying hospital staff privileges...</p>
          </div>
        </div>
      </main>
    );
  }

  if (!isAuthenticated || (user?.role !== 'STAFF' && user?.role !== 'ADMIN')) {
    return (
      <main className="staff-mgmt-page">
        <div className="staff-mgmt-container">
          <div className="staff-mgmt-card state-card access-denied">
            <div className="state-icon">🔒</div>
            <h2>Staff Access Restricted</h2>
            <p>You must be signed in with a Hospital Staff or Administrator account to manage departments.</p>
            <Link to="/profile" className="primary-action-btn">
              Sign In with Staff Account
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (user?.role === 'STAFF' && !user?.hospital_id) {
    return (
      <main className="staff-mgmt-page">
        <div className="staff-mgmt-container">
          <div className="staff-mgmt-card state-card">
            <div className="state-icon">⚠️</div>
            <h2>No Hospital Assigned</h2>
            <p>This staff account is not assigned to a registered healthcare facility. Please contact your platform administrator.</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="staff-mgmt-page">
      <div className="staff-mgmt-container">
        {/* Navigation & Header */}
        <header className="staff-mgmt-header">
          <div className="header-breadcrumbs">
            <Link to="/staff">Hospital Portal</Link>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current">Clinical Departments</span>
          </div>
          <div className="header-main-row">
            <div>
              <h1>Manage Departments</h1>
              <p className="header-subtitle">
                {hospitalInfo?.name || 'Your Hospital'} — Configure clinical specialties and departments
              </p>
            </div>
            <nav className="staff-portal-tabs" aria-label="Hospital Management Tabs">
              <NavLink to="/staff" end className={({ isActive }) => `tab-btn ${isActive ? 'active' : ''}`}>
                Queue Operations
              </NavLink>
              <NavLink to="/staff/departments" className={({ isActive }) => `tab-btn ${isActive ? 'active' : ''}`}>
                Departments ({departments.length})
              </NavLink>
              <NavLink to="/staff/doctors" className={({ isActive }) => `tab-btn ${isActive ? 'active' : ''}`}>
                Doctors
              </NavLink>
              <Link to="/staff?schedule=true" className="tab-btn schedule-tab-btn">
                + Schedule Session
              </Link>
            </nav>
          </div>
        </header>

        {/* Global Notifications */}
        {successNotice && (
          <div className="mgmt-alert mgmt-alert-success" role="status">
            <span>✓ {successNotice}</span>
            <button type="button" className="alert-close-btn" onClick={() => setSuccessNotice(null)} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}

        {error && (
          <div className="mgmt-alert mgmt-alert-error" role="alert">
            <span>⚠️ {error}</span>
            <button type="button" className="alert-close-btn" onClick={() => setError(null)} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}

        {/* Content Layout */}
        <div className="staff-mgmt-grid">
          {/* Add Department Form */}
          <section className="staff-mgmt-card form-card" aria-labelledby="add-dept-title">
            <div className="card-header">
              <h2 id="add-dept-title">Add Department</h2>
              <p>Register a new clinical department for doctor assignments</p>
            </div>

            {formError && (
              <div className="form-inline-alert" role="alert">
                {formError}
              </div>
            )}

            <form onSubmit={handleAddDepartment} className="mgmt-form">
              <div className="form-field">
                <label htmlFor="dept-name">Department Name *</label>
                <input
                  id="dept-name"
                  type="text"
                  required
                  placeholder="e.g. Cardiology, Orthopedics, Pediatrics"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isSubmitting}
                />
                <span className="field-hint">Clinical specialty or outpatient division name</span>
              </div>

              <div className="form-field">
                <label htmlFor="dept-desc">Description (Optional)</label>
                <textarea
                  id="dept-desc"
                  rows={3}
                  placeholder="e.g. Outpatient cardiac consultations and diagnostic ECG referrals"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>

              <div className="form-actions">
                <button type="submit" className="primary-action-btn" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating Department...' : '+ Add Department'}
                </button>
              </div>
            </form>
          </section>

          {/* Department Directory List */}
          <section className="staff-mgmt-card list-card" aria-labelledby="dept-list-title">
            <div className="card-header list-card-header">
              <div>
                <h2 id="dept-list-title">Existing Departments</h2>
                <p>Configured clinical units accepting outpatient bookings</p>
              </div>
              <button
                type="button"
                className="secondary-refresh-btn"
                onClick={refreshDepartments}
                disabled={isLoading}
                title="Refresh departments list"
              >
                {isLoading ? 'Refreshing...' : '↻ Refresh'}
              </button>
            </div>

            {isLoading && departments.length === 0 ? (
              <div className="list-loading-state">
                <div className="spinner" />
                <p>Loading departments...</p>
              </div>
            ) : departments.length === 0 ? (
              <div className="list-empty-state">
                <div className="empty-icon">🏥</div>
                <h3>No Departments Added Yet</h3>
                <p>Create your first clinical department using the form on the left to start adding doctors.</p>
              </div>
            ) : (
              <div className="dept-items-list">
                {departments.map((dept) => (
                  <article key={dept.id} className="dept-item-card">
                    <div className="dept-item-header">
                      <div className="dept-item-title-group">
                        <span className="dept-id-badge">ID #{dept.id}</span>
                        <h3>{dept.name}</h3>
                      </div>
                      <Link
                        to={`/staff/doctors?department_id=${dept.id}`}
                        className="view-doctors-link"
                        title={`View doctors in ${dept.name}`}
                      >
                        Doctors in Department →
                      </Link>
                    </div>
                    {dept.description && (
                      <p className="dept-item-description">{dept.description}</p>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

export default StaffDepartments;

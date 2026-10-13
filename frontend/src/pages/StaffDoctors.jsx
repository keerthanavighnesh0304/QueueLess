import { useState, useEffect, useCallback } from 'react';
import { Link, NavLink, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import {
  fetchHospitalDoctorsApi,
  fetchHospitalDepartmentsApi,
  fetchHospitalDetailsApi,
} from '../api/hospitals';
import { createDoctorApi } from '../api/staff';
import './StaffDoctors.css';

function StaffDoctors() {
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const hospitalId = user?.hospital_id || (user?.role === 'ADMIN' ? 1 : null);

  const [doctors, setDoctors] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [hospitalInfo, setHospitalInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successNotice, setSuccessNotice] = useState(null);

  // Form state
  const [fullName, setFullName] = useState('');
  const [departmentId, setDepartmentId] = useState(() => searchParams.get('department_id') || '');
  const [specialization, setSpecialization] = useState('');
  const [qualification, setQualification] = useState('');
  const [ticketPrefix, setTicketPrefix] = useState('DOC');
  const [avgTimeMins, setAvgTimeMins] = useState(15);
  const [formError, setFormError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Filter state derived from searchParams
  const filterDepartmentId = searchParams.get('department_id') || '';

  const [reloadKey, setReloadKey] = useState(0);

  const refreshDoctors = useCallback(() => {
    setIsLoading(true);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    if (!isAuthenticated || (user?.role !== 'STAFF' && user?.role !== 'ADMIN') || !hospitalId) {
      return;
    }

    let isMounted = true;
    const abortController = new AbortController();

    async function fetchData() {
      try {
        const [docList, deptList, hosp] = await Promise.all([
          fetchHospitalDoctorsApi(hospitalId, { signal: abortController.signal }),
          fetchHospitalDepartmentsApi(hospitalId, { signal: abortController.signal }),
          fetchHospitalDetailsApi(hospitalId, { signal: abortController.signal }).catch(() => null),
        ]);
        if (isMounted) {
          setDoctors(docList || []);
          setDepartments(deptList || []);
          if (hosp) setHospitalInfo(hosp);
          setError(null);
        }
      } catch (err) {
        if (isMounted && err?.name !== 'AbortError') {
          setError(err.message || 'Failed to load doctors and departments.');
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [isAuthenticated, user, hospitalId, reloadKey]);

  function handleFilterChange(deptId) {
    if (deptId) {
      setSearchParams({ department_id: deptId });
    } else {
      setSearchParams({});
    }
  }

  // Derive initial ticket prefix from specialization or doctor name
  function handleSpecializationChange(val) {
    setSpecialization(val);
    const clean = val.replace(/[^A-Za-z]/g, '').toUpperCase();
    if (clean.length >= 3 && ticketPrefix === 'DOC') {
      setTicketPrefix(clean.slice(0, 4));
    }
  }

  async function handleAddDoctor(e) {
    e.preventDefault();
    setFormError(null);
    setSuccessNotice(null);

    const cleanName = fullName.trim();
    if (!cleanName || cleanName.length < 2) {
      setFormError('Doctor full name must be at least 2 characters.');
      return;
    }

    if (!departmentId) {
      setFormError('Please select a clinical department for this doctor.');
      return;
    }

    const cleanSpec = specialization.trim();
    if (!cleanSpec || cleanSpec.length < 2) {
      setFormError('Specialization must be at least 2 characters.');
      return;
    }

    const cleanPrefix = ticketPrefix.trim().toUpperCase() || 'DOC';
    if (cleanPrefix.length > 10) {
      setFormError('Ticket prefix cannot exceed 10 characters.');
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await createDoctorApi(hospitalId, {
        department_id: Number(departmentId),
        full_name: cleanName,
        qualification: qualification.trim() || undefined,
        specialization: cleanSpec,
        ticket_prefix: cleanPrefix,
        avg_consultation_time_mins: Number(avgTimeMins) || 15,
      });

      setSuccessNotice(`Doctor "${created.full_name}" registered successfully under ${departments.find((d) => d.id === Number(departmentId))?.name || 'Department'}.`);
      setFullName('');
      setSpecialization('');
      setQualification('');
      setTicketPrefix('DOC');
      setAvgTimeMins(15);
      refreshDoctors();
    } catch (err) {
      setFormError(err.message || 'Failed to register doctor.');
    } finally {
      setIsSubmitting(false);
    }
  }

  const filteredDoctors = filterDepartmentId
    ? doctors.filter((doc) => doc.department_id === Number(filterDepartmentId))
    : doctors;

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
            <p>You must be signed in with a Hospital Staff or Administrator account to manage doctors.</p>
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
            <span className="breadcrumb-current">Practicing Doctors</span>
          </div>
          <div className="header-main-row">
            <div>
              <h1>Manage Doctors</h1>
              <p className="header-subtitle">
                {hospitalInfo?.name || 'Your Hospital'} — Register physicians and assign OPD ticket prefixes
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
                Doctors ({doctors.length})
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
          {/* Add Doctor Form */}
          <section className="staff-mgmt-card form-card" aria-labelledby="add-doc-title">
            <div className="card-header">
              <h2 id="add-doc-title">Register Doctor</h2>
              <p>Add a practicing physician under an existing department</p>
            </div>

            {departments.length === 0 && !isLoading ? (
              <div className="empty-dep-warning">
                <div className="warning-icon">⚠️</div>
                <h3>No Departments Available</h3>
                <p>
                  Doctors must belong to a clinical department. You need to create at least one department before registering doctors.
                </p>
                <Link to="/staff/departments" className="primary-action-btn">
                  👉 Create First Department
                </Link>
              </div>
            ) : (
              <>
                {formError && (
                  <div className="form-inline-alert" role="alert">
                    {formError}
                  </div>
                )}

                <form onSubmit={handleAddDoctor} className="mgmt-form">
                  <div className="form-field">
                    <label htmlFor="doc-name">Doctor Full Name *</label>
                    <input
                      id="doc-name"
                      type="text"
                      required
                      placeholder="e.g. Dr. Kavitha Sundaram"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="form-field">
                    <label htmlFor="doc-dept">Clinical Department *</label>
                    <select
                      id="doc-dept"
                      required
                      value={departmentId}
                      onChange={(e) => setDepartmentId(e.target.value)}
                      disabled={isSubmitting}
                    >
                      <option value="">-- Select Hospital Department --</option>
                      {departments.map((dept) => (
                        <option key={dept.id} value={dept.id}>
                          {dept.name} (ID #{dept.id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-field">
                    <label htmlFor="doc-spec">Specialization *</label>
                    <input
                      id="doc-spec"
                      type="text"
                      required
                      placeholder="e.g. Interventional Cardiology, Pediatrician"
                      value={specialization}
                      onChange={(e) => handleSpecializationChange(e.target.value)}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="form-field">
                    <label htmlFor="doc-qual">Qualification (Optional)</label>
                    <input
                      id="doc-qual"
                      type="text"
                      placeholder="e.g. MBBS, MD, DM"
                      value={qualification}
                      onChange={(e) => setQualification(e.target.value)}
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="form-row-2">
                    <div className="form-field">
                      <label htmlFor="doc-prefix">Ticket Prefix *</label>
                      <input
                        id="doc-prefix"
                        type="text"
                        required
                        maxLength={10}
                        placeholder="e.g. CARD"
                        value={ticketPrefix}
                        onChange={(e) => setTicketPrefix(e.target.value.toUpperCase())}
                        disabled={isSubmitting}
                      />
                      <span className="field-hint">Used for OPD tokens (e.g. CARD-001)</span>
                    </div>

                    <div className="form-field">
                      <label htmlFor="doc-time">Avg Time (mins)</label>
                      <input
                        id="doc-time"
                        type="number"
                        min={1}
                        max={120}
                        value={avgTimeMins}
                        onChange={(e) => setAvgTimeMins(e.target.value)}
                        disabled={isSubmitting}
                      />
                      <span className="field-hint">Default queue slot estimation</span>
                    </div>
                  </div>

                  <div className="form-actions">
                    <button type="submit" className="primary-action-btn" disabled={isSubmitting}>
                      {isSubmitting ? 'Registering Doctor...' : '+ Register Doctor'}
                    </button>
                  </div>
                </form>
              </>
            )}
          </section>

          {/* Doctor Directory List */}
          <section className="staff-mgmt-card list-card" aria-labelledby="doc-list-title">
            <div className="card-header list-card-header">
              <div>
                <h2 id="doc-list-title">Doctor Directory</h2>
                <p>Active physicians currently eligible for OPD consultation sessions</p>
              </div>

              <div className="list-header-controls">
                {departments.length > 0 && (
                  <select
                    className="dept-filter-select"
                    value={filterDepartmentId}
                    onChange={(e) => handleFilterChange(e.target.value)}
                    aria-label="Filter by department"
                  >
                    <option value="">All Departments ({doctors.length})</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  type="button"
                  className="secondary-refresh-btn"
                  onClick={refreshDoctors}
                  disabled={isLoading}
                  title="Refresh doctor directory"
                >
                  {isLoading ? '...' : '↻'}
                </button>
              </div>
            </div>

            {isLoading && doctors.length === 0 ? (
              <div className="list-loading-state">
                <div className="spinner" />
                <p>Loading practicing doctors...</p>
              </div>
            ) : filteredDoctors.length === 0 ? (
              <div className="list-empty-state">
                <div className="empty-icon">🩺</div>
                <h3>{doctors.length === 0 ? 'No Doctors Registered' : 'No Doctors in this Department'}</h3>
                <p>
                  {doctors.length === 0
                    ? 'Register your first doctor using the form to start scheduling consultation sessions.'
                    : 'Try selecting a different department filter or register a doctor in this department.'}
                </p>
              </div>
            ) : (
              <div className="doctor-cards-grid">
                {filteredDoctors.map((doc) => {
                  const dept = departments.find((d) => d.id === doc.department_id);
                  return (
                    <article key={doc.id} className="doctor-item-card">
                      <div className="doc-item-top">
                        <div className="doc-avatar">{doc.full_name.charAt(doc.full_name.startsWith('Dr.') ? 4 : 0) || 'D'}</div>
                        <div className="doc-info-block">
                          <h3>{doc.full_name}</h3>
                          {doc.qualification && <span className="doc-qualification">{doc.qualification}</span>}
                          <p className="doc-specialization">{doc.specialization}</p>
                        </div>
                      </div>

                      <div className="doc-badges-row">
                        <span className="badge-dept" title="Assigned Department">
                          🏥 {dept?.name || `Dept #${doc.department_id}`}
                        </span>
                        <span className="badge-prefix" title="Ticket sequence token prefix">
                          🎟 Prefix: {doc.ticket_prefix}
                        </span>
                        <span className="badge-duration" title="Estimated consultation time">
                          ⏱ ~{doc.avg_consultation_time_mins}m
                        </span>
                      </div>

                      <div className="doc-card-footer">
                        <Link
                          to={`/staff?schedule=true&doctor_id=${doc.id}`}
                          className="schedule-for-doc-btn"
                        >
                          + Schedule Session for Doctor
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

export default StaffDoctors;

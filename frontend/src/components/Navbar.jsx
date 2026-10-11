import { useState } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useTheme } from '../context/useTheme';
import './Navbar.css';

function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  function closeMobile() {
    setMobileMenuOpen(false);
  }

  return (
    <nav className="navbar" aria-label="Main Navigation">
      <div className="navbar-container">
        {/* Brand */}
        <Link to="/" className="navbar-brand" onClick={closeMobile}>
          <div className="brand-icon">Q</div>
          <div className="brand-text">
            <span className="brand-title">QueueLess</span>
            <span className="brand-tagline">Healthcare OPD Queue</span>
          </div>
        </Link>

        {/* Mobile menu toggle */}
        <button
          type="button"
          className="mobile-toggle"
          aria-label={mobileMenuOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
          aria-expanded={mobileMenuOpen}
          onClick={() => setMobileMenuOpen((prev) => !prev)}
        >
          <span className="hamburger-bar" />
          <span className="hamburger-bar" />
          <span className="hamburger-bar" />
        </button>

        {/* Links and Actions */}
        <div className={`navbar-menu ${mobileMenuOpen ? 'mobile-open' : ''}`}>
          <div className="navbar-links">
            <NavLink to="/" end onClick={closeMobile}>
              Home
            </NavLink>
            <NavLink to="/hospitals" onClick={closeMobile}>
              Find Hospitals
            </NavLink>
            <NavLink to="/my-queue" onClick={closeMobile}>
              My Queue
            </NavLink>

            {isAuthenticated && (user?.role === 'STAFF' || user?.role === 'ADMIN') && (
              <NavLink to="/staff" onClick={closeMobile} className="nav-role-link">
                Staff Queue
              </NavLink>
            )}

            {isAuthenticated && user?.role === 'ADMIN' && (
              <NavLink to="/admin" onClick={closeMobile} className="nav-role-link">
                Approvals
              </NavLink>
            )}
          </div>

          <div className="navbar-actions">
            {/* Theme Toggle Button */}
            <button
              type="button"
              className="theme-toggle-btn"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
            >
              {theme === 'dark' ? (
                // Sun Icon for Dark Mode (to switch to light)
                <svg className="theme-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                // Moon Icon for Light Mode (to switch to dark)
                <svg className="theme-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>

            {/* Auth / Profile Actions */}
            {isAuthenticated && user ? (
              <div className="nav-auth-group">
                <Link to="/profile" className="nav-profile-pill" onClick={closeMobile}>
                  <span className="profile-name">{user.full_name.split(' ')[0]}</span>
                  <span className={`role-badge role-${user.role.toLowerCase()}`}>{user.role}</span>
                </Link>
                <button
                  type="button"
                  className="nav-logout-btn"
                  onClick={() => {
                    closeMobile();
                    logout();
                  }}
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <Link to="/profile" className="nav-signin-btn" onClick={closeMobile}>
                Sign In
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
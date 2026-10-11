/**
 * Centralized API configuration for the QueueLess frontend.
 *
 * NOTE: Variables prefixed with VITE_ are embedded into client JavaScript bundles at build time.
 * They are visible in browser network inspectors and source code.
 * NEVER place backend secrets, database passwords, or JWT secret keys here.
 */

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

// Strip any trailing slash for consistent route concatenation
export const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '');

/**
 * Builds a fully qualified API endpoint URL.
 * Accepts leading slashes or relative paths and ensures clean URL concatenation.
 *
 * @param {string} path - API endpoint path (e.g. '/auth/login' or 'auth/login')
 * @returns {string} - Fully resolved URL
 */
export function buildApiUrl(path) {
  if (!path) return API_BASE_URL;
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
}

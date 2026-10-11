/**
 * Centralized API Client for QueueLess.
 *
 * Built strictly on the browser's native `fetch` API (zero external dependencies).
 * Features:
 * - Automated JSON payload serialization and Content-Type negotiation.
 * - Authoritative Bearer token attachment for authenticated requests.
 * - Origin boundary check: Bearer tokens are NEVER transmitted to external origins.
 * - Normalized FastAPI error message parsing (including Pydantic 422 schemas).
 * - Distinguishes between login credential rejections and expired session tokens.
 * - Dispatches 'queueless:session-expired' events without triggering redirect loops.
 */

import { API_BASE_URL, buildApiUrl } from './config';
import { getToken, clearAuth } from '../utils/tokenStorage';

/**
 * Custom error class encapsulating API and network failures.
 */
export class ApiError extends Error {
  constructor(message, { status = 0, statusText = '', data = null, isNetworkError = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.data = data;
    this.isNetworkError = isNetworkError;
    this.isUnauthorized = status === 401;
    this.isForbidden = status === 403;
    this.isNotFound = status === 404;
  }
}

/**
 * Formats FastAPI error payloads into a clean, human-readable string.
 *
 * @param {any} data - Parsed JSON response body
 * @param {number} status - HTTP status code
 * @returns {string}
 */
export function extractErrorMessage(data, status) {
  if (!data) {
    if (status === 401) return 'Authentication required. Please sign in.';
    if (status === 403) return 'You do not have permission to perform this action.';
    if (status === 404) return 'Requested resource not found.';
    if (status >= 500) return 'Server error. Please try again later.';
    return `Request failed with status ${status}`;
  }

  // FastAPI { "detail": "string" }
  if (typeof data.detail === 'string') {
    return data.detail;
  }

  // FastAPI Pydantic validation error array: { "detail": [{ "loc": [...], "msg": "..." }] }
  if (Array.isArray(data.detail)) {
    const messages = data.detail.map((err) => {
      const field = Array.isArray(err.loc) ? err.loc[err.loc.length - 1] : '';
      return field && field !== 'body' ? `${field}: ${err.msg}` : err.msg;
    });
    return messages.join('; ');
  }

  if (typeof data.message === 'string') {
    return data.message;
  }

  return `Request failed with status ${status}`;
}

/**
 * Dispatches a custom window event notifying components of session expiration.
 * @param {string} reason
 */
function notifySessionExpired(reason) {
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(
      new CustomEvent('queueless:session-expired', {
        detail: { reason: reason || 'Session has expired' },
      })
    );
  }
}

/**
 * Centralized request dispatcher.
 *
 * @param {string} endpoint - API path (e.g. '/auth/login' or 'hospitals')
 * @param {object} [options] - Fetch configuration options
 * @param {boolean} [options.skipAuth] - Explicitly skip Bearer token injection
 * @param {boolean} [options.isLoginRequest] - Flag indicating a login attempt (401 must not trigger session expiration)
 * @returns {Promise<any>}
 */
export async function apiClient(endpoint, options = {}) {
  const {
    body,
    headers: customHeaders = {},
    skipAuth = false,
    isLoginRequest = false,
    ...restOptions
  } = options;

  const url = buildApiUrl(endpoint);

  // Headers setup
  const headers = new Headers(customHeaders);

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  // Attach Bearer token if available and request is directed to the authoritative API base
  if (!skipAuth && !headers.has('Authorization') && url.startsWith(API_BASE_URL)) {
    const token = getToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  // Handle request body
  let serializedBody = body;
  if (body !== undefined && body !== null) {
    if (
      typeof body === 'object' &&
      !(body instanceof FormData) &&
      !(body instanceof Blob) &&
      !(body instanceof URLSearchParams)
    ) {
      serializedBody = JSON.stringify(body);
      if (!headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
      }
    }
  }

  let response;
  try {
    response = await fetch(url, {
      ...restOptions,
      headers,
      body: serializedBody,
    });
  } catch (err) {
    if (err && (err.name === 'AbortError' || err.code === 20)) {
      throw err;
    }
    throw new ApiError(
      'Unable to connect to the QueueLess backend. Please check your network or verify the backend server is running.',
      {
        status: 0,
        statusText: 'Network Error',
        isNetworkError: true,
      }
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  // Parse response body
  const contentType = response.headers.get('content-type') || '';
  let responseData = null;
  if (contentType.includes('application/json')) {
    try {
      responseData = await response.json();
    } catch {
      responseData = null;
    }
  } else {
    try {
      responseData = await response.text();
    } catch {
      responseData = null;
    }
  }

  // Check for HTTP errors (status outside 200..299)
  if (!response.ok) {
    const errorMessage = extractErrorMessage(responseData, response.status);

    // Safe 401 handling:
    // If a protected request (NOT login) returns 401, clear stored credentials and signal expiration
    if (response.status === 401 && !isLoginRequest) {
      clearAuth();
      notifySessionExpired(errorMessage);
    }

    throw new ApiError(errorMessage, {
      status: response.status,
      statusText: response.statusText,
      data: responseData,
    });
  }

  return responseData;
}

// Convenience helpers
apiClient.get = (endpoint, options) => apiClient(endpoint, { ...options, method: 'GET' });
apiClient.post = (endpoint, body, options) => apiClient(endpoint, { ...options, method: 'POST', body });
apiClient.put = (endpoint, body, options) => apiClient(endpoint, { ...options, method: 'PUT', body });
apiClient.patch = (endpoint, body, options) => apiClient(endpoint, { ...options, method: 'PATCH', body });
apiClient.delete = (endpoint, options) => apiClient(endpoint, { ...options, method: 'DELETE' });

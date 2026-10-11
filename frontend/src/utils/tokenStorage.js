/**
 * Centralized Token Storage Utility for QueueLess.
 *
 * SECURITY NOTE & XSS CONSIDERATION:
 * Storing JWT tokens in browser `localStorage` provides persistent authentication across tabs
 * and page reloads, but it is NOT immune to Cross-Site Scripting (XSS) attacks. If malicious
 * third-party JavaScript executes in the page context, localStorage can be read.
 *
 * To minimize exposure:
 * 1. Access tokens have an authoritative server-enforced expiration (60 minutes).
 * 2. Token reads/writes/clears are strictly isolated inside this module; direct access across
 *    components is prohibited.
 * 3. Never log, print, or expose tokens in console statements, error objects, or DOM nodes.
 * 4. All HTML rendering is sanitized by React's native JSX escaping.
 */

const TOKEN_KEY = 'queueless_access_token';
const USER_KEY = 'queueless_user_profile';

/**
 * Safely retrieves the stored JWT access token.
 * @returns {string|null}
 */
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Safely persists the JWT access token.
 * @param {string} token
 */
export function setToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Gracefully handle storage quota or private-browsing restrictions
  }
}

/**
 * Safely retrieves the cached user profile object.
 * @returns {object|null}
 */
export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Safely persists the cached user profile object.
 * @param {object} user
 */
export function setUser(user) {
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  } catch {
    // Gracefully handle storage quota or private-browsing restrictions
  }
}

/**
 * Atomically clears all authentication credentials and cached profile data.
 */
export function clearAuth() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // Silently proceed
  }
}

/**
 * Checks whether an access token is currently held in storage.
 * @returns {boolean}
 */
export function hasToken() {
  return Boolean(getToken());
}

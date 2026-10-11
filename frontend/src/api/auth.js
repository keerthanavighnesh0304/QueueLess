/**
 * Authoritative Authentication & Health API service functions.
 * Connects directly to the FastAPI endpoints verified in Phase 2.
 */

import { apiClient } from './client';

/**
 * Performs credential authentication.
 *
 * @param {object} credentials
 * @param {string} credentials.email
 * @param {string} credentials.password
 * @returns {Promise<{ access_token: string, token_type: string, expires_in_minutes: number, user: object }>}
 */
export async function loginApi({ email, password }) {
  return apiClient.post('/auth/login', { email, password }, { isLoginRequest: true });
}

/**
 * Fetches the currently authenticated user's profile.
 * Sends the Bearer token automatically via `apiClient`.
 *
 * @returns {Promise<object>} UserOut representation
 */
export async function fetchCurrentUserApi() {
  return apiClient.get('/auth/me');
}

/**
 * Checks backend and database health.
 *
 * @returns {Promise<{ status: string, database_connected: boolean, database_type: string }>}
 */
export async function checkHealthApi() {
  return apiClient.get('/health', { skipAuth: true });
}

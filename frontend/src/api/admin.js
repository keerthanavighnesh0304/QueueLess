import { apiClient } from './client';

/**
 * Lists all healthcare facilities awaiting administrative review.
 * Requires admin privileges.
 *
 * @param {object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<Array<object>>} List of HospitalOut objects
 */
export async function fetchPendingHospitalsApi({ signal } = {}) {
  return apiClient.get('/admin/hospitals/pending', { signal });
}

/**
 * Approves a pending hospital onboarding application.
 *
 * @param {number|string} hospitalId
 * @returns {Promise<object>} HospitalActionResponse
 */
export async function approveHospitalApi(hospitalId) {
  return apiClient.post(`/admin/hospitals/${hospitalId}/approve`);
}

/**
 * Rejects a pending hospital onboarding application.
 *
 * @param {number|string} hospitalId
 * @returns {Promise<object>} HospitalActionResponse
 */
export async function rejectHospitalApi(hospitalId) {
  return apiClient.post(`/admin/hospitals/${hospitalId}/reject`);
}

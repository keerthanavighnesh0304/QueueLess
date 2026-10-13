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

/**
 * Provisions the initial staff/manager account for an approved hospital.
 *
 * @param {number|string} hospitalId
 * @param {object} payload
 * @param {string} payload.email
 * @param {string} payload.full_name
 * @param {string} [payload.phone]
 * @param {string} [payload.initial_password]
 * @returns {Promise<object>} StaffProvisionResponse
 */
export async function provisionHospitalStaffApi(hospitalId, payload) {
  return apiClient.post(`/admin/hospitals/${hospitalId}/provision-staff`, payload);
}

/**
 * Authoritative Public Hospital Discovery & Queue Status Service.
 *
 * NOTE: All functions in this module are public and explicitly pass { skipAuth: true }.
 * This guarantees:
 * 1. Bearer tokens are NEVER attached to public browsing requests, preserving privacy and
 *    preventing token exposure in public logs.
 * 2. Unauthenticated and authenticated users receive identical public data.
 * 3. Never invokes the staff-only queue dashboard endpoint.
 */

import { apiClient } from './client';

/**
 * Lists approved hospitals eligible to accept bookings.
 *
 * @param {object} [params]
 * @param {string} [params.search] - Case-insensitive hospital name search
 * @param {string} [params.city] - Exact city filter
 * @returns {Promise<Array<object>>} List of HospitalOut objects
 */
export async function fetchHospitalsApi({ search, city, signal } = {}) {
  const queryParams = new URLSearchParams();
  if (search && search.trim()) queryParams.set('search', search.trim());
  if (city && city.trim()) queryParams.set('city', city.trim());

  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiClient.get(`/hospitals${queryString}`, { skipAuth: true, signal });
}

/**
 * Retrieves details for an approved hospital, including its clinical departments.
 *
 * @param {number|string} hospitalId
 * @param {object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<object>} HospitalDetailOut object
 */
export async function fetchHospitalDetailsApi(hospitalId, { signal } = {}) {
  return apiClient.get(`/hospitals/${hospitalId}`, { skipAuth: true, signal });
}

/**
 * Lists active practicing doctors for an approved hospital.
 *
 * @param {number|string} hospitalId
 * @param {object} [params]
 * @param {number|string} [params.departmentId]
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<Array<object>>} List of DoctorOut objects
 */
export async function fetchHospitalDoctorsApi(hospitalId, { departmentId, signal } = {}) {
  const queryParams = new URLSearchParams();
  if (departmentId) queryParams.set('department_id', String(departmentId));

  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiClient.get(`/hospitals/${hospitalId}/doctors${queryString}`, { skipAuth: true, signal });
}

/**
 * Lists consultation sessions for an approved hospital.
 * Defaults to session_date >= today unless a specific date is supplied.
 *
 * @param {number|string} hospitalId
 * @param {object} [params]
 * @param {string} [params.sessionDate] - ISO date string (YYYY-MM-DD)
 * @param {number|string} [params.doctorId]
 * @param {string} [params.status] - SCHEDULED, ACTIVE, PAUSED, COMPLETED
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<Array<object>>} List of ConsultationSessionOut objects
 */
export async function fetchHospitalSessionsApi(hospitalId, { sessionDate, doctorId, status, signal } = {}) {
  const queryParams = new URLSearchParams();
  if (sessionDate) queryParams.set('session_date', sessionDate);
  if (doctorId) queryParams.set('doctor_id', String(doctorId));
  if (status) queryParams.set('status', status);

  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiClient.get(`/hospitals/${hospitalId}/sessions${queryString}`, { skipAuth: true, signal });
}

/**
 * Retrieves public, anonymized live queue status for lobby displays.
 * Strictly excludes any patient identities, names, or phone numbers.
 *
 * @param {number|string} sessionId
 * @param {object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<object>} LiveQueuePublicStatusOut object
 */
export async function fetchPublicQueueStatusApi(sessionId, { signal } = {}) {
  return apiClient.get(`/sessions/${sessionId}/queue/status`, { skipAuth: true, signal });
}

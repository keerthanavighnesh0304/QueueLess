import { apiClient } from './client';

/**
 * Fetches the operational live queue summary for a consultation session.
 * Requires hospital staff credentials matching the hospital, or admin privileges.
 *
 * @param {number|string} hospitalId
 * @param {number|string} sessionId
 * @param {object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<object>} LiveQueueSummaryOut
 */
export async function fetchStaffLiveQueueApi(hospitalId, sessionId, { signal } = {}) {
  return apiClient.get(`/hospitals/${hospitalId}/sessions/${sessionId}/queue`, { signal });
}

/**
 * Advances the queue by calling the next patient in WAITING status.
 *
 * @param {number|string} hospitalId
 * @param {number|string} sessionId
 * @returns {Promise<object>} CallNextResponse
 */
export async function callNextPatientApi(hospitalId, sessionId) {
  return apiClient.post(`/hospitals/${hospitalId}/sessions/${sessionId}/queue/call-next`);
}

/**
 * Transitions a called ticket to IN_CONSULTATION.
 *
 * @param {number|string} hospitalId
 * @param {number|string} ticketId
 * @returns {Promise<object>} TicketActionResponse
 */
export async function servePatientApi(hospitalId, ticketId) {
  return apiClient.post(`/hospitals/${hospitalId}/tickets/${ticketId}/serve`);
}

/**
 * Completes a consultation (transitions IN_CONSULTATION -> COMPLETED).
 *
 * @param {number|string} hospitalId
 * @param {number|string} ticketId
 * @returns {Promise<object>} TicketActionResponse
 */
export async function completeConsultationApi(hospitalId, ticketId) {
  return apiClient.post(`/hospitals/${hospitalId}/tickets/${ticketId}/complete`);
}

/**
 * Marks a non-attending called patient as skipped (CALLING -> NO_SHOW).
 *
 * @param {number|string} hospitalId
 * @param {number|string} ticketId
 * @returns {Promise<object>} TicketActionResponse
 */
export async function markNoShowApi(hospitalId, ticketId) {
  return apiClient.post(`/hospitals/${hospitalId}/tickets/${ticketId}/no-show`);
}

/**
 * Issues an in-person walk-in ticket at the hospital registration desk.
 *
 * @param {number|string} hospitalId
 * @param {number|string} sessionId
 * @param {object} payload
 * @param {string} payload.patient_name
 * @param {string} [payload.patient_phone]
 * @returns {Promise<object>} TicketActionResponse
 */
export async function createWalkInTicketApi(hospitalId, sessionId, payload) {
  return apiClient.post(`/hospitals/${hospitalId}/sessions/${sessionId}/walk-in`, payload);
}

/**
 * Creates an authoritative OPD consultation session for a doctor.
 *
 * @param {number|string} hospitalId
 * @param {object} payload
 * @param {number} payload.doctor_id
 * @param {string} payload.session_name
 * @param {string} payload.session_date - YYYY-MM-DD
 * @param {string} [payload.start_time] - HH:MM:SS
 * @param {string} [payload.end_time] - HH:MM:SS
 * @param {number} [payload.max_capacity]
 * @returns {Promise<object>} ConsultationSessionOut
 */
export async function createConsultationSessionApi(hospitalId, payload) {
  return apiClient.post(`/hospitals/${hospitalId}/sessions`, payload);
}

/**
 * Updates the operational status of a consultation session.
 *
 * @param {number|string} hospitalId
 * @param {number|string} sessionId
 * @param {string} status - SCHEDULED, ACTIVE, PAUSED, COMPLETED
 * @returns {Promise<object>} ConsultationSessionActionResponse
 */
export async function updateSessionStatusApi(hospitalId, sessionId, status) {
  return apiClient.patch(`/hospitals/${hospitalId}/sessions/${sessionId}/status`, { status });
}

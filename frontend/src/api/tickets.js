import { apiClient } from './client';

/**
 * Creates an authorized queue ticket for an authenticated patient.
 *
 * @param {number|string} sessionId
 * @param {object} payload
 * @param {string} payload.patient_name
 * @param {string} [payload.patient_phone]
 * @returns {Promise<object>} PatientTicketActionResponse
 */
export async function createTicketApi(sessionId, payload) {
  return apiClient.post(`/sessions/${sessionId}/tickets`, payload);
}

/**
 * Fetches all tickets belonging to the currently authenticated patient.
 * Includes dynamic queue positions and estimated waiting times.
 *
 * @returns {Promise<Array<object>>} List of QueueTicketPatientOut objects
 */
export async function fetchMyTicketsApi({ signal } = {}) {
  return apiClient.get('/tickets/my', { signal });
}

/**
 * Fetches detailed info for a specific ticket.
 *
 * @param {number|string} ticketId
 * @returns {Promise<object>} QueueTicketPatientOut object
 */
export async function fetchTicketDetailsApi(ticketId, { signal } = {}) {
  return apiClient.get(`/tickets/${ticketId}`, { signal });
}

/**
 * Cancels an active ticket (in WAITING or CALLING status).
 *
 * @param {number|string} ticketId
 * @returns {Promise<object>} PatientTicketActionResponse
 */
export async function cancelTicketApi(ticketId) {
  return apiClient.post(`/tickets/${ticketId}/cancel`);
}

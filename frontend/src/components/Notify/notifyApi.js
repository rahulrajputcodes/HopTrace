/**
 * M3 Notification API helpers.
 *
 * Owns all network calls for the notification subsystem (M3).
 * Imports `api` from useApi (M2-owned) for authenticated fetch —
 * does NOT duplicate token handling, base URL config, or auth logic.
 *
 * Usage:
 *   import { fetchNotificationPreview, sendNotifications, ... } from './notifyApi';
 */

import { api } from '../../hooks/useApi.js';

/**
 * Fetch a preview of outage notifications for all affected subscribers.
 *
 * @param {string} incidentId
 * @param {{ channel?: string, kind?: string, translate?: boolean }} opts
 * @returns {Promise<object>}
 */
export async function fetchNotificationPreview(
  incidentId,
  { channel = 'sms', kind = 'outage', translate = false } = {}
) {
  return api(
    `/incidents/${incidentId}/notifications/preview?channel=${channel}&kind=${kind}&translate=${translate}`
  );
}

/**
 * Dispatch outage or restoration notifications.
 *
 * When targeting Twilio, the caller MUST supply `idempotencyKey`.
 * For console/sandbox sends the key is optional and may be auto-generated server-side.
 *
 * @param {string} incidentId
 * @param {object} payload  — { channel, kind, subscriber_ids, translate }
 * @param {string|undefined} idempotencyKey
 * @returns {Promise<object>}
 */
export async function sendNotifications(incidentId, payload, idempotencyKey) {
  const headers = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return api(`/incidents/${incidentId}/notify`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch notification dispatch history for an incident.
 *
 * @param {string} incidentId
 * @returns {Promise<object>}
 */
export async function fetchNotificationHistory(incidentId) {
  return api(`/incidents/${incidentId}/notifications`);
}

/**
 * Retry failed deliveries for an incident batch.
 *
 * @param {string} incidentId
 * @param {object} [payload]  — { batch_id?, delivery_ids? }
 * @returns {Promise<Array>}
 */
export async function retryNotifications(incidentId, payload = {}) {
  return api(`/incidents/${incidentId}/notifications/retry`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch notification provider and service status.
 *
 * Returns a safe default object on network failure so callers
 * never need to handle undefined.
 *
 * @returns {Promise<object>}
 */
export async function fetchNotificationStatus() {
  try {
    return await api('/notifications/status');
  } catch {
    return {
      available: false,
      provider: 'unavailable',
      reason:
        'Outage notification provider is not configured. Set NOTIFICATION_PROVIDER=console or twilio.',
    };
  }
}

/**
 * Synthesize an alert message to voice audio via Sarvam AI TTS.
 *
 * @param {string} text
 * @param {string} [language='hi']
 * @param {string} [speaker='meera']
 * @returns {Promise<{ audio_base64: string, mime: string, provider: string }>}
 */
export async function synthesizeVoice(text, language = 'hi', speaker = 'meera') {
  return api('/voice', {
    method: 'POST',
    body: JSON.stringify({ text, language, speaker }),
  });
}

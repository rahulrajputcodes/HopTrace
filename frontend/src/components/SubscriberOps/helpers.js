/**
 * Subscriber Operations Helper Functions
 *
 * Resolves access point identifiers and village locations for subscribers,
 * handling field mismatches (access_point_id vs ap_id) and dynamic/fallback
 * village mappings.
 */

export const DEFAULT_AP_TO_VILLAGE = {
  AP1: 'Rampur',
  AP2: 'Rampur',
  AP3: 'Bhatpur',
  AP4: 'Bhatpur',
  AP5: 'Daulatpur',
  AP6: 'Daulatpur',
};

/**
 * Resolves the display village name for a subscriber.
 * Priority:
 * 1. subscriber.village (if explicitly provided)
 * 2. Lookup in dynamically fetched villages list (matching access_points array)
 * 3. Default canonical AP-to-village mapping
 * 4. Fallback '—'
 *
 * @param {Object} subscriber
 * @param {Array} [villages]
 * @returns {string} Village name or '—'
 */
export function getSubscriberVillage(subscriber, villages = []) {
  if (subscriber?.village) return subscriber.village;
  const apId = subscriber?.access_point_id || subscriber?.ap_id;
  if (!apId) return '—';

  if (Array.isArray(villages) && villages.length > 0) {
    const found = villages.find(v =>
      Array.isArray(v.access_points) && v.access_points.includes(apId)
    );
    if (found?.name) return found.name;
    if (found?.village_id) {
      return found.village_id.charAt(0).toUpperCase() + found.village_id.slice(1);
    }
  }

  return DEFAULT_AP_TO_VILLAGE[apId] || '—';
}

/**
 * Resolves the display Access Point ID for a subscriber.
 * Handles field name differences between API (access_point_id) and legacy UI references (ap_id).
 *
 * @param {Object} subscriber
 * @returns {string} AP identifier or '—'
 */
export function getSubscriberAp(subscriber) {
  return subscriber?.access_point_id || subscriber?.ap_id || '—';
}

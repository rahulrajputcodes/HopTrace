export const STORAGE_KEY_MAP_LEGEND = 'ht_map_legend_open';
export const STORAGE_KEY_MAP_VILLAGES = 'ht_map_villages_open';

/**
 * Reads persisted popover preference (defaulting to false / collapsed).
 *
 * @param {string} key
 * @param {boolean} [defaultValue=false]
 * @param {Storage} [storage=window?.localStorage]
 * @returns {boolean}
 */
export function getStoredPopoverPref(
  key,
  defaultValue = false,
  storage = typeof window !== 'undefined' ? window.localStorage : null
) {
  if (!storage) return defaultValue;
  try {
    const item = storage.getItem(key);
    if (item === null) return defaultValue;
    return item === 'true';
  } catch {
    return defaultValue;
  }
}

/**
 * Persists popover preference safely.
 *
 * @param {string} key
 * @param {boolean} value
 * @param {Storage} [storage=window?.localStorage]
 */
export function setStoredPopoverPref(
  key,
  value,
  storage = typeof window !== 'undefined' ? window.localStorage : null
) {
  if (!storage) return;
  try {
    storage.setItem(key, String(Boolean(value)));
  } catch {
    // Gracefully ignore storage quota / sandbox write errors
  }
}

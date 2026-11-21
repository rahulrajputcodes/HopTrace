/**
 * Preference storage helper for NetworkView (Map vs Graph view).
 */

export const STORAGE_KEY = 'hoptrace.networkView';
export const VALID_VIEWS = ['map', 'graph'];
export const DEFAULT_VIEW = 'map';

/**
 * Gets the preferred view from storage, validating against allowed views.
 * Safely falls back to 'map' if storage is missing, throws, or holds an invalid view.
 *
 * @param {Storage} [customStorage]
 * @returns {'map' | 'graph'}
 */
export function getViewPref(customStorage) {
  try {
    const storage =
      customStorage ?? (typeof window !== 'undefined' ? window.localStorage : null);
    if (!storage) {
      return DEFAULT_VIEW;
    }
    const val = storage.getItem(STORAGE_KEY);
    if (val && VALID_VIEWS.includes(val)) {
      return val;
    }
    return DEFAULT_VIEW;
  } catch {
    return DEFAULT_VIEW;
  }
}

/**
 * Persists the preferred view to storage.
 *
 * @param {'map' | 'graph'} view
 * @param {Storage} [customStorage]
 */
export function setViewPref(view, customStorage) {
  if (!VALID_VIEWS.includes(view)) {
    return;
  }
  try {
    const storage =
      customStorage ?? (typeof window !== 'undefined' ? window.localStorage : null);
    if (!storage) {
      return;
    }
    storage.setItem(STORAGE_KEY, view);
  } catch {
    // Storage access may be denied; safe no-op
    return;
  }
}

export const STORAGE_KEY_MAP_LAYERS = 'hoptrace.mapLayers';
export const LABEL_MIN_ZOOM = 16;

export const DEFAULT_MAP_LAYERS = {
  coverage: true,
  links: true,
  labels: true,
};

/**
 * Reads persisted map layer visibility preferences.
 * Safe against storage errors and corrupted JSON.
 *
 * @param {Storage} [storage=window?.localStorage]
 * @returns {{ coverage: boolean, links: boolean, labels: boolean }}
 */
export function getStoredLayers(storage = typeof window !== 'undefined' ? window.localStorage : null) {
  if (!storage) return { ...DEFAULT_MAP_LAYERS };
  try {
    const raw = storage.getItem(STORAGE_KEY_MAP_LAYERS);
    if (!raw) return { ...DEFAULT_MAP_LAYERS };
    const parsed = JSON.parse(raw);
    return {
      coverage: typeof parsed.coverage === 'boolean' ? parsed.coverage : DEFAULT_MAP_LAYERS.coverage,
      links: typeof parsed.links === 'boolean' ? parsed.links : DEFAULT_MAP_LAYERS.links,
      labels: typeof parsed.labels === 'boolean' ? parsed.labels : DEFAULT_MAP_LAYERS.labels,
    };
  } catch {
    return { ...DEFAULT_MAP_LAYERS };
  }
}

/**
 * Persists map layer visibility preferences.
 *
 * @param {{ coverage: boolean, links: boolean, labels: boolean }} layers
 * @param {Storage} [storage=window?.localStorage]
 */
export function setStoredLayers(layers, storage = typeof window !== 'undefined' ? window.localStorage : null) {
  if (!storage || !layers) return;
  try {
    storage.setItem(STORAGE_KEY_MAP_LAYERS, JSON.stringify(layers));
  } catch {
    // Gracefully ignore storage quota / sandbox write errors
  }
}

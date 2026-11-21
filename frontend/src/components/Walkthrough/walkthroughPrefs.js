/**
 * M4 — Walkthrough localStorage prefs (pure, non-React).
 * Split from Walkthrough.jsx to satisfy react-refresh/only-export-components.
 */

const STORAGE_KEY = 'hoptrace_walkthrough_seen';

/** Returns true if the walkthrough has already been seen */
export function hasSeenWalkthrough() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

/** Marks the walkthrough as seen so it won't auto-open again */
export function markWalkthroughSeen() {
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch { /* storage unavailable — not fatal */ }
}

/**
 * M4 — SLAView pure helpers.
 *
 * All functions are pure (no React, no side effects) so they can be
 * tested with node:test without JSDOM.
 *
 * formatUptime      — float → "99.7%" or "–"
 * formatDowntime    — minutes → "2h 15m" or "0m" or "–"
 * slaStatusConfig   — status string → Tailwind colour tokens
 * windowLabel       — hours integer → human-readable window label
 */

// ---------------------------------------------------------------------------
// formatUptime
// ---------------------------------------------------------------------------

/**
 * Formats an uptime percentage for display.
 * Returns "–" for null/undefined/NaN (never invents a value).
 *
 * @param {number|null|undefined} pct  0–100
 * @returns {string}
 */
export function formatUptime(pct) {
  if (pct === null || pct === undefined) return '–';
  const n = Number(pct);
  if (!Number.isFinite(n)) return '–';
  return `${n.toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// formatDowntime
// ---------------------------------------------------------------------------

/**
 * Converts downtime in minutes to a readable duration string.
 * Returns "–" for null/undefined/NaN.
 * Returns "0m" for zero.
 *
 * @param {number|null|undefined} minutes
 * @returns {string}
 */
export function formatDowntime(minutes) {
  if (minutes === null || minutes === undefined) return '–';
  const m = Number(minutes);
  if (!Number.isFinite(m)) return '–';
  if (m <= 0) return '0m';
  const h = Math.floor(m / 60);
  const rem = Math.round(m % 60);
  if (h === 0) return `${rem}m`;
  if (rem === 0) return `${h}h`;
  return `${h}h ${rem}m`;
}

// ---------------------------------------------------------------------------
// slaStatusConfig
// ---------------------------------------------------------------------------

const STATUS_MAP = {
  healthy: {
    label: 'Healthy',
    colorClass: 'text-emerald-400',
    bgClass: 'bg-emerald-950/60',
    borderClass: 'border-emerald-700/50',
    dotClass: 'bg-emerald-400',
    badgeClass: 'bg-emerald-900/80 text-emerald-300 border-emerald-700/60',
  },
  degraded: {
    label: 'Degraded',
    colorClass: 'text-amber-400',
    bgClass: 'bg-amber-950/60',
    borderClass: 'border-amber-700/50',
    dotClass: 'bg-amber-400',
    badgeClass: 'bg-amber-900/80 text-amber-300 border-amber-700/60',
  },
  critical: {
    label: 'Critical',
    colorClass: 'text-red-400',
    bgClass: 'bg-red-950/60',
    borderClass: 'border-red-700/50',
    dotClass: 'bg-red-400',
    badgeClass: 'bg-red-900/80 text-red-300 border-red-700/60',
  },
};

const FALLBACK_STATUS = {
  label: 'Unknown',
  colorClass: 'text-slate-400',
  bgClass: 'bg-slate-800/60',
  borderClass: 'border-slate-700/50',
  dotClass: 'bg-slate-500',
  badgeClass: 'bg-slate-800/80 text-slate-400 border-slate-700/60',
};

/**
 * Returns Tailwind styling tokens for a given SLA status string.
 * Never throws — returns FALLBACK_STATUS for unexpected values.
 *
 * @param {string} status  'healthy' | 'degraded' | 'critical' | <anything>
 * @returns {{ label, colorClass, bgClass, borderClass, dotClass, badgeClass }}
 */
export function slaStatusConfig(status) {
  return STATUS_MAP[status] ?? FALLBACK_STATUS;
}

// ---------------------------------------------------------------------------
// windowLabel
// ---------------------------------------------------------------------------

const WINDOW_LABELS = {
  24: 'Last 24 hours',
  168: 'Last 7 days',
  720: 'Last 30 days',
};

/**
 * Returns a human-readable label for the SLA window.
 *
 * @param {number} hours
 * @returns {string}
 */
export function windowLabel(hours) {
  return WINDOW_LABELS[hours] ?? `Last ${hours}h`;
}

// ---------------------------------------------------------------------------
// formatTimestamp
// ---------------------------------------------------------------------------

/**
 * Formats an ISO UTC timestamp to a readable local time string.
 * Returns "–" for null/undefined/invalid.
 *
 * @param {string|null|undefined} iso
 * @returns {string}
 */
export function formatTimestamp(iso) {
  if (!iso) return '–';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '–';
  }
}

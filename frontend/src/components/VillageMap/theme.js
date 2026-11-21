/**
 * Design constants and theme tokens mirrored from TopologyCanvas (commit f46157e)
 * to ensure visual consistency across both views.
 */

export const NODE_TYPES_META = {
  gateway: { color: '#8b5cf6', bg: '#2e1065', icon: '🌐', label: 'Gateway' },
  router: { color: '#3b82f6', bg: '#1e3a8a', icon: '🔄', label: 'Router' },
  wireless_bridge: { color: '#f59e0b', bg: '#451a03', icon: '📡', label: 'Bridge' },
  access_point: { color: '#10b981', bg: '#022c22', icon: '📶', label: 'AP' },
};

export const VILLAGE_COLORS = {
  Rampur: '#3b82f6',
  Bhatpur: '#10b981',
  Daulatpur: '#f59e0b',
};

export const VILLAGE_STATUS_COLORS = {
  healthy: '#10b981',
  degraded: '#f59e0b',
  critical: '#ef4444',
  unknown: '#64748b',
};

/**
 * Returns color code for village aggregate network health status.
 * @param {string | null | undefined} status
 * @returns {string}
 */
export function villageStatusColor(status) {
  if (status && typeof status === 'string') {
    const s = status.toLowerCase();
    if (VILLAGE_STATUS_COLORS[s]) return VILLAGE_STATUS_COLORS[s];
  }
  return VILLAGE_STATUS_COLORS.unknown;
}

/**
 * Returns color code corresponding to risk score, identical to TopologyCanvas.
 * @param {number} score
 * @returns {string}
 */
export function riskColor(score) {
  if (score >= 80) return '#ef4444';
  if (score >= 60) return '#f97316';
  if (score >= 40) return '#f59e0b';
  return '#10b981';
}

/**
 * Returns human-readable telemetry label corresponding to backend DataSource string.
 * Returns "Simulated telemetry" for 'simulated',
 * "Measured telemetry" for 'measured',
 * and null for anything else (e.g. 'loading' or null).
 *
 * @param {string | null | undefined} dataSource
 * @returns {string | null}
 */
export function telemetryLabel(dataSource) {
  if (dataSource === 'simulated') return 'Simulated telemetry';
  if (dataSource === 'measured') return 'Measured telemetry';
  return null;
}


/**
 * Telemetry freshness and health calculation helpers.
 * Adheres to HopTrace Part 1 Contract §2.1 and TRACK_B_api_frontend.md §B3.
 */

/**
 * Returns display styling properties for a given telemetry freshness state.
 *
 * @param {string | null | undefined} freshness - "live" | "stale" | "no_data" | "simulated"
 * @returns {{ label: string, color: string, dashed: boolean }}
 */
export function freshnessStyle(freshness) {
  const f = typeof freshness === 'string' ? freshness.toLowerCase().trim() : '';
  switch (f) {
    case 'live':
      return { label: 'Live', color: '#10b981', dashed: false };
    case 'stale':
      return { label: 'Stale', color: '#f59e0b', dashed: true };
    case 'no_data':
      return { label: 'No data', color: '#64748b', dashed: true };
    case 'simulated':
      return { label: 'Simulated', color: '#94a3b8', dashed: false };
    default:
      return { label: 'Unknown', color: '#64748b', dashed: true };
  }
}

/**
 * Determines whether a link should be counted as healthy for KPI calculations.
 * Rule: links with freshness === 'no_data' or broken connectivity are never healthy.
 *
 * @param {Object} link
 * @returns {boolean}
 */
export function isHealthyForKpi(link) {
  if (!link || typeof link !== 'object') return false;

  const freshness = link.freshness || link.live?.freshness;
  if (freshness === 'no_data') {
    return false;
  }

  // Connectivity down
  if (link.isDown || link.connectivity_ok === false || link.live?.connectivity_ok === false) {
    return false;
  }

  // Explicit failure/down status
  if (link.status === 'down' || link.status === 'failed') {
    return false;
  }

  // High risk
  const risk = typeof link.risk_score === 'number' ? link.risk_score : 0;
  if (risk >= 60) {
    return false;
  }

  // If metrics are explicitly null and data_source is live (unmonitored), not healthy
  if (
    (link.live?.data_source === 'live' || link.data_source === 'live') &&
    link.live?.latency_ms === null &&
    link.live?.packet_loss_pct === null
  ) {
    return false;
  }

  return true;
}

/**
 * Formats a last_seen_utc ISO timestamp into human readable text.
 * E.g. "last seen 42s ago" or "never seen".
 *
 * @param {string | null | undefined} lastSeenUtc
 * @param {number | Date} [now=Date.now()]
 * @returns {string}
 */
export function formatLastSeen(lastSeenUtc, now = Date.now()) {
  if (!lastSeenUtc || typeof lastSeenUtc !== 'string') {
    return 'never seen';
  }

  const seenTime = new Date(lastSeenUtc).getTime();
  if (Number.isNaN(seenTime)) {
    return 'never seen';
  }

  const nowMs = typeof now === 'number' ? now : (now instanceof Date ? now.getTime() : Date.now());
  const diffSec = Math.max(0, Math.floor((nowMs - seenTime) / 1000));

  if (diffSec < 60) {
    return `last seen ${diffSec}s ago`;
  }
  if (diffSec < 3600) {
    return `last seen ${Math.floor(diffSec / 60)}m ago`;
  }
  return `last seen ${Math.floor(diffSec / 3600)}h ago`;
}

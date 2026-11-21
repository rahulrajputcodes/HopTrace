/**
 * Pure risk scoring and stroke styling functions for network links.
 * Derived from TopologyCanvas (commit f46157e, lines 45-50 and 126-131).
 */

/**
 * Returns color code corresponding to numeric risk score.
 * Matches TopologyCanvas riskColor exact thresholds.
 *
 * @param {number} score
 * @returns {string}
 */
export function riskColor(score) {
  const s = typeof score === 'number' && !Number.isNaN(score) ? score : 0;
  if (s >= 80) return '#ef4444';
  if (s >= 60) return '#f97316';
  if (s >= 40) return '#f59e0b';
  return '#10b981';
}

/**
 * Derives numeric risk score for a link following TopologyCanvas precedence:
 * 1. riskSnapshot[link_id]?.risk_score
 * 2. liveMeasurements[link_id]?.risk_score (Map or Object)
 * 3. Fallback: 0
 *
 * @param {string} linkId
 * @param {Record<string, {risk_score?: number}> | null | undefined} riskSnapshot
 * @param {Map<string, {risk_score?: number}> | Record<string, {risk_score?: number}> | null | undefined} liveMap
 * @returns {number}
 */
export function getLinkRisk(linkId, riskSnapshot, liveMap) {
  if (!linkId) return 0;

  const snapScore = riskSnapshot?.[linkId]?.risk_score;
  if (typeof snapScore === 'number' && Number.isFinite(snapScore)) {
    return snapScore;
  }

  let liveScore = null;
  if (liveMap instanceof Map) {
    liveScore = liveMap.get(linkId)?.risk_score;
  } else if (liveMap && typeof liveMap === 'object') {
    liveScore = liveMap[linkId]?.risk_score;
  }

  if (typeof liveScore === 'number' && Number.isFinite(liveScore)) {
    return liveScore;
  }

  return 0;
}

/**
 * Calculates polyline stroke width based on risk score and suspected state.
 * Matches TopologyCanvas line 130: `isSuspected ? 4 : Math.max(1.5, 1.5 + risk / 40)`.
 *
 * @param {number} riskScore
 * @param {boolean} [isSuspected=false]
 * @returns {number}
 */
export function getLinkStrokeWidth(riskScore, isSuspected = false) {
  if (isSuspected) return 4;
  const score = typeof riskScore === 'number' && Number.isFinite(riskScore) ? riskScore : 0;
  return Math.max(1.5, 1.5 + score / 40);
}

/**
 * Determines stroke dash array based on connectivity state.
 * Returns '6 4' when connectivity_ok is strictly false. Missing or true remains solid (undefined).
 *
 * @param {boolean | undefined | null} connectivityOk
 * @returns {string | undefined}
 */
export function getLinkDashArray(connectivityOk) {
  return connectivityOk === false ? '6 4' : undefined;
}

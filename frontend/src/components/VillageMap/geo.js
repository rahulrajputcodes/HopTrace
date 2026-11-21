/**
 * Pure geographic and wireless physics utility functions for HopTrace VillageMap.
 */

/**
 * Computes bounding box [[minLat, minLon], [maxLat, maxLon]] for an array of nodes.
 * Only nodes with finite numeric `lat` and `lon` are considered.
 * Returns null if no valid coordinates exist.
 *
 * @param {Array<{lat?: number, lon?: number}>} nodes
 * @returns {[[number, number], [number, number]] | null}
 */
export function computeBounds(nodes) {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return null;
  }

  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  let count = 0;

  for (const node of nodes) {
    if (!node || typeof node !== 'object') continue;
    const { lat, lon } = node;
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
      count++;
    }
  }

  if (count === 0) {
    return null;
  }

  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ];
}

/**
 * Parses a frequency string like "5GHz" or "60 GHz" (case-insensitive) into numeric GHz.
 * Returns null for missing, non-string, unparsable, or non-positive values.
 *
 * @param {string | null | undefined} str
 * @returns {number | null}
 */
export function parseGHz(str) {
  if (typeof str !== 'string') return null;
  const match = str.trim().match(/^(\d+(?:\.\d+)?)\s*ghz$/i);
  if (!match) return null;
  const val = parseFloat(match[1]);
  if (!Number.isFinite(val) || val <= 0) return null;
  return val;
}

/**
 * Calculates the first Fresnel zone radius (F1) in metres at mid-path.
 * Formula: F1 = 17.32 * Math.sqrt(dKm / (4 * fGHz))
 * Returns null if any argument is non-numeric, non-positive, or NaN.
 *
 * @param {number} dKm - Path distance in kilometres
 * @param {number} fGHz - Carrier frequency in GHz
 * @returns {number | null}
 */
export function fresnelF1Metres(dKm, fGHz) {
  if (
    typeof dKm !== 'number' ||
    typeof fGHz !== 'number' ||
    !Number.isFinite(dKm) ||
    !Number.isFinite(fGHz) ||
    dKm <= 0 ||
    fGHz <= 0
  ) {
    return null;
  }
  return 17.32 * Math.sqrt(dKm / (4 * fGHz));
}

/**
 * Computes the 60% clearance requirement in metres: 0.6 * F1.
 * Returns null for invalid or non-positive F1.
 *
 * @param {number} f1 - F1 radius in metres
 * @returns {number | null}
 */
export function clearance60(f1) {
  if (typeof f1 !== 'number' || !Number.isFinite(f1) || f1 <= 0) {
    return null;
  }
  return 0.6 * f1;
}

/**
 * Calculates geographic midpoint [lat, lon] between two network nodes.
 * Returns null if either node lacks finite coordinates.
 *
 * @param {{lat?: number, lon?: number} | null | undefined} sourceNode
 * @param {{lat?: number, lon?: number} | null | undefined} targetNode
 * @returns {[number, number] | null}
 */
export function getLinkMidpoint(sourceNode, targetNode) {
  if (
    !sourceNode ||
    !targetNode ||
    !Number.isFinite(sourceNode.lat) ||
    !Number.isFinite(sourceNode.lon) ||
    !Number.isFinite(targetNode.lat) ||
    !Number.isFinite(targetNode.lon)
  ) {
    return null;
  }
  return [
    (sourceNode.lat + targetNode.lat) / 2,
    (sourceNode.lon + targetNode.lon) / 2,
  ];
}

/**
 * Extracts and validates predicted failure ETA in minutes from a live measurement entry.
 * Returns rounded integer minutes if finite and >= 0, otherwise null.
 *
 * @param {Object | null | undefined} liveMeasurement
 * @returns {number | null}
 */
export function getPredictedEtaMinutes(liveMeasurement) {
  if (!liveMeasurement || typeof liveMeasurement !== 'object') {
    return null;
  }
  const eta = liveMeasurement.predicted_eta_minutes;
  if (typeof eta === 'number' && Number.isFinite(eta) && eta >= 0) {
    return Math.round(eta);
  }
  return null;
}

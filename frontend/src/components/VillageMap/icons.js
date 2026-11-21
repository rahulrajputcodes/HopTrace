import { NODE_TYPES_META } from './theme.js';

export const NODE_Z_INDEX = {
  gateway: 400,
  router: 300,
  wireless_bridge: 200,
  access_point: 100,
  suspected: 1000,
};

/**
 * Generates configuration for a Leaflet DivIcon representing a network node.
 * Uses distinct shapes, sizes, colors and semantic labels for each node type:
 * - Gateway: 30px squircle (rounded square)
 * - Router: 26px circle
 * - Bridge: 26px diamond
 * - AP: 22px circle
 *
 * @param {Object} node
 * @returns {{
 *   html: string,
 *   className: string,
 *   iconSize: [number, number],
 *   iconAnchor: [number, number],
 *   zIndexOffset: number
 * }}
 */
export function getNodeIconConfig(node) {
  const type = node?.type || 'access_point';
  const meta = NODE_TYPES_META[type] || NODE_TYPES_META.access_point;
  const isBlast = Boolean(node?.isBlastAp);
  const isSuspected = Boolean(node?.isSuspected);

  let size;
  let anchor;
  let innerShapeHtml;

  const blastBadgeHtml = isBlast
    ? '<span class="hoptrace-blast-badge" aria-label="Blast radius impact">!</span>'
    : '';

  if (type === 'gateway') {
    size = [30, 30];
    anchor = [15, 15];
    innerShapeHtml = `
      <div style="width: 30px; height: 30px; border-radius: 6px; border: 2px solid ${meta.color}; background-color: ${meta.bg}; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.5); font-size: 14px; position: relative;">
        <span>${meta.icon}</span>
        ${blastBadgeHtml}
      </div>
    `;
  } else if (type === 'router') {
    size = [26, 26];
    anchor = [13, 13];
    innerShapeHtml = `
      <div style="width: 26px; height: 26px; border-radius: 9999px; border: 2px solid ${meta.color}; background-color: ${meta.bg}; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.5); font-size: 12px; position: relative;">
        <span>${meta.icon}</span>
        ${blastBadgeHtml}
      </div>
    `;
  } else if (type === 'wireless_bridge') {
    size = [28, 28];
    anchor = [14, 14];
    innerShapeHtml = `
      <div style="width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; position: relative;">
        <div style="width: 20px; height: 20px; border-radius: 4px; border: 2px solid ${meta.color}; background-color: ${meta.bg}; transform: rotate(45deg); box-shadow: 0 2px 6px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;">
          <span style="transform: rotate(-45deg); font-size: 10px; display: block;">${meta.icon}</span>
        </div>
        ${blastBadgeHtml}
      </div>
    `;
  } else {
    // access_point
    size = [22, 22];
    anchor = [11, 11];
    innerShapeHtml = `
      <div style="width: 22px; height: 22px; border-radius: 9999px; border: 2px solid ${meta.color}; background-color: ${meta.bg}; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.5); font-size: 10px; position: relative;">
        <span>${meta.icon}</span>
        ${blastBadgeHtml}
      </div>
    `;
  }

  const ariaLabel = `${node?.id || 'node'}: ${meta.label} at ${node?.village || 'unknown'}`;
  const html = `
    <div role="button" tabindex="0" aria-label="${ariaLabel}" title="${ariaLabel}" style="cursor: pointer; outline: none;">
      ${innerShapeHtml}
    </div>
  `;

  const zIndexOffset = isSuspected
    ? NODE_Z_INDEX.suspected
    : (NODE_Z_INDEX[type] || 100);

  return {
    html,
    className: 'hoptrace-node-div-icon',
    iconSize: size,
    iconAnchor: anchor,
    zIndexOffset,
  };
}

/**
 * Generates configuration for the pulsing incident ring overlay.
 *
 * @returns {{
 *   html: string,
 *   className: string,
 *   iconSize: [number, number],
 *   iconAnchor: [number, number]
 * }}
 */
export function getSuspectedRingConfig() {
  return {
    html: '<div class="hoptrace-suspected-ring" style="width: 44px; height: 44px;"></div>',
    className: 'hoptrace-suspected-ring-icon',
    iconSize: [44, 44],
    iconAnchor: [22, 22],
  };
}

/**
 * Creates a Leaflet DivIcon for a node marker.
 *
 * @param {Object} node
 * @param {Object} [leaflet]
 * @returns {Object}
 */
export function createNodeIcon(node, leaflet) {
  const config = getNodeIconConfig(node);
  if (leaflet && typeof leaflet.divIcon === 'function') {
    return leaflet.divIcon(config);
  }
  return config;
}

/**
 * Creates a Leaflet DivIcon for suspected ring marker.
 *
 * @param {Object} [leaflet]
 * @returns {Object}
 */
export function createSuspectedRingIcon(leaflet) {
  const config = getSuspectedRingConfig();
  if (leaflet && typeof leaflet.divIcon === 'function') {
    return leaflet.divIcon(config);
  }
  return config;
}

/**
 * Generates configuration for an amber prediction badge DivIcon.
 *
 * @param {number} etaMinutes
 * @returns {{
 *   html: string,
 *   className: string,
 *   iconSize: [number, number],
 *   iconAnchor: [number, number]
 * }}
 */
export function getPredictionBadgeConfig(etaMinutes) {
  const rounded = Math.round(etaMinutes);
  const ariaLabel = `Predicted ETA about ${rounded} minutes (simulated)`;
  const html = `
    <div
      aria-label="${ariaLabel}"
      title="${ariaLabel}"
      style="background: #f59e0b; color: #0b172a; font-size: 10px; font-weight: 700; font-family: ui-monospace, SFMono-Regular, monospace; padding: 1px 5px; border-radius: 4px; border: 1px solid #d97706; box-shadow: 0 2px 4px rgba(0,0,0,0.5); white-space: nowrap; pointer-events: none; text-align: center; display: inline-block; transform: translate(-50%, -50%);"
    >
      ~${rounded} min
    </div>
  `;
  return {
    html,
    className: 'hoptrace-prediction-badge-icon',
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  };
}

/**
 * Creates a Leaflet DivIcon for the prediction badge marker.
 *
 * @param {number} etaMinutes
 * @param {Object} [leaflet]
 * @returns {Object}
 */
export function createPredictionBadgeIcon(etaMinutes, leaflet) {
  const config = getPredictionBadgeConfig(etaMinutes);
  if (leaflet && typeof leaflet.divIcon === 'function') {
    return leaflet.divIcon(config);
  }
  return config;
}

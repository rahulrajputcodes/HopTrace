import { getLinkRisk } from './risk.js';

/**
 * Pure data model transformation for VillageMap.
 * Derives valid geographic nodes, valid interconnected links, active suspected components,
 * and downstream blast radius access points without any React, Leaflet, or store dependency.
 *
 * @param {Object} params
 * @param {Object} [params.topology]
 * @param {Array<Object>} [params.villages]
 * @param {Record<string, {risk_score?: number, freshness?: string, last_seen_utc?: string}>} [params.riskSnapshot]
 * @param {Array<Object>} [params.liveMeasurements]
 * @param {Object} [params.activeIncident]
 * @param {Array<Object>} [params.affectedSubscribers]
 * @returns {{
 *   nodes: Array<Object>,
 *   links: Array<Object>,
 *   villages: Array<Object>,
 *   blastApIds: Set<string>,
 *   suspected: { id: string, type: 'node' | 'link' | null } | null
 * }}
 */
export function buildMapModel({
  topology = null,
  villages = [],
  riskSnapshot = {},
  liveMeasurements = [],
  activeIncident = null,
  affectedSubscribers = [],
} = {}) {
  // 1. Index live measurements by link_id
  const liveMap = new Map();
  if (Array.isArray(liveMeasurements)) {
    for (const m of liveMeasurements) {
      if (m && m.link_id) {
        liveMap.set(m.link_id, m);
      }
    }
  }

  // 2. Index villages by village_id
  const villageStatusMap = new Map();
  if (Array.isArray(villages)) {
    for (const v of villages) {
      if (v && v.village_id) {
        villageStatusMap.set(v.village_id, v.status || 'unknown');
      }
    }
  }

  // 3. Filter valid nodes with finite numeric coordinates
  const validNodeMap = new Map();
  const rawNodes = Array.isArray(topology?.nodes) ? topology.nodes : [];
  for (const node of rawNodes) {
    if (
      node &&
      node.id &&
      Number.isFinite(node.lat) &&
      Number.isFinite(node.lon)
    ) {
      validNodeMap.set(node.id, node);
    }
  }

  // 4. Resolve suspected component
  const suspectedId = activeIncident?.suspected_component_id || null;
  let suspectedType = activeIncident?.suspected_component_type || null;

  if (suspectedId && !suspectedType) {
    if (validNodeMap.has(suspectedId)) {
      suspectedType = 'node';
    } else {
      const rawLinks = Array.isArray(topology?.links) ? topology.links : [];
      if (rawLinks.some((l) => l?.id === suspectedId)) {
        suspectedType = 'link';
      }
    }
  }

  const suspected = suspectedId
    ? { id: suspectedId, type: suspectedType }
    : null;

  // 5. Derive blast radius AP IDs from affected subscribers
  const blastApIds = new Set();
  if (Array.isArray(affectedSubscribers)) {
    for (const sub of affectedSubscribers) {
      const apId = sub?.access_point_id;
      if (apId && validNodeMap.has(apId)) {
        const targetNode = validNodeMap.get(apId);
        if (targetNode.type === 'access_point') {
          blastApIds.add(apId);
        }
      }
    }
  }

  // 6. Filter and enrich links whose endpoints are both valid
  const rawLinks = Array.isArray(topology?.links) ? topology.links : [];
  const links = [];
  for (const link of rawLinks) {
    if (
      link &&
      link.id &&
      validNodeMap.has(link.source) &&
      validNodeMap.has(link.target)
    ) {
      const sourceNode = validNodeMap.get(link.source);
      const targetNode = validNodeMap.get(link.target);
      const riskScore = getLinkRisk(link.id, riskSnapshot, liveMap);
      const live = liveMap.get(link.id) || null;
      const isSuspected =
        suspected?.type === 'link' && suspected.id === link.id;
      const isDown = live?.connectivity_ok === false;
      const freshness = live?.freshness || riskSnapshot?.[link.id]?.freshness || (link.data_source === 'live' ? 'live' : 'simulated');
      const lastSeenUtc = live?.last_seen_utc ?? riskSnapshot?.[link.id]?.last_seen_utc ?? null;
      const isNoData = freshness === 'no_data';

      links.push({
        ...link,
        sourceNode,
        targetNode,
        risk_score: riskScore,
        isSuspected,
        isDown,
        freshness,
        last_seen_utc: lastSeenUtc,
        isNoData,
        live: live
          ? {
              latency_ms: live.latency_ms,
              packet_loss_pct: live.packet_loss_pct,
              throughput_mbps: live.throughput_mbps,
              connectivity_ok: live.connectivity_ok,
              predicted_eta_minutes: live.predicted_eta_minutes,
              data_source: live.data_source || 'simulated',
              freshness,
              last_seen_utc: lastSeenUtc,
            }
          : null,
      });
    }
  }

  // 7. If all links in a village are no_data, village status becomes "unknown"
  const effectiveVillages = (Array.isArray(villages) ? villages : []).map((v) => {
    if (!v || !v.village_id) return v;
    const vLinks = links.filter(
      (l) => l.sourceNode?.village === v.village_id || l.targetNode?.village === v.village_id
    );
    if (vLinks.length > 0 && vLinks.every((l) => l.isNoData)) {
      return { ...v, status: 'unknown' };
    }
    return v;
  });

  for (const v of effectiveVillages) {
    if (v && v.village_id) {
      villageStatusMap.set(v.village_id, v.status || 'unknown');
    }
  }

  // 8. Enrich nodes with presentation metadata
  const nodes = [];
  for (const node of validNodeMap.values()) {
    const isSuspected = suspected?.type === 'node' && suspected.id === node.id;
    const isBlastAp = blastApIds.has(node.id);
    const vStatus = node.village
      ? villageStatusMap.get(node.village) || 'unknown'
      : 'unknown';

    nodes.push({
      ...node,
      label: node.label || node.id,
      villageStatus: vStatus,
      isSuspected,
      isBlastAp,
    });
  }

  return {
    nodes,
    links,
    villages: effectiveVillages,
    blastApIds,
    suspected,
  };
}

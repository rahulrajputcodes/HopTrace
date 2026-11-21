/**
 * Pure hop trace failure path analysis helper.
 * Adheres to HopTrace Part 1 Contract §2.2 / §13 and TRACK_B_api_frontend.md §B5.
 */

/**
 * Builds the path from vantage node to the first failure boundary,
 * and identifies nodes behind the failure that are not blamed.
 *
 * @param {Array<Object>|null|undefined} hopTrace
 * @param {Array<Object>|null|undefined} topologyLinks
 * @returns {{ path: Array<Object>, behind: Array<string> }}
 */
export function buildFailurePath(hopTrace, topologyLinks = []) {
  if (!Array.isArray(hopTrace) || hopTrace.length === 0) {
    return { path: [], behind: [] };
  }

  // Index hops by node_id
  const hopMap = new Map();
  for (const h of hopTrace) {
    if (h && h.node_id) {
      hopMap.set(h.node_id, h);
    }
  }

  // Index topology links by target node and link id
  const linkByTarget = new Map();
  const linkById = new Map();
  if (Array.isArray(topologyLinks)) {
    for (const l of topologyLinks) {
      if (!l) continue;
      if (l.target) linkByTarget.set(l.target, l);
      if (l.id) linkById.set(l.id, l);
    }
  }

  // 1. Identify target hop to trace to
  // Priority: first 'failed' hop -> worst 'degraded' hop
  const failedHops = hopTrace.filter((h) => h?.status === 'failed');
  let targetHop = null;

  if (failedHops.length > 0) {
    // Pick first failed hop (lowest depth)
    targetHop = [...failedHops].sort((a, b) => (a.depth || 0) - (b.depth || 0))[0];
  } else {
    const degradedHops = hopTrace.filter((h) => h?.status === 'degraded');
    if (degradedHops.length > 0) {
      // Pick worst degraded hop by packet loss, then latency
      targetHop = [...degradedHops].sort((a, b) => {
        const lossDiff = (b.packet_loss_pct || 0) - (a.packet_loss_pct || 0);
        if (lossDiff !== 0) return lossDiff;
        return (b.latency_ms || 0) - (a.latency_ms || 0);
      })[0];
    }
  }

  // If no failure and no degradation, nothing to isolate
  if (!targetHop) {
    return { path: [], behind: [] };
  }

  // 2. Trace path back from targetHop to vantage node (depth 0)
  const path = [];
  const visited = new Set();
  let curr = targetHop;

  while (curr && !visited.has(curr.node_id)) {
    visited.add(curr.node_id);
    path.unshift(curr);

    if (curr.depth === 0) {
      break;
    }

    // Find parent via link_id or linkByTarget
    let parentNodeId = null;
    if (curr.link_id && linkById.has(curr.link_id)) {
      parentNodeId = linkById.get(curr.link_id).source;
    } else if (linkByTarget.has(curr.node_id)) {
      parentNodeId = linkByTarget.get(curr.node_id).source;
    }

    if (parentNodeId && hopMap.has(parentNodeId)) {
      curr = hopMap.get(parentNodeId);
    } else {
      // Fallback: look for predecessor hop with depth === curr.depth - 1
      const targetDepth = (curr.depth || 1) - 1;
      curr = hopTrace.find((h) => h && h.depth === targetDepth && !visited.has(h.node_id)) || null;
    }
  }

  // 3. Identify nodes behind failure
  // Nodes with status 'behind_failure' or downstream of the first failed hop
  const behindHops = hopTrace.filter((h) => h?.status === 'behind_failure');
  let behind = behindHops.map((h) => h.node_id);

  // If behind_failure status wasn't explicitly tagged, collect any hops with depth > failed hop depth
  if (behind.length === 0 && targetHop.status === 'failed') {
    const pathNodeIds = new Set(path.map((p) => p.node_id));
    behind = hopTrace
      .filter((h) => h && !pathNodeIds.has(h.node_id) && (h.depth || 0) > (targetHop.depth || 0))
      .map((h) => h.node_id);
  }

  return { path, behind };
}

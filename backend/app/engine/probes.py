"""Hop-by-hop path probe derivation engine.

Converts node-level probe results into link-level measurements and hop trace results
using strict tree semantics (blaming only the first failed hop).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from app.engine.diagnostics import DiagnosticEngine
from app.engine.models import HopResult, Measurement, NetworkTopology
from app.schemas.probes import NodeProbeResult


def derive_link_measurements(
    results: List[Union[NodeProbeResult, Dict[str, Any]]],
    topology: NetworkTopology,
    vantage_node_id: str = "GW1",
) -> Tuple[List[Measurement], List[HopResult]]:
    """Derives per-link measurements and per-hop status from node probe results.

    Tree semantics:
      1. X has no result -> HopResult.status = "no_data", no link measurement.
      2. P unreachable or P is "failed"/"behind_failure" -> HopResult.status = "behind_failure",
         no link measurement (never blame descendants).
      3. X unreachable, P reachable -> HopResult.status = "failed",
         inbound link: connectivity_ok=False, loss=100.0, latency=None.
      4. X and P reachable -> HopResult.status = "ok" (or "degraded" if score >= threshold),
         latency = max(0, lat_X - lat_P),
         loss = 1 - (1 - loss_X) / (1 - loss_P).
    """
    # 1. Map probe results by node ID
    result_by_node: Dict[str, Any] = {}
    for r in results:
        nid = r.get("node_id") if isinstance(r, dict) else getattr(r, "node_id", None)
        if nid:
            result_by_node[nid] = r

    # 2. Build graph adjacency and inbound link mappings
    inbound_link_by_target: Dict[str, Any] = {}
    children_by_parent: Dict[str, List[Tuple[str, str]]] = {}

    for link in topology.links:
        inbound_link_by_target[link.target] = link
        children_by_parent.setdefault(link.source, []).append((link.target, link.id))

    all_nodes = {n.id: n for n in topology.nodes}
    diag_engine = DiagnosticEngine()
    baselines = diag_engine.baselines
    detection_threshold = diag_engine.detection_threshold

    hop_results: Dict[str, HopResult] = {}
    derived_measurements: List[Measurement] = []

    # 3. Handle vantage node
    v_res = result_by_node.get(vantage_node_id)
    if v_res is not None:
        v_reachable = bool(v_res.get("reachable") if isinstance(v_res, dict) else v_res.reachable)
        v_lat = v_res.get("latency_ms") if isinstance(v_res, dict) else v_res.latency_ms
        v_loss = v_res.get("packet_loss_pct") if isinstance(v_res, dict) else v_res.packet_loss_pct
        v_status = "ok" if v_reachable else "failed"
    else:
        # Default vantage node assumption when probing starts directly at vantage node
        v_reachable = True
        v_lat = 0.0
        v_loss = 0.0
        v_status = "ok"

    hop_results[vantage_node_id] = HopResult(
        node_id=vantage_node_id,
        link_id=None,
        depth=0,
        reachable=v_reachable,
        latency_ms=v_lat,
        packet_loss_pct=v_loss,
        status=v_status,
    )

    # 4. BFS traversal in topological tree order starting from vantage node
    queue: List[Tuple[str, int]] = [(vantage_node_id, 0)]
    visited = {vantage_node_id}

    while queue:
        curr_id, curr_depth = queue.pop(0)
        curr_hop = hop_results[curr_id]

        children = children_by_parent.get(curr_id, [])
        for child_id, link_id in children:
            if child_id in visited:
                continue
            visited.add(child_id)
            child_depth = curr_depth + 1

            x_res = result_by_node.get(child_id)

            # Situation 1: X has no result
            if x_res is None:
                hop_results[child_id] = HopResult(
                    node_id=child_id,
                    link_id=link_id,
                    depth=child_depth,
                    reachable=False,
                    latency_ms=None,
                    packet_loss_pct=None,
                    status="no_data",
                )
                queue.append((child_id, child_depth))
                continue

            x_reachable = bool(x_res.get("reachable") if isinstance(x_res, dict) else x_res.reachable)
            x_lat = x_res.get("latency_ms") if isinstance(x_res, dict) else x_res.latency_ms
            x_loss = x_res.get("packet_loss_pct") if isinstance(x_res, dict) else x_res.packet_loss_pct

            # Situation 2: Parent unreachable or P is failed/behind_failure
            if not curr_hop.reachable or curr_hop.status in ("failed", "behind_failure"):
                hop_results[child_id] = HopResult(
                    node_id=child_id,
                    link_id=link_id,
                    depth=child_depth,
                    reachable=x_reachable,
                    latency_ms=x_lat,
                    packet_loss_pct=x_loss,
                    status="behind_failure",
                )
                queue.append((child_id, child_depth))
                continue

            # Situation 3: X unreachable, P reachable
            is_unreachable = (
                not x_reachable
                or (x_loss is not None and x_loss >= 100.0)
                or (x_lat is None and not x_reachable)
            )
            if is_unreachable:
                hop_results[child_id] = HopResult(
                    node_id=child_id,
                    link_id=link_id,
                    depth=child_depth,
                    reachable=False,
                    latency_ms=None,
                    packet_loss_pct=100.0 if x_loss is None else x_loss,
                    status="failed",
                )
                m = Measurement(
                    component_id=link_id,
                    latency_ms=None,
                    packet_loss_pct=100.0,
                    throughput_mbps=None,
                    connectivity_ok=False,
                    data_source="path_probe",
                    provides=["latency_ms", "packet_loss_pct", "connectivity_ok"],
                )
                derived_measurements.append(m)
                queue.append((child_id, child_depth))
                continue

            # Situation 4: Both X and P reachable
            p_lat = curr_hop.latency_ms if curr_hop.latency_ms is not None else 0.0
            c_lat = x_lat if x_lat is not None else 0.0
            link_lat = max(0.0, round(c_lat - p_lat, 2))

            p_loss_frac = (curr_hop.packet_loss_pct or 0.0) / 100.0
            c_loss_frac = (x_loss or 0.0) / 100.0
            if p_loss_frac >= 1.0 or (1.0 - p_loss_frac) <= 1e-6:
                link_loss_pct = 0.0
            else:
                rem = (1.0 - c_loss_frac) / (1.0 - p_loss_frac)
                link_loss_pct = max(0.0, min(100.0, round((1.0 - rem) * 100.0, 2)))

            m = Measurement(
                component_id=link_id,
                latency_ms=link_lat,
                packet_loss_pct=link_loss_pct,
                throughput_mbps=None,
                connectivity_ok=True,
                data_source="path_probe",
                provides=["latency_ms", "packet_loss_pct", "connectivity_ok"],
            )
            derived_measurements.append(m)

            base = baselines.get(link_id, {})
            rep = diag_engine.evaluate_link(m, base, link_id)
            hop_status = "degraded" if rep.score >= detection_threshold else "ok"

            hop_results[child_id] = HopResult(
                node_id=child_id,
                link_id=link_id,
                depth=child_depth,
                reachable=True,
                latency_ms=x_lat,
                packet_loss_pct=x_loss,
                status=hop_status,
            )
            queue.append((child_id, child_depth))

    # Any remaining nodes in topology that were not reached in BFS
    for node_id in all_nodes:
        if node_id not in hop_results:
            inbound = inbound_link_by_target.get(node_id)
            hop_results[node_id] = HopResult(
                node_id=node_id,
                link_id=inbound.id if inbound else None,
                depth=99,
                reachable=False,
                latency_ms=None,
                packet_loss_pct=None,
                status="no_data",
            )

    return derived_measurements, list(hop_results.values())

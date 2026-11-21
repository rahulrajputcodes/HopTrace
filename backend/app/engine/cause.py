"""Deterministic Root Cause Classifier for HopTrace.

Pure, deterministic heuristic classifier adhering to HopTrace Part 1 Contract §3.
Evaluates observed metrics, topology structure, and time-series history without
external LLM dependencies.

Must NEVER raise an unhandled exception.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from app.engine.models import CauseResult

logger = logging.getLogger(__name__)

GATEWAY_LINK_ID = "L1"


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """Defensively retrieve an attribute or dict key from arbitrary objects."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _get_metric_map(measurements: List[Any]) -> Dict[str, Dict[str, Any]]:
    """Index measurements by component_id / link_id."""
    m_map: Dict[str, Dict[str, Any]] = {}
    if not isinstance(measurements, (list, tuple)):
        return m_map

    for m in measurements:
        if m is None:
            continue
        cid = _safe_get(m, "component_id") or _safe_get(m, "link_id")
        if not cid or not isinstance(cid, str):
            continue

        loss = _safe_get(m, "packet_loss_pct")
        latency = _safe_get(m, "latency_ms")
        throughput = _safe_get(m, "throughput_mbps")
        conn = _safe_get(m, "connectivity_ok", True)

        m_map[cid] = {
            "component_id": cid,
            "packet_loss_pct": float(loss) if loss is not None else None,
            "latency_ms": float(latency) if latency is not None else None,
            "throughput_mbps": float(throughput) if throughput is not None else None,
            "connectivity_ok": bool(conn) if conn is not None else True,
        }
    return m_map


def _analyze_history(history: Optional[List[Any]]) -> Tuple[str, Dict[str, Any]]:
    """Analyze time-series history.

    Returns:
        (trajectory, stats) where trajectory is "abrupt" | "gradual" | "insufficient" | "unknown"
    """
    if not history or not isinstance(history, (list, tuple)) or len(history) < 6:
        return "insufficient", {"count": len(history) if isinstance(history, (list, tuple)) else 0}

    valid_samples = []
    for s in history:
        if not isinstance(s, dict):
            continue
        loss = s.get("packet_loss_pct")
        lat = s.get("latency_ms")
        conn = s.get("connectivity_ok", True)
        valid_samples.append({
            "loss": float(loss) if loss is not None else 0.0,
            "latency": float(lat) if lat is not None else 0.0,
            "connectivity_ok": bool(conn) if conn is not None else True,
        })

    if len(valid_samples) < 6:
        return "insufficient", {"count": len(valid_samples)}

    # Inspect the last 6 samples
    window = valid_samples[-6:]
    first_loss = window[0]["loss"]
    last_loss = window[-1]["loss"]
    first_lat = window[0]["latency"]
    last_lat = window[-1]["latency"]

    # Gradual check: loss or latency rising monotonically-ish across the window,
    # and final sample is still connected (not complete immediate blackout)
    loss_rising = last_loss > first_loss + 5.0
    lat_rising = last_lat > first_lat * 1.3 and (last_lat - first_lat) >= 10.0

    increasing_steps = sum(
        1 for i in range(len(window) - 1)
        if window[i + 1]["loss"] >= window[i]["loss"] or window[i + 1]["latency"] >= window[i]["latency"]
    )

    if (loss_rising or lat_rising) and increasing_steps >= 3 and window[-1]["connectivity_ok"]:
        return "gradual", {
            "first_loss": first_loss,
            "last_loss": last_loss,
            "first_latency": first_lat,
            "last_latency": last_lat,
        }

    # Abrupt check: earlier samples were within baseline thresholds (loss <= 2%, conn == True),
    # followed by sudden failure
    prior_samples = valid_samples[:-1] if len(valid_samples) > 6 else valid_samples[:3]
    all_prior_ok = all(s["connectivity_ok"] and s["loss"] <= 5.0 for s in prior_samples[-5:])

    if all_prior_ok:
        return "abrupt", {
            "baseline_loss": prior_samples[-1]["loss"],
            "final_loss": valid_samples[-1]["loss"],
        }

    return "abrupt", {"note": "default to abrupt for sudden failure"}


def _build_topology_index(topology: Any) -> Tuple[
    Dict[str, Dict[str, Any]],  # nodes by id
    Dict[str, Dict[str, Any]],  # links by id
    Dict[str, List[str]],        # outgoing links by source node
    Dict[str, Set[str]],         # elements by village
]:
    nodes_map: Dict[str, Dict[str, Any]] = {}
    links_map: Dict[str, Dict[str, Any]] = {}
    outgoing_by_node: Dict[str, List[str]] = {}
    village_elements: Dict[str, Set[str]] = {}

    if topology is None:
        return nodes_map, links_map, outgoing_by_node, village_elements

    raw_nodes = _safe_get(topology, "nodes") or []
    raw_links = _safe_get(topology, "links") or []

    for n in raw_nodes:
        nid = _safe_get(n, "id")
        if not nid:
            continue
        props = _safe_get(n, "properties") or {}
        village = _safe_get(n, "village") or props.get("village")
        nodes_map[nid] = {
            "id": nid,
            "type": _safe_get(n, "type", "router"),
            "village": village,
            "properties": props,
        }
        if village:
            village_elements.setdefault(village.lower(), set()).add(nid)

    for l in raw_links:
        lid = _safe_get(l, "id")
        if not lid:
            continue
        src = _safe_get(l, "source")
        tgt = _safe_get(l, "target")
        props = _safe_get(l, "properties") or {}
        medium = _safe_get(l, "medium") or props.get("medium", "")

        links_map[lid] = {
            "id": lid,
            "source": src,
            "target": tgt,
            "medium": medium,
            "properties": props,
        }
        if src:
            outgoing_by_node.setdefault(src, []).append(lid)

        # Associate link with village(s) of its nodes
        src_v = nodes_map.get(src, {}).get("village")
        tgt_v = nodes_map.get(tgt, {}).get("village")
        if src_v:
            village_elements.setdefault(src_v.lower(), set()).add(lid)
        if tgt_v:
            village_elements.setdefault(tgt_v.lower(), set()).add(lid)

    return nodes_map, links_map, outgoing_by_node, village_elements


def _get_downstream_set(
    component_id: str,
    nodes_map: Dict[str, Dict[str, Any]],
    links_map: Dict[str, Dict[str, Any]],
    outgoing_by_node: Dict[str, List[str]],
) -> Tuple[Set[str], Set[str]]:
    """Returns (downstream_nodes, downstream_links) reachable strictly below component_id."""
    downstream_nodes: Set[str] = set()
    downstream_links: Set[str] = set()

    queue: List[str] = []

    if component_id in links_map:
        target = links_map[component_id].get("target")
        if target:
            downstream_nodes.add(target)
            queue.append(target)
    elif component_id in nodes_map:
        queue.append(component_id)

    visited_nodes: Set[str] = set()
    while queue:
        curr_node = queue.pop(0)
        if curr_node in visited_nodes:
            continue
        visited_nodes.add(curr_node)

        for lid in outgoing_by_node.get(curr_node, []):
            downstream_links.add(lid)
            tgt = links_map.get(lid, {}).get("target")
            if tgt and tgt not in visited_nodes:
                downstream_nodes.add(tgt)
                queue.append(tgt)

    return downstream_nodes, downstream_links


def classify_cause(
    measurements: List[Any],
    topology: Any,
    suspected_component_id: Optional[str],
    link_history: Optional[List[dict]] = None,
) -> CauseResult:
    """Deterministically classifies root cause of network failure or degradation."""
    try:
        # 1. Parse measurements
        meas_map = _get_metric_map(measurements)

        # 2. Check for Upstream Failure (Rule 5)
        # Situation: All interior links report >= 98% packet loss
        interior_measured = [
            m for cid, m in meas_map.items()
            if cid != GATEWAY_LINK_ID and m.get("packet_loss_pct") is not None
        ]
        if len(interior_measured) >= 2 and all(
            m["packet_loss_pct"] >= 98.0 for m in interior_measured
        ):
            return CauseResult(
                cause="upstream_failure",
                confidence=0.85,
                reasoning=[
                    f"All {len(interior_measured)} interior distribution links report >= 98% packet loss simultaneously.",
                    "Distribution links remain physically present while transit is interrupted.",
                    "Consistent with upstream gateway blackout or ISP backhaul failure.",
                ],
            )

        # 3. Check for No Suspected Component or Healthy State (Rule 6)
        if not suspected_component_id or not isinstance(suspected_component_id, str):
            return CauseResult(
                cause="unknown",
                confidence=0.0,
                reasoning=["No suspected component identified."],
            )

        curr_meas = meas_map.get(suspected_component_id)
        if curr_meas is not None:
            conn_ok = curr_meas.get("connectivity_ok", True)
            loss_pct = curr_meas.get("packet_loss_pct", 0.0) or 0.0
            lat_ms = curr_meas.get("latency_ms", 0.0) or 0.0
            if conn_ok and loss_pct < 5.0 and lat_ms < 40.0:
                return CauseResult(
                    cause="unknown",
                    confidence=0.0,
                    reasoning=[
                        f"Suspected component '{suspected_component_id}' metrics are within normal baseline thresholds.",
                        f"Observed packet loss: {loss_pct:.1f}%, latency: {lat_ms:.1f}ms, connectivity: ok.",
                    ],
                )

        # 4. Parse Topology
        nodes_map, links_map, outgoing_by_node, village_elements = _build_topology_index(topology)

        # Determine medium and component type
        is_link = suspected_component_id in links_map
        is_node = suspected_component_id in nodes_map
        medium = ""
        comp_village = None

        if is_link:
            medium = str(links_map[suspected_component_id].get("medium", "")).lower()
            src_node = nodes_map.get(links_map[suspected_component_id].get("source", ""))
            tgt_node = nodes_map.get(links_map[suspected_component_id].get("target", ""))
            comp_village = (tgt_node or {}).get("village") or (src_node or {}).get("village")
        elif is_node:
            comp_village = nodes_map[suspected_component_id].get("village")

        is_fiber = "fiber" in medium
        is_wireless = any(w in medium for w in ["wireless", "ptp", "5ghz", "60ghz", "radio"]) or (
            is_node and nodes_map[suspected_component_id].get("type") in ["wireless_bridge", "access_point"]
        )

        # 5. Analyze Time-Series History
        trajectory, hist_stats = _analyze_history(link_history)

        if trajectory == "insufficient":
            return CauseResult(
                cause="unknown",
                confidence=0.0,
                reasoning=[
                    f"Link history unavailable or insufficient (< 6 samples) for '{suspected_component_id}'.",
                    "Cannot reliably distinguish abrupt from gradual failure without time-series depth.",
                ],
            )

        # 6. Fiber Cut (Rule 1)
        # Situation: Fiber link hard-down (connectivity_ok false, loss >= 98%), abrupt
        loss_val = curr_meas.get("packet_loss_pct", 100.0) if curr_meas else 100.0
        conn_val = curr_meas.get("connectivity_ok", False) if curr_meas else False
        is_hard_down = not conn_val or (loss_val is not None and loss_val >= 98.0)

        if is_fiber and is_hard_down and trajectory == "abrupt":
            return CauseResult(
                cause="fiber_cut",
                confidence=0.80,
                reasoning=[
                    f"Hard-down state on fiber backhaul link '{suspected_component_id}'.",
                    f"Observed {loss_val:.1f}% packet loss with connectivity_ok={conn_val}.",
                    "Transition was abrupt following nominal baseline operation.",
                    "Indicates physical fiber cut or optical transceiver disconnect.",
                ],
            )

        # 7. RF Degradation (Rule 2)
        # Situation: Wireless link, loss/latency rising over history, still connected
        if is_wireless and trajectory == "gradual" and not is_hard_down:
            return CauseResult(
                cause="rf_degradation",
                confidence=0.75,
                reasoning=[
                    f"Wireless link '{suspected_component_id}' remains connected with gradual degradation over history.",
                    f"Packet loss rose from {hist_stats.get('first_loss', 0):.1f}% to {hist_stats.get('last_loss', 0):.1f}%.",
                    f"Latency rose from {hist_stats.get('first_latency', 0):.1f}ms to {hist_stats.get('last_latency', 0):.1f}ms.",
                    "Consistent with Fresnel zone obstruction, weather attenuation, or antenna misalignment.",
                ],
            )

        # 8. Power Outage vs Isolated Wireless Failure (Rules 3 & 4)
        if (is_wireless or is_node) and is_hard_down and trajectory == "abrupt":
            downstream_nodes, downstream_links = _get_downstream_set(
                suspected_component_id, nodes_map, links_map, outgoing_by_node
            )
            downstream_elements = downstream_nodes | downstream_links

            # Find co-located elements in the same village that are NOT downstream
            colocated_elements = village_elements.get((comp_village or "").lower(), set())
            independent_colocated = [
                eid for eid in colocated_elements
                if eid != suspected_component_id and eid not in downstream_elements
            ]

            # Check if any independent co-located element also failed
            colocated_failures = []
            for eid in independent_colocated:
                emeas = meas_map.get(eid)
                if emeas and (not emeas.get("connectivity_ok", True) or (emeas.get("packet_loss_pct") or 0) >= 98.0):
                    colocated_failures.append(eid)

            if colocated_failures:
                # Rule 3: Power Outage
                failed_str = ", ".join(colocated_failures[:3])
                return CauseResult(
                    cause="power_outage",
                    confidence=0.60,
                    reasoning=[
                        f"Abrupt loss on '{suspected_component_id}' co-occurred with independent failure of [{failed_str}] in village '{comp_village}'.",
                        f"Independent elements are not downstream of '{suspected_component_id}'.",
                        "Simultaneous co-located drop indicates grid or solar power interruption; verify power/UPS on site.",
                    ],
                )
            else:
                # Rule 4: Isolated wireless hard-down without co-located failure
                return CauseResult(
                    cause="unknown",
                    confidence=0.40,
                    reasoning=[
                        f"Wireless component '{suspected_component_id}' experienced an abrupt connectivity loss.",
                        "No co-located independent failures observed in the same village.",
                        "abrupt loss; cannot tell power from radio failure remotely.",
                    ],
                )

        # Default fallback
        return CauseResult(
            cause="unknown",
            confidence=0.0,
            reasoning=[
                f"Observed pattern for '{suspected_component_id}' does not match a deterministic root cause rule.",
            ],
        )

    except Exception as exc:
        logger.exception("Error in classify_cause: %s", exc)
        return CauseResult(
            cause="unknown",
            confidence=0.0,
            reasoning=[f"Classification failed safely: {exc}"],
        )

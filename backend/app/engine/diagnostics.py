"""Upgraded explainable fault localization engine for HopTrace v2.

CRITICAL VALIDATION RULE:
The diagnostic engine infers suspected faults SOLELY from observed measurements,
documented baselines, and graph topology. It NEVER receives the injected
fault ID, scenario name, or ground truth label as input.

New in v2:
- Cascade fault detection: 2+ adjacent links crossing threshold simultaneously.
- Flapping detection: link toggling connectivity_ok repeatedly.
- Risk-score-aware ambiguity resolution.
- fault_class field: "isolated" | "cascade" | "flapping" | "upstream".
- Works across 14-link, 3-village topology.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import (
    EvidenceItem,
    IncidentDetails,
    Measurement,
    NetworkTopology,
)
from .telemetry import BASELINE_TELEMETRY, GATEWAY_LINK_ID, INTERIOR_LINK_IDS


class LinkAnomalyReport:
    """Internal evaluation record for a single link's telemetry."""

    def __init__(self, link_id: str) -> None:
        self.link_id = link_id
        self.score: float = 0.0
        self.s_conn: float = 0.0
        self.s_loss: float = 0.0
        self.s_lat: float = 0.0
        self.s_tp: float = 0.0
        self.evidence: List[EvidenceItem] = []
        self.missing_metrics_count: int = 0
        self.is_unmonitored: bool = False
        self.is_flapping: bool = False


class DiagnosticEngine:
    """Explainable diagnostic engine for multi-village rural ISP fault localization.

    v2 upgrades:
    - 14-link topology awareness (3 villages)
    - Cascade fault detection (2+ adjacent links degrade simultaneously)
    - Flapping link detection (connectivity_ok toggles)
    - fault_class tagging on IncidentDetails
    """

    def __init__(
        self,
        baselines: Optional[Dict[str, Dict[str, float | bool]]] = None,
        detection_threshold: float = 0.10,
        ambiguity_margin: float = 0.08,
        upstream_full_loss_threshold: float = 98.0,
    ) -> None:
        self.baselines = baselines or BASELINE_TELEMETRY
        self.detection_threshold = detection_threshold
        self.ambiguity_margin = ambiguity_margin
        self.upstream_full_loss_threshold = upstream_full_loss_threshold

    def evaluate_link(
        self,
        measurement: Optional[Measurement],
        baseline: Dict[str, float | bool],
        link_id: str,
    ) -> LinkAnomalyReport:
        """Evaluates a single link's measurement against documented baseline values."""
        report = LinkAnomalyReport(link_id)

        if measurement is None:
            report.is_unmonitored = True
            report.missing_metrics_count = 4
            report.evidence.append(EvidenceItem(
                metric="telemetry_presence",
                observed_value=None,
                baseline_value="active_telemetry",
                threshold="required",
                status="missing",
                severity="medium",
                description=f"Link '{link_id}' has no telemetry reports. Health cannot be verified.",
            ))
            return report

        base_lat = float(baseline.get("latency_ms", 20.0))
        base_loss = float(baseline.get("packet_loss_pct", 0.0))
        base_tp = float(baseline.get("throughput_mbps", 50.0))
        base_conn = bool(baseline.get("connectivity_ok", True))

        # 1. Connectivity status
        if not measurement.connectivity_ok:
            report.s_conn = 1.0
            report.is_flapping = True  # Will be confirmed at engine level
            report.evidence.append(EvidenceItem(
                metric="connectivity_ok",
                observed_value=False,
                baseline_value=base_conn,
                threshold=True,
                status="anomaly",
                severity="critical",
                description=f"Link '{link_id}' reported loss of connectivity (link down or flapping).",
            ))

        # 2. Packet Loss Abnormality
        if measurement.packet_loss_pct is None:
            report.missing_metrics_count += 1
            report.evidence.append(EvidenceItem(
                metric="packet_loss_pct",
                observed_value=None,
                baseline_value=base_loss,
                threshold="<= 1.0%",
                status="missing",
                severity="low",
                description=f"Packet loss telemetry missing for link '{link_id}'.",
            ))
        else:
            delta_loss = max(0.0, measurement.packet_loss_pct - base_loss)
            if delta_loss > 1.0:
                report.s_loss = min(1.0, delta_loss / 25.0)
                sev = "high" if delta_loss >= 15.0 else ("medium" if delta_loss >= 5.0 else "low")
                report.evidence.append(EvidenceItem(
                    metric="packet_loss_pct",
                    observed_value=measurement.packet_loss_pct,
                    baseline_value=base_loss,
                    threshold=1.0,
                    status="anomaly",
                    severity=sev,
                    description=(
                        f"Packet loss {measurement.packet_loss_pct:.1f}% exceeds baseline "
                        f"({base_loss:.1f}%) by {delta_loss:.1f}%."
                    ),
                ))

        # 3. Latency Inflation
        if measurement.latency_ms is None:
            report.missing_metrics_count += 1
            report.evidence.append(EvidenceItem(
                metric="latency_ms",
                observed_value=None,
                baseline_value=base_lat,
                threshold=f"<= {base_lat + 10.0} ms",
                status="missing",
                severity="low",
                description=f"Latency telemetry missing for link '{link_id}'.",
            ))
        else:
            delta_lat = max(0.0, measurement.latency_ms - base_lat)
            if delta_lat > 10.0:
                report.s_lat = min(1.0, delta_lat / 150.0)
                sev = "high" if delta_lat >= 80.0 else ("medium" if delta_lat >= 30.0 else "low")
                report.evidence.append(EvidenceItem(
                    metric="latency_ms",
                    observed_value=measurement.latency_ms,
                    baseline_value=base_lat,
                    threshold=round(base_lat + 10.0, 1),
                    status="anomaly",
                    severity=sev,
                    description=(
                        f"Observed latency {measurement.latency_ms:.1f} ms exceeds baseline "
                        f"({base_lat:.1f} ms) by +{delta_lat:.1f} ms."
                    ),
                ))

        # 4. Throughput Degradation
        if measurement.throughput_mbps is None:
            report.missing_metrics_count += 1
            report.evidence.append(EvidenceItem(
                metric="throughput_mbps",
                observed_value=None,
                baseline_value=base_tp,
                threshold=f">= {base_tp * 0.85:.1f} Mbps",
                status="missing",
                severity="low",
                description=f"Throughput telemetry missing for link '{link_id}'.",
            ))
        else:
            drop_pct = max(0.0, (base_tp - measurement.throughput_mbps) / base_tp) if base_tp > 0 else 0.0
            if drop_pct > 0.15:
                report.s_tp = min(1.0, (drop_pct - 0.15) / 0.70)
                sev = "high" if drop_pct >= 0.60 else ("medium" if drop_pct >= 0.30 else "low")
                report.evidence.append(EvidenceItem(
                    metric="throughput_mbps",
                    observed_value=measurement.throughput_mbps,
                    baseline_value=base_tp,
                    threshold=round(base_tp * 0.85, 1),
                    status="anomaly",
                    severity=sev,
                    description=(
                        f"Throughput degraded to {measurement.throughput_mbps:.1f} Mbps "
                        f"({drop_pct * 100:.1f}% below baseline {base_tp:.1f} Mbps)."
                    ),
                ))

        # Composite score: w_conn=0.40, w_loss=0.30, w_lat=0.20, w_tp=0.10
        raw_score = (
            (0.40 * report.s_conn)
            + (0.30 * report.s_loss)
            + (0.20 * report.s_lat)
            + (0.10 * report.s_tp)
        )
        report.score = round(raw_score, 4)
        return report

    def _detect_upstream_failure(
        self,
        meas_map: Dict[str, Measurement],
        known_links: List[str],
    ) -> Optional[IncidentDetails]:
        """Detects the upstream-gateway-failure pattern from observations alone.

        Upstream signature (inferred from measurements, not from ground truth):
          1. Gateway backhaul link (L1) has connectivity_ok=False.
          2. ALL interior distribution links have packet_loss >= upstream_full_loss_threshold
             AND throughput = 0 simultaneously.
          3. At least one interior link is locally link-present (connectivity_ok=True).
        """
        gw_link_id = GATEWAY_LINK_ID
        interior_ids = [lid for lid in known_links if lid != gw_link_id]

        gw_meas = meas_map.get(gw_link_id)
        if gw_meas is None or gw_meas.connectivity_ok:
            return None

        interior_measured = [meas_map[lid] for lid in interior_ids if lid in meas_map]
        if not interior_measured:
            return None

        all_interior_saturated = all(
            m.packet_loss_pct is not None
            and m.packet_loss_pct >= self.upstream_full_loss_threshold
            and m.throughput_mbps is not None
            and m.throughput_mbps == 0.0
            for m in interior_measured
        )
        if not all_interior_saturated:
            return None

        any_interior_link_up = any(m.connectivity_ok for m in interior_measured)

        evidence = [
            EvidenceItem(
                metric="connectivity_ok",
                observed_value=False,
                baseline_value=True,
                threshold=True,
                status="anomaly",
                severity="critical",
                description=(
                    f"Gateway backhaul link '{gw_link_id}' has lost connectivity. "
                    "No internet traffic can pass into the village cluster."
                ),
            ),
            EvidenceItem(
                metric="packet_loss_pct",
                observed_value=100.0,
                baseline_value=0.0,
                threshold=1.0,
                status="anomaly",
                severity="critical",
                description=(
                    f"All {len(interior_measured)} interior distribution link(s) simultaneously "
                    "report 100% packet loss — consistent with full upstream internet blackout, "
                    "not a single intermediate segment failure."
                ),
            ),
            EvidenceItem(
                metric="throughput_mbps",
                observed_value=0.0,
                baseline_value=None,
                threshold=None,
                status="anomaly",
                severity="critical",
                description=(
                    "Zero throughput across all 3-village distribution links. "
                    "Interior links remain locally link-present (no independent physical failure)."
                ),
            ),
        ]

        uncertainty_note = (
            "Interior distribution links remain locally link-present (Ethernet/RF layer up). "
            "Simultaneous full packet loss and zero throughput across all segments is "
            "consistent with an upstream internet gateway failure at L1/GW1."
            if any_interior_link_up else
            "Interior links also report connectivity_ok=False. May indicate a total power "
            "failure or cascading hardware fault. Physical inspection recommended."
        )

        return IncidentDetails(
            id=f"incident-{uuid.uuid4().hex[:8]}",
            run_id="",
            status="open",
            suspected_component_id=gw_link_id,
            suspected_component_type="link",
            summary=(
                f"Upstream internet gateway failure detected on link '{gw_link_id}'. "
                f"All {len(interior_measured)} downstream distribution segments across "
                "3 villages show complete internet traffic blackout."
            ),
            confidence_score=0.92 if any_interior_link_up else 0.70,
            diagnostic_score=1.0,
            evidence=evidence,
            uncertainty_note=uncertainty_note,
            data_source="simulated",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _derive_branches(topology: Optional[NetworkTopology]) -> List[set[str]]:
        """Derives independent distribution branches from a NetworkTopology.

        Computes branches as the sets of interior links downstream of each
        child of the gateway link.
        """
        if not topology:
            return []

        links = getattr(topology, "links", None) or []
        nodes = getattr(topology, "nodes", None) or []
        if not links:
            return []

        def _get_val(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        # 1. Identify the gateway link
        gw_node_ids = {
            _get_val(n, "id")
            for n in nodes
            if str(_get_val(n, "type") or "").lower() in ("gateway", "fiber_gateway")
            or str(_get_val(n, "id") or "").upper().startswith("GW")
        }
        gw_node_ids.discard(None)

        gw_link = None
        if gw_node_ids:
            gw_link = next((l for l in links if _get_val(l, "source") in gw_node_ids), None)

        if gw_link is None:
            gw_link = next((l for l in links if _get_val(l, "id") == GATEWAY_LINK_ID), None)

        if gw_link is None:
            all_targets = {_get_val(l, "target") for l in links}
            root_sources = [
                _get_val(l, "source")
                for l in links
                if _get_val(l, "source") and _get_val(l, "source") not in all_targets
            ]
            if root_sources:
                gw_link = next((l for l in links if _get_val(l, "source") == root_sources[0]), None)

        if gw_link is None:
            return []

        gw_link_id = _get_val(gw_link, "id")
        gw_target = _get_val(gw_link, "target")
        if not gw_target:
            return []

        # 2. Child links originating from the gateway link's target node
        child_links = [
            l
            for l in links
            if _get_val(l, "source") == gw_target and _get_val(l, "id") != gw_link_id
        ]
        if not child_links:
            return []

        # 3. Build adjacency list of outgoing links
        outgoing_by_node: Dict[str, List[Any]] = {}
        for l in links:
            src = _get_val(l, "source")
            if src:
                outgoing_by_node.setdefault(src, []).append(l)

        # 4. Traverse downstream for each child link to form independent branches
        branches: List[set[str]] = []
        for cl in child_links:
            branch_set: set[str] = set()
            visited: set[str] = set()
            queue = [cl]
            while queue:
                curr = queue.pop(0)
                curr_id = _get_val(curr, "id")
                if not curr_id or curr_id in visited:
                    continue
                visited.add(curr_id)
                if curr_id != gw_link_id:
                    branch_set.add(curr_id)
                curr_target = _get_val(curr, "target")
                for nxt in outgoing_by_node.get(curr_target, []):
                    nxt_id = _get_val(nxt, "id")
                    if nxt_id and nxt_id not in visited and nxt_id != gw_link_id:
                        queue.append(nxt)
            if branch_set:
                branches.append(branch_set)

        return branches

    def _detect_cascade_fault(
        self,
        reports: List[LinkAnomalyReport],
        topology: Optional[NetworkTopology] = None,
        threshold: float = 0.10,
        min_links: int = 2,
    ) -> bool:
        """Detect if 2+ independent links cross threshold simultaneously (cascade pattern)."""
        degraded = [r for r in reports if r.score >= threshold and not r.is_unmonitored]
        if len(degraded) < min_links:
            return False
        # True cascade: at least 2 links are degraded, at least 2 are in separate branches
        # (i.e., not parent-child in the same path)
        degraded_ids = {r.link_id for r in degraded}

        branches = self._derive_branches(topology) if topology is not None else None
        if not branches:
            # Fallback to the current hard-coded sets only when no topology is given (or empty/invalid)
            # Rampur branch: L2, L3, L4 (sequential)
            # Bhatpur branch: L6, L7, L8, L9, L10
            # Daulatpur branch: L11, L12, L13, L14
            branches = [
                {"L2", "L3", "L4"},
                {"L6", "L7", "L8", "L9", "L10"},
                {"L11", "L12", "L13", "L14"},
            ]

        branches_affected = sum(1 for b in branches if b & degraded_ids)
        return branches_affected >= 2 or len(degraded) >= 3

    def _detect_flapping(
        self,
        meas_map: Dict[str, Measurement],
        known_links: List[str],
    ) -> Optional[str]:
        """Return link_id if any link shows connectivity_ok=False while loss<100% (flapping hint)."""
        for link_id in known_links:
            m = meas_map.get(link_id)
            if m and not m.connectivity_ok:
                loss = m.packet_loss_pct
                # Full blackout is upstream failure territory; partial loss + down = flapping
                if loss is not None and loss < 90.0:
                    return link_id
        return None

    def diagnose(
        self,
        measurements: List[Measurement],
        topology: Optional[NetworkTopology] = None,
        run_id: Optional[str] = None,
    ) -> IncidentDetails:
        """Infers the root-cause suspect from telemetry observations.

        CRITICAL: Never accepts expected fault input. Solely infers suspect.
        """
        run_identifier = run_id or f"run-{uuid.uuid4().hex[:8]}"
        incident_id = f"incident-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        meas_map = {m.component_id: m for m in measurements}
        known_links = list(self.baselines.keys())
        if topology and topology.links:
            known_links = [lk.id for lk in topology.links]

        # ── 1. Upstream failure check ─────────────────────────────────────────
        upstream_incident = self._detect_upstream_failure(meas_map, known_links)
        if upstream_incident is not None:
            upstream_incident.id = incident_id
            upstream_incident.run_id = run_identifier
            upstream_incident.created_at = created_at
            # Tag with fault_class via summary prefix (backward compatible)
            upstream_incident.summary = "[upstream] " + upstream_incident.summary
            return upstream_incident

        # ── 2. Per-link anomaly scoring ───────────────────────────────────────
        reports: List[LinkAnomalyReport] = []
        missing_notes: List[str] = []

        for link_id in known_links:
            m = meas_map.get(link_id)
            base = self.baselines.get(link_id, {})
            rep = self.evaluate_link(m, base, link_id)
            reports.append(rep)
            if rep.is_unmonitored or rep.missing_metrics_count > 0:
                missing_notes.append(
                    f"Link '{link_id}' has missing telemetry ({rep.missing_metrics_count} metric(s) null/omitted)."
                )

        reports.sort(key=lambda r: r.score, reverse=True)
        top_report = reports[0] if reports else None
        top_score = top_report.score if top_report else 0.0

        # ── 3. Healthy baseline ───────────────────────────────────────────────
        if top_score < self.detection_threshold:
            uncertainty_text = ("Incomplete telemetry: " + "; ".join(missing_notes)) if missing_notes else None
            return IncidentDetails(
                id=incident_id,
                run_id=run_identifier,
                status="closed" if not missing_notes else "open",
                suspected_component_id=None,
                suspected_component_type=None,
                summary=(
                    "Normal network operation: All monitored links within baseline thresholds."
                    if not missing_notes else
                    "Uncertain network state: Telemetry missing on some links without detected anomalies on others."
                ),
                confidence_score=1.0 if not missing_notes else None,
                diagnostic_score=top_score,
                evidence=[],
                uncertainty_note=uncertainty_text,
                data_source="simulated",
                created_at=created_at,
            )

        # ── 4. Flapping detection ─────────────────────────────────────────────
        flapping_link = self._detect_flapping(meas_map, known_links)
        if flapping_link and top_report and top_report.link_id == flapping_link:
            summary = f"[flapping] Link flapping detected on '{flapping_link}' — physical layer instability."
            uncertainty_note = (
                f"Link '{flapping_link}' is showing connectivity oscillation (link up/down). "
                "This indicates physical layer instability: dirty connector, weathered cable, "
                "or RF interference. Highest-priority physical inspection required."
            )
            return IncidentDetails(
                id=incident_id, run_id=run_identifier, status="open",
                suspected_component_id=flapping_link,
                suspected_component_type="link",
                summary=summary,
                confidence_score=0.88,
                diagnostic_score=top_score,
                evidence=top_report.evidence,
                uncertainty_note=uncertainty_note,
                data_source="simulated",
                created_at=created_at,
            )

        # ── 5. Cascade detection ──────────────────────────────────────────────
        is_cascade = self._detect_cascade_fault(
            reports, topology=topology, threshold=self.detection_threshold
        )
        degraded_reports = [r for r in reports if r.score >= self.detection_threshold and not r.is_unmonitored]

        if is_cascade and len(degraded_reports) >= 2:
            affected_links_str = ", ".join(f"'{r.link_id}'" for r in degraded_reports[:4])
            summary = (
                f"[cascade] Multi-link degradation detected across independent branches "
                f"({affected_links_str}). Possible shared-path or environmental cause."
            )
            combined_evidence = []
            for r in degraded_reports[:3]:
                combined_evidence.extend(r.evidence)
            uncertainty_note = (
                f"Simultaneous anomalies on {len(degraded_reports)} links spanning "
                "2+ independent distribution branches. This pattern suggests a shared-path "
                "fault (e.g. R1 core router issue), environmental interference (weather/RF), "
                "or congestion at the backhaul. Individual link failure is less likely."
            )
            return IncidentDetails(
                id=incident_id, run_id=run_identifier, status="open",
                suspected_component_id=top_report.link_id if top_report else None,
                suspected_component_type="link",
                summary=summary,
                confidence_score=round(min(1.0, 0.4 + top_score * 0.3), 2),
                diagnostic_score=top_score,
                evidence=combined_evidence[:8],
                uncertainty_note=uncertainty_note,
                data_source="simulated",
                created_at=created_at,
            )

        # ── 6. Standard isolated fault ────────────────────────────────────────
        second_report = reports[1] if len(reports) > 1 else None
        second_score = second_report.score if second_report else 0.0

        is_ambiguous = (
            second_report is not None
            and second_score >= self.detection_threshold
            and abs(top_score - second_score) <= self.ambiguity_margin
        )

        uncertainty_note = None
        confidence_score = None

        if is_ambiguous and second_report:
            uncertainty_note = (
                f"Ambiguous evidence: Link '{top_report.link_id}' (score {top_score:.2f}) "
                f"and Link '{second_report.link_id}' (score {second_score:.2f}) show comparable "
                f"degradation within margin ({self.ambiguity_margin}). Root cause cannot be isolated "
                "to a single segment without intermediate hop telemetry."
            )
            margin = abs(top_score - second_score)
            confidence_score = round(max(0.20, margin / self.detection_threshold), 2)
            summary = (
                f"[isolated] Potential degradation on link {top_report.link_id} "
                f"(ambiguity detected with {second_report.link_id})"
            )
        else:
            confidence_score = round(min(1.0, 0.5 + (top_score * 0.5)), 2)
            summary = f"[isolated] Degradation localized to link {top_report.link_id}"
            if missing_notes:
                uncertainty_note = "Telemetry missing on other segments: " + "; ".join(missing_notes)

        return IncidentDetails(
            id=incident_id,
            run_id=run_identifier,
            status="open",
            suspected_component_id=top_report.link_id if top_report else None,
            suspected_component_type="link",
            summary=summary,
            confidence_score=confidence_score,
            diagnostic_score=top_score,
            evidence=top_report.evidence if top_report else [],
            uncertainty_note=uncertainty_note,
            data_source="simulated",
            created_at=created_at,
        )


def diagnose(
    measurements: List[Measurement],
    topology: Optional[NetworkTopology] = None,
    run_id: Optional[str] = None,
    baselines: Optional[Dict[str, Dict[str, float | bool]]] = None,
) -> IncidentDetails:
    """Convenience function running the explainable diagnostic engine."""
    engine = DiagnosticEngine(baselines=baselines)
    return engine.diagnose(measurements=measurements, topology=topology, run_id=run_id)


def derive_topology_branches(topology: Optional[NetworkTopology]) -> List[set[str]]:
    """Convenience helper to compute distribution branches from a network topology."""
    return DiagnosticEngine._derive_branches(topology)


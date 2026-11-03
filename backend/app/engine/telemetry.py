"""Deterministic simulated telemetry generator for HopTrace.

NOTE: All measurements produced by this module are SIMULATED for testing
and validation purposes. They do NOT represent data from a live or production ISP.

Documented Baseline Model:
- L1 (Fiber Backhaul): 15.0 ms latency, 0.0% loss, 100.0 Mbps throughput, OK.
- L2 (Tower Ethernet): 2.0 ms latency, 0.0% loss, 80.0 Mbps throughput, OK.
- L3 (Wireless PtP Bridge): 25.0 ms latency, 0.5% loss, 35.0 Mbps throughput, OK.
- L4 (North AP Ethernet): 3.0 ms latency, 0.0% loss, 50.0 Mbps throughput, OK.
- L5 (South AP Ethernet): 5.0 ms latency, 0.0% loss, 60.0 Mbps throughput, OK.

Upstream Failure Model (upstream_failure scenario):
When the upstream gateway (GW1) or its fiber connection fails:
  - L1 (GW1->R1): loses connectivity completely.
      connectivity_ok=False, packet_loss_pct=100.0, throughput_mbps=0.0,
      latency_ms=None (internet targets unreachable).
  - L2–L5 (interior distribution links): remain locally link-present at the
      Ethernet/RF layer (the village LAN is still switched), but carry zero
      internet traffic. Observed pattern:
      connectivity_ok=True (local physical layer up),
      packet_loss_pct=100.0 (no internet frames pass),
      throughput_mbps=0.0 (no internet data),
      latency_ms=None (internet ICMP targets unreachable).
  This fingerprint — gateway link fully down, all downstream links showing
  full packet loss with no measurable internet latency — is the canonical
  upstream failure signature used by the diagnostic engine.

Gradual Degradation Model (gradual_degradation scenario):
A single link degrades linearly from its baseline toward the full severity
fault values over RAMP_TICKS simulation ticks.  At progress=0 the link is
healthy; at progress=1 it matches the degrade_link steady-state values.
RAMP_TICKS = 40 (approximately 2 minutes at the 3-second streaming tick).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from backend.app.engine.models import Measurement

# Documented constant: number of streaming ticks over which gradual_degradation
# ramps from baseline to full severity.  At the default 3-second tick this is
# approximately 2 minutes.  Must match the ramp-state logic in facade.py.
RAMP_TICKS: int = 40


# Documented baseline metrics per link
BASELINE_TELEMETRY: Dict[str, Dict[str, float | bool]] = {
    "L1": {
        "latency_ms": 15.0,
        "packet_loss_pct": 0.0,
        "throughput_mbps": 100.0,
        "connectivity_ok": True,
    },
    "L2": {
        "latency_ms": 2.0,
        "packet_loss_pct": 0.0,
        "throughput_mbps": 80.0,
        "connectivity_ok": True,
    },
    "L3": {
        "latency_ms": 25.0,
        "packet_loss_pct": 0.5,
        "throughput_mbps": 35.0,
        "connectivity_ok": True,
    },
    "L4": {
        "latency_ms": 3.0,
        "packet_loss_pct": 0.0,
        "throughput_mbps": 50.0,
        "connectivity_ok": True,
    },
    "L5": {
        "latency_ms": 5.0,
        "packet_loss_pct": 0.0,
        "throughput_mbps": 60.0,
        "connectivity_ok": True,
    },
}

# Severity scaling factors for degradation scenarios
SEVERITY_FACTORS = {
    "low": {
        "latency_delta_ms": 35.0,
        "packet_loss_delta_pct": 5.0,
        "throughput_multiplier": 0.70,
    },
    "medium": {
        "latency_delta_ms": 90.0,
        "packet_loss_delta_pct": 15.0,
        "throughput_multiplier": 0.40,
    },
    "high": {
        "latency_delta_ms": 175.0,
        "packet_loss_delta_pct": 25.0,
        "throughput_multiplier": 0.15,
    },
}

# Upstream-gateway links: the link ID that directly terminates at GW1 (gateway).
# In the canonical topology this is L1 (GW1 -> R1).
# Interior distribution links share the upstream failure symptom differently:
# they remain locally link-present but carry zero internet traffic.
GATEWAY_LINK_ID = "L1"
INTERIOR_LINK_IDS = ["L2", "L3", "L4", "L5"]


class SimulatedTelemetryGenerator:
    """Produces deterministic simulated telemetry for laboratory scenarios."""

    def __init__(
        self,
        baseline_metrics: Optional[Dict[str, Dict[str, float | bool]]] = None,
    ) -> None:
        self.baselines = baseline_metrics or BASELINE_TELEMETRY

    def generate_measurements(
        self,
        scenario: str = "baseline",
        target_link_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        severity: str = "medium",
        missing_link_ids: Optional[List[str]] = None,
        ambiguous_link_ids: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
        ramp_progress: float = 0.0,
    ) -> List[Measurement]:
        """Generates deterministic measurements based on scenario specifications.

        Supported scenarios:
        - baseline: All links report healthy baseline values.
        - degrade_link: Target link suffers increased latency, packet loss, and reduced throughput.
        - gradual_degradation: Target link degrades linearly; progress in [0,1] controls the ramp.
          At ramp_progress=0 the link is at baseline; at 1.0 it matches degrade_link steady-state.
        - access_point_failure: Target AP's incoming link suffers complete connectivity failure.
        - upstream_failure: Gateway or upstream fiber fails (target_node_id="GW1" or similar).
            L1 loses full connectivity; L2-L5 stay locally link-present but
            carry zero internet traffic (packet_loss=100%, throughput=0, latency=null).
        - ambiguous_fault: Multiple links (e.g., L2 and L3) suffer equal degradation.
        - missing_measurements: Selected links have null or missing telemetry.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        missing_set = set(missing_link_ids or [])
        measurements: List[Measurement] = []

        factors = SEVERITY_FACTORS.get(severity, SEVERITY_FACTORS["medium"])

        # Determine which links have faults injected
        degraded_links: Dict[str, Dict[str, float]] = {}

        if scenario == "degrade_link" and target_link_id:
            degraded_links[target_link_id] = factors
        elif scenario == "ambiguous_fault":
            links_to_degrade = ambiguous_link_ids or ["L2", "L3"]
            for lid in links_to_degrade:
                degraded_links[lid] = factors

        for link_id, base in self.baselines.items():
            # Check if this link should have null measurements
            if link_id in missing_set:
                measurements.append(
                    Measurement(
                        component_id=link_id,
                        timestamp_utc=ts,
                        latency_ms=None,
                        packet_loss_pct=None,
                        throughput_mbps=None,
                        connectivity_ok=False,
                        data_source="simulated",
                    )
                )
                continue

            # upstream_failure scenario: gateway link drops, interior links saturate
            if scenario == "upstream_failure":
                if link_id == GATEWAY_LINK_ID:
                    # Gateway link: full connectivity loss
                    measurements.append(
                        Measurement(
                            component_id=link_id,
                            timestamp_utc=ts,
                            latency_ms=None,
                            packet_loss_pct=100.0,
                            throughput_mbps=0.0,
                            connectivity_ok=False,
                            data_source="simulated",
                        )
                    )
                else:
                    # Interior distribution links: locally up, zero internet traffic
                    measurements.append(
                        Measurement(
                            component_id=link_id,
                            timestamp_utc=ts,
                            latency_ms=None,
                            packet_loss_pct=100.0,
                            throughput_mbps=0.0,
                            connectivity_ok=True,
                            data_source="simulated",
                        )
                    )
                continue

            # access_point_failure scenario
            if scenario == "access_point_failure":
                # If target is AP1, incoming link L4 fails; if AP2, link L5 fails
                if (target_node_id == "AP1" and link_id == "L4") or (
                    target_node_id == "AP2" and link_id == "L5"
                ):
                    measurements.append(
                        Measurement(
                            component_id=link_id,
                            timestamp_utc=ts,
                            latency_ms=None,
                            packet_loss_pct=100.0,
                            throughput_mbps=0.0,
                            connectivity_ok=False,
                            data_source="simulated",
                        )
                    )
                    continue

            # gradual_degradation scenario: linear ramp on target link
            if scenario == "gradual_degradation" and link_id == target_link_id:
                measurements.append(
                    self.generate_ramp_measurement(
                        link_id=link_id,
                        severity=severity,
                        progress=ramp_progress,
                        timestamp=ts,
                    )
                )
                continue

            # degrade_link / ambiguous_fault scenario
            if link_id in degraded_links:
                f = degraded_links[link_id]
                base_lat = float(base["latency_ms"])
                base_loss = float(base["packet_loss_pct"])
                base_tp = float(base["throughput_mbps"])

                measurements.append(
                    Measurement(
                        component_id=link_id,
                        timestamp_utc=ts,
                        latency_ms=round(base_lat + f["latency_delta_ms"], 2),
                        packet_loss_pct=round(base_loss + f["packet_loss_delta_pct"], 2),
                        throughput_mbps=round(base_tp * f["throughput_multiplier"], 2),
                        connectivity_ok=True,
                        data_source="simulated",
                    )
                )
            else:
                # Normal healthy baseline measurement
                measurements.append(
                    Measurement(
                        component_id=link_id,
                        timestamp_utc=ts,
                        latency_ms=float(base["latency_ms"]),
                        packet_loss_pct=float(base["packet_loss_pct"]),
                        throughput_mbps=float(base["throughput_mbps"]),
                        connectivity_ok=bool(base["connectivity_ok"]),
                        data_source="simulated",
                    )
                )

        return measurements

    def generate_ramp_measurement(
        self,
        link_id: str,
        severity: str,
        progress: float,
        timestamp: Optional[str] = None,
    ) -> Measurement:
        """Generates a single ramped measurement for a degrading link.

        Metrics interpolate linearly from baseline to full-severity values.
        progress is in [0, 1]:  0 = healthy baseline, 1 = full degrade_link values.
        The same noise profile as streaming is applied (deterministic ±5% jitter
        based on hash of link_id and progress to keep tests reproducible).
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        base = self.baselines.get(link_id, {})
        factors = SEVERITY_FACTORS.get(severity, SEVERITY_FACTORS["medium"])

        base_lat = float(base.get("latency_ms", 20.0))
        base_loss = float(base.get("packet_loss_pct", 0.0))
        base_tp = float(base.get("throughput_mbps", 50.0))

        p = max(0.0, min(1.0, progress))

        # Target (full severity) values
        target_lat = base_lat + factors["latency_delta_ms"]
        target_loss = base_loss + factors["packet_loss_delta_pct"]
        target_tp = base_tp * factors["throughput_multiplier"]

        # Deterministic noise: ±5% jitter using math.sin seeded by link hash
        noise_seed = (hash(link_id) % 1000) / 1000.0
        jitter = math.sin(noise_seed + p * math.pi) * 0.05

        ramp_lat = base_lat + p * (target_lat - base_lat) * (1.0 + jitter)
        ramp_loss = max(0.0, base_loss + p * (target_loss - base_loss) * (1.0 + jitter))
        ramp_tp = max(0.0, base_tp + p * (target_tp - base_tp) * (1.0 - jitter))

        return Measurement(
            component_id=link_id,
            timestamp_utc=ts,
            latency_ms=round(ramp_lat, 2),
            packet_loss_pct=round(ramp_loss, 2),
            throughput_mbps=round(ramp_tp, 2),
            connectivity_ok=True,
            data_source="simulated",
        )

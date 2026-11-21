"""Expanded 15-node, 3-village network topology for HopTrace v2.

Topology Structure (Village Cluster: Rampur Block):
═══════════════════════════════════════════════════

VILLAGE 1 — RAMPUR (Primary)
  GW1 → R1 (Fiber Backhaul 100Mbps)
  R1 → WB1 (Ethernet to Bridge Tx)
  WB1 → WB2 (5GHz PtP 3.2km to North Hamlet)
  WB2 → AP1 (North Market AP)
  R1 → AP2 (Panchayat Bhawan AP)

VILLAGE 2 — BHATPUR (North, via 60GHz PtP hop from R1)
  R1 → WB3 (Ethernet to Bhatpur Bridge Tx)
  WB3 → WB4 (60GHz PtP 2.8km to Bhatpur)
  WB4 → R2 (Bhatpur Village Router)
  R2 → AP3 (Bhatpur Market AP)
  R2 → AP4 (Bhatpur School AP)

VILLAGE 3 — DAULATPUR (South, via second wireless hop)
  R1 → WB5 (South Bridge Tx)
  WB5 → WB6 (5GHz PtP 4.1km to South Hamlet)
  WB6 → AP5 (South Market AP)
  WB6 → AP6 (Daulatpur Health Centre AP)

Subscribers (20 total):
  AP1 → SUB101, SUB102, SUB103
  AP2 → SUB201, SUB202, SUB203, SUB204
  AP3 → SUB301, SUB302, SUB303
  AP4 → SUB401, SUB402, SUB403
  AP5 → SUB501, SUB502, SUB503
  AP6 → SUB601, SUB602

Links (14 total):
  L1: GW1→R1  (Fiber 100Mbps)
  L2: R1→WB1  (GE Ethernet)
  L3: WB1→WB2 (5GHz PtP 3.2km)
  L4: WB2→AP1 (FE Ethernet)
  L5: R1→AP2  (GE Ethernet)
  L6: R1→WB3  (GE Ethernet)
  L7: WB3→WB4 (60GHz PtP 2.8km)
  L8: WB4→R2  (GE Ethernet)
  L9: R2→AP3  (FE Ethernet)
  L10: R2→AP4 (FE Ethernet)
  L11: R1→WB5 (GE Ethernet)
  L12: WB5→WB6 (5GHz PtP 4.1km)
  L13: WB6→AP5 (FE Ethernet)
  L14: WB6→AP6 (FE Ethernet)
"""

from __future__ import annotations

from typing import Dict, List, Optional
from .models import (
    AffectedSubscriber,
    NetworkTopology,
    Subscriber,
    TopologyLink,
    TopologyNode,
)


def get_default_nodes() -> List[TopologyNode]:
    """Returns canonical node definitions for the 3-village cluster."""
    return [
        # ── Gateway ──────────────────────────────────────────────────────────
        TopologyNode(
            id="GW1",
            type="gateway",
            label="Taluk PoP — Fiber Gateway",
            status="healthy",
            properties={
                "location": "Taluk Substation, Block HQ",
                "ip": "10.0.0.1",
                "village": "block_hq",
                "powerSource": "Grid Mains 230V",
                "batteryVoltage": 52.8,
                "solarAmps": 0.0,
                "lat": 27.20000,  # illustrative placement, not surveyed
                "lon": 80.57877,
            },
        ),
        # ── Core Router ──────────────────────────────────────────────────────
        TopologyNode(
            id="R1",
            type="router",
            label="Rampur Core Router (Tower)",
            status="healthy",
            properties={
                "location": "Village Water Tower, Rampur",
                "ip": "10.1.0.1",
                "village": "rampur",
                "powerSource": "Grid + 48V UPS",
                "batteryVoltage": 51.4,
                "solarAmps": 0.0,
                "lat": 27.20000,  # illustrative placement, not surveyed
                "lon": 80.60000,
            },
        ),
        # ── Village 1 — Rampur Wireless Bridges ──────────────────────────────
        TopologyNode(
            id="WB1",
            type="wireless_bridge",
            label="Rampur Bridge Tx (5GHz)",
            status="healthy",
            properties={
                "location": "Village Water Tower, Rampur",
                "village": "rampur",
                "frequency": "5GHz",
                "powerSource": "Solar + 12V LiFePO4",
                "batteryVoltage": 12.8,
                "solarAmps": 5.2,
                "lat": 27.20045,  # illustrative placement, not surveyed
                "lon": 80.60000,
            },
        ),
        TopologyNode(
            id="WB2",
            type="wireless_bridge",
            label="North Hamlet Bridge Rx (5GHz)",
            status="healthy",
            properties={
                "location": "North Hamlet Pole, Rampur",
                "village": "rampur",
                "frequency": "5GHz",
                "powerSource": "Solar + 12V LiFePO4",
                "batteryVoltage": 12.5,
                "solarAmps": 4.6,
                "lat": 27.22879,  # illustrative placement, not surveyed
                "lon": 80.60562,
            },
        ),
        # ── Village 1 — Rampur Access Points ─────────────────────────────────
        TopologyNode(
            id="AP1",
            type="access_point",
            label="Rampur North Market AP",
            status="healthy",
            properties={
                "location": "Market Square, North Rampur",
                "village": "rampur",
                "coverage_radius_m": 300,
                "powerSource": "PoE 24V Switch",
                "batteryVoltage": 24.0,
                "lat": 27.22906,  # illustrative placement, not surveyed
                "lon": 80.60602,
            },
        ),
        TopologyNode(
            id="AP2",
            type="access_point",
            label="Rampur Panchayat Bhawan AP",
            status="healthy",
            properties={
                "location": "Gram Panchayat Bhawan, Rampur",
                "village": "rampur",
                "coverage_radius_m": 250,
                "powerSource": "PoE 24V Switch",
                "batteryVoltage": 24.0,
                "lat": 27.20000,  # illustrative placement, not surveyed
                "lon": 80.59949,
            },
        ),
        # ── Village 2 — Bhatpur Wireless Bridges ─────────────────────────────
        TopologyNode(
            id="WB3",
            type="wireless_bridge",
            label="Bhatpur Bridge Tx (60GHz)",
            status="healthy",
            properties={
                "location": "R1 Tower, Rampur (Tx side)",
                "village": "bhatpur",
                "frequency": "60GHz",
                "powerSource": "Grid + PoE",
                "batteryVoltage": 24.0,
                "solarAmps": 0.0,
                "lat": 27.20000,  # illustrative placement, not surveyed
                "lon": 80.60051,
            },
        ),
        TopologyNode(
            id="WB4",
            type="wireless_bridge",
            label="Bhatpur Bridge Rx (60GHz)",
            status="healthy",
            properties={
                "location": "Bhatpur Hillock Pole",
                "village": "bhatpur",
                "frequency": "60GHz",
                "powerSource": "Solar + 12V LiFePO4",
                "batteryVoltage": 12.6,
                "solarAmps": 6.1,
                "lat": 27.20652,  # illustrative placement, not surveyed
                "lon": 80.62785,
            },
        ),
        TopologyNode(
            id="R2",
            type="router",
            label="Bhatpur Village Router",
            status="healthy",
            properties={
                "location": "Bhatpur Community Hall Rooftop",
                "ip": "10.2.0.1",
                "village": "bhatpur",
                "powerSource": "Grid + UPS",
                "batteryVoltage": 48.0,
                "solarAmps": 0.0,
                "lat": 27.20652,  # illustrative placement, not surveyed
                "lon": 80.62836,
            },
        ),
        # ── Village 2 — Bhatpur Access Points ────────────────────────────────
        TopologyNode(
            id="AP3",
            type="access_point",
            label="Bhatpur Market AP",
            status="healthy",
            properties={
                "location": "Bhatpur Weekly Market Ground",
                "village": "bhatpur",
                "coverage_radius_m": 280,
                "powerSource": "PoE 24V Switch",
                "batteryVoltage": 24.0,
                "lat": 27.20697,  # illustrative placement, not surveyed
                "lon": 80.62836,
            },
        ),
        TopologyNode(
            id="AP4",
            type="access_point",
            label="Bhatpur Govt School AP",
            status="healthy",
            properties={
                "location": "Bhatpur Government Secondary School",
                "village": "bhatpur",
                "coverage_radius_m": 200,
                "powerSource": "PoE 24V Switch",
                "batteryVoltage": 24.0,
                "lat": 27.20607,  # illustrative placement, not surveyed
                "lon": 80.62836,
            },
        ),
        # ── Village 3 — Daulatpur Wireless Bridges ────────────────────────────
        TopologyNode(
            id="WB5",
            type="wireless_bridge",
            label="Daulatpur Bridge Tx (5GHz)",
            status="healthy",
            properties={
                "location": "R1 Tower, Rampur (South face)",
                "village": "daulatpur",
                "frequency": "5GHz",
                "powerSource": "Grid + PoE",
                "batteryVoltage": 24.0,
                "solarAmps": 0.0,
                "lat": 27.19955,  # illustrative placement, not surveyed
                "lon": 80.60000,
            },
        ),
        TopologyNode(
            id="WB6",
            type="wireless_bridge",
            label="Daulatpur Bridge Rx (5GHz)",
            status="healthy",
            properties={
                "location": "Daulatpur Temple Compound Pole",
                "village": "daulatpur",
                "frequency": "5GHz",
                "powerSource": "Solar + 12V LiFePO4",
                "batteryVoltage": 12.3,
                "solarAmps": 4.9,
                "lat": 27.17130,  # illustrative placement, not surveyed
                "lon": 80.62665,
            },
        ),
        # ── Village 3 — Daulatpur Access Points ──────────────────────────────
        TopologyNode(
            id="AP5",
            type="access_point",
            label="Daulatpur South Market AP",
            status="healthy",
            properties={
                "location": "Daulatpur Bazaar",
                "village": "daulatpur",
                "coverage_radius_m": 320,
                "powerSource": "PoE 24V Switch",
                "batteryVoltage": 24.0,
                "lat": 27.17130,  # illustrative placement, not surveyed
                "lon": 80.62715,
            },
        ),
        TopologyNode(
            id="AP6",
            type="access_point",
            label="Daulatpur PHC & e-Gram AP",
            status="healthy",
            properties={
                "location": "Primary Health Centre, Daulatpur",
                "village": "daulatpur",
                "coverage_radius_m": 230,
                "powerSource": "Grid + UPS",
                "batteryVoltage": 48.0,
                "solarAmps": 0.0,
                "lat": 27.17085,  # illustrative placement, not surveyed
                "lon": 80.62665,
            },
        ),
    ]


def get_default_links() -> List[TopologyLink]:
    """Returns canonical link definitions for the 3-village cluster."""
    return [
        # ── Village 1 — Rampur backbone ──────────────────────────────────────
        TopologyLink(
            id="L1",
            source="GW1", target="R1",
            status="healthy",
            latency_ms=15.0, packet_loss_pct=0.0, throughput_mbps=100.0,
            properties={"medium": "fiber", "capacity_mbps": 100.0, "distance_km": 2.1},
        ),
        TopologyLink(
            id="L2",
            source="R1", target="WB1",
            status="healthy",
            latency_ms=2.0, packet_loss_pct=0.0, throughput_mbps=80.0,
            properties={"medium": "ethernet", "capacity_mbps": 1000.0},
        ),
        TopologyLink(
            id="L3",
            source="WB1", target="WB2",
            status="healthy",
            latency_ms=25.0, packet_loss_pct=0.5, throughput_mbps=35.0,
            properties={"medium": "wireless_ptp", "frequency": "5GHz", "distance_km": 3.2},
        ),
        TopologyLink(
            id="L4",
            source="WB2", target="AP1",
            status="healthy",
            latency_ms=3.0, packet_loss_pct=0.0, throughput_mbps=50.0,
            properties={"medium": "ethernet", "capacity_mbps": 1000.0},
        ),
        TopologyLink(
            id="L5",
            source="R1", target="AP2",
            status="healthy",
            latency_ms=5.0, packet_loss_pct=0.0, throughput_mbps=60.0,
            properties={"medium": "ethernet", "capacity_mbps": 1000.0},
        ),
        # ── Village 2 — Bhatpur branch ───────────────────────────────────────
        TopologyLink(
            id="L6",
            source="R1", target="WB3",
            status="healthy",
            latency_ms=2.0, packet_loss_pct=0.0, throughput_mbps=80.0,
            properties={"medium": "ethernet", "capacity_mbps": 1000.0},
        ),
        TopologyLink(
            id="L7",
            source="WB3", target="WB4",
            status="healthy",
            latency_ms=12.0, packet_loss_pct=0.2, throughput_mbps=40.0,
            properties={"medium": "wireless_ptp", "frequency": "60GHz", "distance_km": 2.8},
        ),
        TopologyLink(
            id="L8",
            source="WB4", target="R2",
            status="healthy",
            latency_ms=2.0, packet_loss_pct=0.0, throughput_mbps=38.0,
            properties={"medium": "ethernet", "capacity_mbps": 100.0},
        ),
        TopologyLink(
            id="L9",
            source="R2", target="AP3",
            status="healthy",
            latency_ms=3.0, packet_loss_pct=0.0, throughput_mbps=35.0,
            properties={"medium": "ethernet", "capacity_mbps": 100.0},
        ),
        TopologyLink(
            id="L10",
            source="R2", target="AP4",
            status="healthy",
            latency_ms=3.0, packet_loss_pct=0.0, throughput_mbps=35.0,
            properties={"medium": "ethernet", "capacity_mbps": 100.0},
        ),
        # ── Village 3 — Daulatpur branch ─────────────────────────────────────
        TopologyLink(
            id="L11",
            source="R1", target="WB5",
            status="healthy",
            latency_ms=2.0, packet_loss_pct=0.0, throughput_mbps=80.0,
            properties={"medium": "ethernet", "capacity_mbps": 1000.0},
        ),
        TopologyLink(
            id="L12",
            source="WB5", target="WB6",
            status="healthy",
            latency_ms=30.0, packet_loss_pct=0.8, throughput_mbps=28.0,
            properties={"medium": "wireless_ptp", "frequency": "5GHz", "distance_km": 4.1},
        ),
        TopologyLink(
            id="L13",
            source="WB6", target="AP5",
            status="healthy",
            latency_ms=3.0, packet_loss_pct=0.0, throughput_mbps=26.0,
            properties={"medium": "ethernet", "capacity_mbps": 100.0},
        ),
        TopologyLink(
            id="L14",
            source="WB6", target="AP6",
            status="healthy",
            latency_ms=3.0, packet_loss_pct=0.0, throughput_mbps=26.0,
            properties={"medium": "ethernet", "capacity_mbps": 100.0},
        ),
    ]


def get_default_subscribers() -> List[Subscriber]:
    """Returns 20 demo subscribers across 3 villages."""
    return [
        # ── Village 1: Rampur — AP1 (North Market) ───────────────────────────
        Subscriber(id="SUB101", display_name="Ramesh Patel — Kishan Kirana Store",
                   access_point_id="AP1", plan="Basic", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB102", display_name="Gram Panchayat e-Seva Kendra",
                   access_point_id="AP1", plan="Enterprise", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB103", display_name="Rampur Co-op Bank Branch",
                   access_point_id="AP1", plan="Enterprise", status="active",
                   payment_status="due", due_date="2026-11-01"),
        # ── Village 1: Rampur — AP2 (Panchayat Bhawan) ───────────────────────
        Subscriber(id="SUB201", display_name="Primary Health Centre Rampur",
                   access_point_id="AP2", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB202", display_name="Govt Secondary School Rampur",
                   access_point_id="AP2", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB203", display_name="Manoj CSC Digital Centre",
                   access_point_id="AP2", plan="Basic", status="active",
                   payment_status="due", due_date="2026-10-15"),
        Subscriber(id="SUB204", display_name="Rampur Ration Shop (PDS)",
                   access_point_id="AP2", plan="Basic", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        # ── Village 2: Bhatpur — AP3 (Market) ────────────────────────────────
        Subscriber(id="SUB301", display_name="Bhatpur Vegetable Mandi",
                   access_point_id="AP3", plan="Basic", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB302", display_name="Bhatpur Milk Collection Point",
                   access_point_id="AP3", plan="Basic", status="active",
                   payment_status="due", due_date="2026-11-01"),
        Subscriber(id="SUB303", display_name="Bhatpur Village Sarpanch Office",
                   access_point_id="AP3", plan="Enterprise", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        # ── Village 2: Bhatpur — AP4 (School) ────────────────────────────────
        Subscriber(id="SUB401", display_name="Bhatpur Govt Middle School",
                   access_point_id="AP4", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB402", display_name="Bhatpur Anganwadi Centre",
                   access_point_id="AP4", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB403", display_name="Bhatpur Youth Digital Library",
                   access_point_id="AP4", plan="Basic", status="active",
                   payment_status="due", due_date="2026-10-28"),
        # ── Village 3: Daulatpur — AP5 (South Market) ────────────────────────
        Subscriber(id="SUB501", display_name="Daulatpur Haat Bazaar Committee",
                   access_point_id="AP5", plan="Basic", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB502", display_name="Suresh Cold Storage & Agri",
                   access_point_id="AP5", plan="Enterprise", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB503", display_name="Daulatpur CSC e-District Point",
                   access_point_id="AP5", plan="Basic", status="active",
                   payment_status="due", due_date="2026-11-01"),
        # ── Village 3: Daulatpur — AP6 (PHC) ─────────────────────────────────
        Subscriber(id="SUB601", display_name="PHC Daulatpur — Telemedicine",
                   access_point_id="AP6", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB602", display_name="Daulatpur Sub-District Hospital",
                   access_point_id="AP6", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        # Bonus subscribers (makes it a rounder 20)
        Subscriber(id="SUB604", display_name="Daulatpur Govt ITI College",
                   access_point_id="AP6", plan="Community", status="active",
                   payment_status="paid", due_date="2026-11-15"),
        Subscriber(id="SUB504", display_name="Daulatpur Police Chowki",
                   access_point_id="AP5", plan="Enterprise", status="active",
                   payment_status="paid", due_date="2026-11-15"),
    ]


def get_default_topology() -> NetworkTopology:
    """Returns the complete default NetworkTopology object."""
    return NetworkTopology(
        nodes=get_default_nodes(),
        links=get_default_links(),
        data_source="simulated",
    )


# ── Village metadata ──────────────────────────────────────────────────────────

VILLAGE_METADATA = {
    "rampur": {
        "name": "Rampur",
        "population": 4200,
        "access_points": ["AP1", "AP2"],
        "description": "Primary hub village with water tower relay",
    },
    "bhatpur": {
        "name": "Bhatpur",
        "population": 2800,
        "access_points": ["AP3", "AP4"],
        "description": "North hamlet connected via 60GHz PtP bridge",
    },
    "daulatpur": {
        "name": "Daulatpur",
        "population": 3100,
        "access_points": ["AP5", "AP6"],
        "description": "South village connected via 5GHz long-range PtP",
    },
}


class InMemoryTopologyGraph:
    """In-memory representation of the multi-village graph topology.

    Mirrors the exact graph semantics and downstream dependency logic of Neo4j.
    Used for fast simulation without live database.
    """

    def __init__(
        self,
        nodes: Optional[List[TopologyNode]] = None,
        links: Optional[List[TopologyLink]] = None,
        subscribers: Optional[List[Subscriber]] = None,
    ) -> None:
        self.nodes: Dict[str, TopologyNode] = {
            n.id: n for n in (nodes if nodes is not None else get_default_nodes())
        }
        self.links: Dict[str, TopologyLink] = {
            lk.id: lk for lk in (links if links is not None else get_default_links())
        }
        self.subscribers: Dict[str, Subscriber] = {
            s.id: s for s in (subscribers if subscribers is not None else get_default_subscribers())
        }

    def get_downstream_access_points(self, start_node_id: str) -> List[str]:
        """Finds all access point IDs reachable downstream from start_node_id along links."""
        visited_nodes = set()
        queue = [start_node_id]
        reachable_aps = []

        while queue:
            current = queue.pop(0)
            if current in visited_nodes:
                continue
            visited_nodes.add(current)

            node = self.nodes.get(current)
            if node and node.type == "access_point":
                reachable_aps.append(current)

            for link in self.links.values():
                if link.source == current and link.target not in visited_nodes:
                    queue.append(link.target)

        return reachable_aps

    def get_affected_subscribers(
        self,
        suspected_component_id: str,
        component_type: str = "link",
    ) -> List[AffectedSubscriber]:
        """Calculates affected subscribers from the suspected component.

        Assumption: Single-path routing per segment.
        """
        target_aps: List[str] = []

        if component_type == "link" or suspected_component_id in self.links:
            link = self.links.get(suspected_component_id)
            if not link:
                return []
            target_aps = self.get_downstream_access_points(link.target)

        elif suspected_component_id in self.nodes:
            node = self.nodes.get(suspected_component_id)
            if not node:
                return []
            if node.type == "access_point":
                target_aps = [node.id]
            else:
                target_aps = self.get_downstream_access_points(node.id)

        affected = [
            AffectedSubscriber(
                id=sub.id,
                display_name=sub.display_name,
                access_point_id=sub.access_point_id,
            )
            for sub in self.subscribers.values()
            if sub.access_point_id in target_aps
        ]
        affected.sort(key=lambda s: s.id)
        return affected

    def get_village_for_ap(self, ap_id: str) -> Optional[str]:
        """Return the village name for an access point."""
        node = self.nodes.get(ap_id)
        if node:
            return node.properties.get("village")
        return None

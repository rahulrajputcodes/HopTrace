"""Tests for network geography, geographic placement, and expanded topology schemas.

Validates:
(a) All 15 nodes have lat/lon in valid coordinate ranges and inside the UP bounding box.
(b) Haversine vs distance_km within 10% for long radiating links (L1, L3, L7, L12).
(c) All intra-site links have haversine distance < 0.3 km.
(d) Minimum pairwise node distance in the network is >= 30 m.
(e) Schema backward compatibility: TopologyNode and TopologyLink validate without optional fields;
    out-of-range lat/lon is rejected.
(f) Node villages are a subset of {rampur, bhatpur, daulatpur, block_hq}; non-HQ village IDs
    equal the IDs served by /villages (from VILLAGE_METADATA); each access_point is mapped correctly.
(g) Exactly the 6 AP nodes have coverage_radius_m matching [300, 250, 280, 200, 320, 230],
    and every other node has None.
(h) GET /api/v1/topology returns the new fields for all nodes and links (null where absent).
(i) AP circles of different villages do not overlap (centre distance > sum of radii).
"""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engine.topology import VILLAGE_METADATA
from app.schemas.topology import TopologyLink, TopologyNode


# ── Helpers ──────────────────────────────────────────────────────────────────

UP_LAT_MIN = 23.8
UP_LAT_MAX = 30.5
UP_LON_MIN = 77.0
UP_LON_MAX = 84.7


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in kilometres."""
    r_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_km * c


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in metres."""
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0


# ── (a) Valid coordinates in UP bounding box ─────────────────────────────────

def test_all_15_nodes_have_valid_coordinates_in_up_bbox(client: TestClient) -> None:
    resp = client.get("/api/v1/topology")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]
    assert len(nodes) == 15

    for node in nodes:
        lat = node.get("lat")
        lon = node.get("lon")
        assert lat is not None, f"Node {node['id']} missing lat"
        assert lon is not None, f"Node {node['id']} missing lon"
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert -90.0 <= lat <= 90.0
        assert -180.0 <= lon <= 180.0
        assert UP_LAT_MIN <= lat <= UP_LAT_MAX, f"Node {node['id']} lat {lat} outside UP bbox"
        assert UP_LON_MIN <= lon <= UP_LON_MAX, f"Node {node['id']} lon {lon} outside UP bbox"


# ── (b) Haversine vs distance_km within 10% for L1, L3, L7, L12 ───────────────

def test_long_links_haversine_matches_distance_km(client: TestClient) -> None:
    resp = client.get("/api/v1/topology").json()
    node_coords: Dict[str, Tuple[float, float]] = {
        n["id"]: (n["lat"], n["lon"]) for n in resp["nodes"]
    }
    links_by_id = {l["id"]: l for l in resp["links"]}

    expected_long_links = {
        "L1": 2.1,
        "L3": 3.2,
        "L7": 2.8,
        "L12": 4.1,
    }

    for lid, target_km in expected_long_links.items():
        assert lid in links_by_id, f"Link {lid} missing from topology"
        link = links_by_id[lid]
        src_lat, src_lon = node_coords[link["source"]]
        tgt_lat, tgt_lon = node_coords[link["target"]]

        actual_km = haversine_km(src_lat, src_lon, tgt_lat, tgt_lon)
        pct_error = abs(actual_km - target_km) / target_km * 100.0

        assert pct_error <= 10.0, (
            f"Link {lid} ({link['source']}->{link['target']}) distance {actual_km:.3f} km "
            f"deviates {pct_error:.2f}% from target {target_km} km (must be <= 10%)"
        )
        assert link.get("distance_km") == target_km


# ── (c) Intra-site links < 0.3 km ────────────────────────────────────────────

def test_intra_site_links_haversine_below_300m(client: TestClient) -> None:
    resp = client.get("/api/v1/topology").json()
    node_coords: Dict[str, Tuple[float, float]] = {
        n["id"]: (n["lat"], n["lon"]) for n in resp["nodes"]
    }

    intra_site_link_ids = {"L2", "L4", "L5", "L6", "L8", "L9", "L10", "L11", "L13", "L14"}

    for link in resp["links"]:
        if link["id"] in intra_site_link_ids:
            src_lat, src_lon = node_coords[link["source"]]
            tgt_lat, tgt_lon = node_coords[link["target"]]
            dist_km = haversine_km(src_lat, src_lon, tgt_lat, tgt_lon)
            assert dist_km < 0.3, (
                f"Link {link['id']} ({link['source']}->{link['target']}) distance {dist_km:.4f} km >= 0.3 km"
            )


# ── (d) Minimum pairwise node distance >= 30 m ───────────────────────────────

def test_minimum_pairwise_node_distance_at_least_30m(client: TestClient) -> None:
    resp = client.get("/api/v1/topology").json()
    nodes = resp["nodes"]
    assert len(nodes) == 15

    min_dist_m = float("inf")
    closest_pair: Tuple[str, str] = ("", "")

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            n1 = nodes[i]
            n2 = nodes[j]
            dist_m = haversine_m(n1["lat"], n1["lon"], n2["lat"], n2["lon"])
            if dist_m < min_dist_m:
                min_dist_m = dist_m
                closest_pair = (n1["id"], n2["id"])

    assert min_dist_m >= 30.0, (
        f"Nodes {closest_pair} are too close: {min_dist_m:.2f} m (must be >= 30 m)"
    )


# ── (e) Schema validation & rejection ────────────────────────────────────────

def test_schema_backward_compatibility_and_validation() -> None:
    # 1. Valid without optional fields
    node_min = TopologyNode(
        id="N1",
        type="router",
        label="Router 1",
        status="healthy",
    )
    assert node_min.lat is None
    assert node_min.lon is None
    assert node_min.village is None
    assert node_min.coverage_radius_m is None

    link_min = TopologyLink(
        id="L1",
        source="N1",
        target="N2",
        status="healthy",
    )
    assert link_min.distance_km is None
    assert link_min.medium is None
    assert link_min.frequency is None

    # 2. Valid with optional fields
    node_full = TopologyNode(
        id="AP1",
        type="access_point",
        label="AP 1",
        status="healthy",
        lat=27.20000,
        lon=80.60000,
        village="rampur",
        coverage_radius_m=300,
    )
    assert node_full.lat == 27.20000
    assert node_full.coverage_radius_m == 300

    link_full = TopologyLink(
        id="L3",
        source="WB1",
        target="WB2",
        status="healthy",
        distance_km=3.2,
        medium="wireless_ptp",
        frequency="5GHz",
    )
    assert link_full.distance_km == 3.2
    assert link_full.frequency == "5GHz"

    # 3. Invalid lat/lon rejected
    with pytest.raises(ValidationError):
        TopologyNode(id="X", type="router", label="X", status="healthy", lat=95.0)

    with pytest.raises(ValidationError):
        TopologyNode(id="X", type="router", label="X", status="healthy", lat=-95.0)

    with pytest.raises(ValidationError):
        TopologyNode(id="X", type="router", label="X", status="healthy", lon=185.0)

    with pytest.raises(ValidationError):
        TopologyNode(id="X", type="router", label="X", status="healthy", lon=-185.0)

    # 4. Invalid coverage_radius_m rejected (must be > 0)
    with pytest.raises(ValidationError):
        TopologyNode(id="X", type="access_point", label="X", status="healthy", coverage_radius_m=0)

    with pytest.raises(ValidationError):
        TopologyNode(id="X", type="access_point", label="X", status="healthy", coverage_radius_m=-10)


# ── (f) Node villages and metadata consistency ────────────────────────────────

def test_node_villages_and_metadata_consistency(client: TestClient) -> None:
    resp = client.get("/api/v1/topology").json()
    nodes = resp["nodes"]

    allowed_villages = {"rampur", "bhatpur", "daulatpur", "block_hq"}
    for node in nodes:
        assert node["village"] in allowed_villages, f"Unexpected village {node['village']} on {node['id']}"

    # Non-HQ village IDs must match /villages response and VILLAGE_METADATA
    villages_resp = client.get("/api/v1/villages").json()["villages"]
    api_village_ids = {v["village_id"] for v in villages_resp}
    metadata_village_ids = set(VILLAGE_METADATA.keys())

    assert api_village_ids == metadata_village_ids
    assert api_village_ids == {"rampur", "bhatpur", "daulatpur"}

    nodes_by_id = {n["id"]: n for n in nodes}
    for vid, meta in VILLAGE_METADATA.items():
        for ap_id in meta["access_points"]:
            assert ap_id in nodes_by_id, f"AP {ap_id} from {vid} not in topology"
            ap_node = nodes_by_id[ap_id]
            assert ap_node["type"] == "access_point"
            assert ap_node["village"] == vid, f"AP {ap_id} village {ap_node['village']} != {vid}"


# ── (g) Coverage radius present only on 6 APs ─────────────────────────────────

def test_coverage_radius_present_only_on_access_points(client: TestClient) -> None:
    resp = client.get("/api/v1/topology").json()
    nodes = resp["nodes"]

    expected_ap_radii = {
        "AP1": 300,
        "AP2": 250,
        "AP3": 280,
        "AP4": 200,
        "AP5": 320,
        "AP6": 230,
    }

    for node in nodes:
        nid = node["id"]
        if nid in expected_ap_radii:
            assert node["type"] == "access_point"
            assert node["coverage_radius_m"] == expected_ap_radii[nid], (
                f"{nid} coverage_radius_m {node['coverage_radius_m']} != {expected_ap_radii[nid]}"
            )
        else:
            assert node["coverage_radius_m"] is None, (
                f"Non-AP node {nid} unexpectedly has coverage_radius_m={node['coverage_radius_m']}"
            )


# ── (h) GET /api/v1/topology returns new fields ───────────────────────────────

def test_get_topology_api_returns_geography_fields(client: TestClient) -> None:
    resp = client.get("/api/v1/topology")
    assert resp.status_code == 200
    data = resp.json()

    # All nodes must have lat, lon, village
    for node in data["nodes"]:
        assert "lat" in node and isinstance(node["lat"], float)
        assert "lon" in node and isinstance(node["lon"], float)
        assert "village" in node and isinstance(node["village"], str)
        assert "coverage_radius_m" in node

    links_by_id = {l["id"]: l for l in data["links"]}

    # L1 (fiber backhaul)
    l1 = links_by_id["L1"]
    assert l1["distance_km"] == 2.1
    assert l1["medium"] == "fiber"
    assert l1["frequency"] is None

    # L3 (wireless PtP)
    l3 = links_by_id["L3"]
    assert l3["distance_km"] == 3.2
    assert l3["medium"] == "wireless_ptp"
    assert l3["frequency"] == "5GHz"

    # L7 (wireless PtP 60GHz)
    l7 = links_by_id["L7"]
    assert l7["distance_km"] == 2.8
    assert l7["medium"] == "wireless_ptp"
    assert l7["frequency"] == "60GHz"

    # L12 (wireless PtP 5GHz)
    l12 = links_by_id["L12"]
    assert l12["distance_km"] == 4.1
    assert l12["medium"] == "wireless_ptp"
    assert l12["frequency"] == "5GHz"

    # Short wired links have medium="ethernet", distance_km=null, frequency=null
    l2 = links_by_id["L2"]
    assert l2["medium"] == "ethernet"
    assert l2["distance_km"] is None
    assert l2["frequency"] is None


# ── (i) Cross-village AP circles do not overlap ──────────────────────────────

def test_cross_village_ap_circles_do_not_overlap(client: TestClient) -> None:
    resp = client.get("/api/v1/topology").json()
    ap_nodes = [n for n in resp["nodes"] if n["type"] == "access_point"]
    assert len(ap_nodes) == 6

    for i in range(len(ap_nodes)):
        for j in range(i + 1, len(ap_nodes)):
            ap1 = ap_nodes[i]
            ap2 = ap_nodes[j]
            # Check only across different villages
            if ap1["village"] != ap2["village"]:
                centre_dist_m = haversine_m(ap1["lat"], ap1["lon"], ap2["lat"], ap2["lon"])
                sum_radii_m = ap1["coverage_radius_m"] + ap2["coverage_radius_m"]
                assert centre_dist_m > sum_radii_m, (
                    f"AP circle overlap between {ap1['id']} ({ap1['village']}) and {ap2['id']} ({ap2['village']}): "
                    f"center distance {centre_dist_m:.1f} m <= sum of radii {sum_radii_m} m"
                )

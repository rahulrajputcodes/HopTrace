"""Graph store implementations for HopTrace.

Includes:
1. Neo4jGraphStore: Parameterized Cypher queries managing graph persistence
   and downstream subscriber dependency queries in Neo4j (including Neo4j Aura).
2. InMemoryGraphStore: High-fidelity in-memory graph store for fast unit
   testing without live database dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .models import (
    AffectedSubscriber,
    AffectedSubscribersResponse,
    NetworkTopology,
    TopologyLink,
    TopologyNode,
    Subscriber,
)
from .neo4j_client import Neo4jClient, get_neo4j_client
from .topology import (
    InMemoryTopologyGraph,
    get_default_links,
    get_default_nodes,
    get_default_subscribers,
    get_default_topology,
)


class Neo4jGraphStore:
    """Manages topology and dependency queries in Neo4j using parameterized Cypher."""

    def __init__(self, client: Optional[Neo4jClient] = None) -> None:
        self.client = client or get_neo4j_client()

    def create_constraints(self) -> None:
        """Idempotently creates unique constraints for Device and Subscriber nodes."""
        c1 = (
            "CREATE CONSTRAINT device_id_unique IF NOT EXISTS "
            "FOR (d:Device) REQUIRE d.id IS UNIQUE"
        )
        c2 = (
            "CREATE CONSTRAINT subscriber_id_unique IF NOT EXISTS "
            "FOR (s:Subscriber) REQUIRE s.id IS UNIQUE"
        )
        try:
            self.client.execute_write(c1)
            self.client.execute_write(c2)
        except Exception:
            # Fallback gracefully if permissions or older Cypher syntax differ
            pass

    def seed_topology(
        self,
        nodes: Optional[List[TopologyNode]] = None,
        links: Optional[List[TopologyLink]] = None,
        subscribers: Optional[List[Subscriber]] = None,
    ) -> Dict[str, Any]:
        """Idempotently seeds nodes, links, and subscribers into Neo4j.

        Running this operation multiple times will NOT duplicate nodes or relationships.
        """
        self.create_constraints()

        node_list = nodes if nodes is not None else get_default_nodes()
        link_list = links if links is not None else get_default_links()
        sub_list = subscribers if subscribers is not None else get_default_subscribers()

        # 1. Upsert Device Nodes
        device_params = [
            {
                "id": n.id,
                "label": n.label,
                "type": n.type,
                "status": n.status,
            }
            for n in node_list
        ]
        seed_devices_cypher = """
        UNWIND $devices AS dev
        MERGE (d:Device {id: dev.id})
        SET d.label = dev.label,
            d.type = dev.type,
            d.status = dev.status
        FOREACH (_ IN CASE WHEN dev.type = 'gateway' THEN [1] ELSE [] END | SET d:Gateway)
        FOREACH (_ IN CASE WHEN dev.type = 'router' THEN [1] ELSE [] END | SET d:Router)
        FOREACH (_ IN CASE WHEN dev.type = 'wireless_bridge' THEN [1] ELSE [] END | SET d:WirelessBridge)
        FOREACH (_ IN CASE WHEN dev.type = 'access_point' THEN [1] ELSE [] END | SET d:AccessPoint)
        RETURN count(d) AS seeded_devices
        """
        self.client.execute_write(seed_devices_cypher, {"devices": device_params})

        # 2. Upsert Subscribers
        sub_params = [
            {
                "id": s.id,
                "display_name": s.display_name,
                "access_point_id": s.access_point_id,
                "plan": s.plan,
                "status": s.status,
                "payment_status": s.payment_status,
                "due_date": s.due_date,
            }
            for s in sub_list
        ]
        seed_subs_cypher = """
        UNWIND $subscribers AS sub
        MERGE (s:Subscriber {id: sub.id})
        SET s.display_name = sub.display_name,
            s.access_point_id = sub.access_point_id,
            s.plan = sub.plan,
            s.status = sub.status,
            s.payment_status = sub.payment_status,
            s.due_date = sub.due_date
        RETURN count(s) AS seeded_subscribers
        """
        self.client.execute_write(seed_subs_cypher, {"subscribers": sub_params})

        # 3. Upsert Links between devices
        link_params = [
            {
                "id": l.id,
                "source": l.source,
                "target": l.target,
                "status": l.status,
                "latency_ms": l.latency_ms,
                "packet_loss_pct": l.packet_loss_pct,
                "throughput_mbps": l.throughput_mbps,
            }
            for l in link_list
        ]
        seed_links_cypher = """
        UNWIND $links AS lk
        MATCH (src:Device {id: lk.source})
        MATCH (tgt:Device {id: lk.target})
        MERGE (src)-[r:LINK {id: lk.id}]->(tgt)
        SET r.status = lk.status,
            r.latency_ms = lk.latency_ms,
            r.packet_loss_pct = lk.packet_loss_pct,
            r.throughput_mbps = lk.throughput_mbps
        RETURN count(r) AS seeded_links
        """
        self.client.execute_write(seed_links_cypher, {"links": link_params})

        # 4. Upsert SERVES relationships from AccessPoints to Subscribers
        seed_serves_cypher = """
        UNWIND $subscribers AS sub
        MATCH (ap:Device {id: sub.access_point_id})
        MATCH (s:Subscriber {id: sub.id})
        MERGE (ap)-[r:SERVES]->(s)
        RETURN count(r) AS seeded_serves
        """
        self.client.execute_write(seed_serves_cypher, {"subscribers": sub_params})

        return {
            "status": "seeded",
            "nodes_count": len(node_list),
            "links_count": len(link_list),
            "subscribers_count": len(sub_list),
        }

    def get_topology(self, prefix: Optional[str] = None) -> NetworkTopology:
        """Retrieves topology from Neo4j, optionally filtered by ID prefix for test isolation."""
        if prefix:
            nodes_cypher = """
            MATCH (d:Device)
            WHERE d.id STARTS WITH $prefix
            RETURN d.id AS id, d.type AS type, d.label AS label, d.status AS status
            ORDER BY d.id
            """
            links_cypher = """
            MATCH (src:Device)-[r:LINK]->(tgt:Device)
            WHERE r.id STARTS WITH $prefix
            RETURN r.id AS id, src.id AS source, tgt.id AS target, r.status AS status,
                   r.latency_ms AS latency_ms, r.packet_loss_pct AS packet_loss_pct,
                   r.throughput_mbps AS throughput_mbps
            ORDER BY r.id
            """
            node_records = self.client.execute_query(nodes_cypher, {"prefix": prefix})
            link_records = self.client.execute_query(links_cypher, {"prefix": prefix})
        else:
            nodes_cypher = """
            MATCH (d:Device)
            RETURN d.id AS id, d.type AS type, d.label AS label, d.status AS status
            ORDER BY d.id
            """
            links_cypher = """
            MATCH (src:Device)-[r:LINK]->(tgt:Device)
            RETURN r.id AS id, src.id AS source, tgt.id AS target, r.status AS status,
                   r.latency_ms AS latency_ms, r.packet_loss_pct AS packet_loss_pct,
                   r.throughput_mbps AS throughput_mbps
            ORDER BY r.id
            """
            node_records = self.client.execute_query(nodes_cypher)
            link_records = self.client.execute_query(links_cypher)

        nodes = [
            TopologyNode(
                id=rec["id"],
                type=rec.get("type", "router"),
                label=rec.get("label", rec["id"]),
                status=rec.get("status", "healthy"),
            )
            for rec in node_records
        ]
        links = [
            TopologyLink(
                id=rec["id"],
                source=rec["source"],
                target=rec["target"],
                status=rec.get("status", "healthy"),
                latency_ms=rec.get("latency_ms"),
                packet_loss_pct=rec.get("packet_loss_pct"),
                throughput_mbps=rec.get("throughput_mbps"),
            )
            for rec in link_records
        ]

        return NetworkTopology(nodes=nodes, links=links, data_source="simulated")

    def get_affected_subscribers(
        self,
        suspected_component_id: str,
        component_type: str = "link",
    ) -> AffectedSubscribersResponse:
        """Traces downstream subscriber dependencies from the suspected link or node.

        Assumption:
        Single-path routing: Subscribers do not have alternate redundant paths
        unless explicitly represented in the graph.
        """
        if component_type == "link":
            cypher = """
            MATCH (src:Device)-[rel:LINK {id: $component_id}]->(tgt:Device)
            MATCH (tgt)-[:LINK*0..]->(ap:Device)-[:SERVES]->(sub:Subscriber)
            WHERE ap.type = 'access_point'
            RETURN DISTINCT sub.id AS id, sub.display_name AS display_name, ap.id AS access_point_id
            ORDER BY sub.id
            """
        else:
            cypher = """
            MATCH (n:Device {id: $component_id})-[:LINK*0..]->(ap:Device)-[:SERVES]->(sub:Subscriber)
            WHERE ap.type = 'access_point'
            RETURN DISTINCT sub.id AS id, sub.display_name AS display_name, ap.id AS access_point_id
            ORDER BY sub.id
            """

        records = self.client.execute_query(cypher, {"component_id": suspected_component_id})
        subs = [
            AffectedSubscriber(
                id=r["id"],
                display_name=r["display_name"],
                access_point_id=r["access_point_id"],
            )
            for r in records
        ]
        return AffectedSubscribersResponse(count=len(subs), subscribers=subs)

    def delete_isolated_test_data(self, prefix: str = "TEST_") -> None:
        """Removes test nodes and relationships starting with prefix without touching demo topology."""
        if not prefix:
            raise ValueError("Prefix cannot be empty for safe test data cleanup.")

        delete_subs = "MATCH (s:Subscriber) WHERE s.id STARTS WITH $prefix DETACH DELETE s"
        delete_devices = "MATCH (d:Device) WHERE d.id STARTS WITH $prefix DETACH DELETE d"
        try:
            self.client.execute_write(delete_subs, {"prefix": prefix})
            self.client.execute_write(delete_devices, {"prefix": prefix})
        except Exception:
            pass


class InMemoryGraphStore:
    """In-memory graph store for pure unit testing without a live Neo4j database."""

    def __init__(self) -> None:
        self.graph = InMemoryTopologyGraph()
        self.seed_count: int = 0

    def seed_topology(
        self,
        nodes: Optional[List[TopologyNode]] = None,
        links: Optional[List[TopologyLink]] = None,
        subscribers: Optional[List[Subscriber]] = None,
    ) -> Dict[str, Any]:
        """Idempotently seeds nodes, links, and subscribers."""
        node_list = nodes if nodes is not None else get_default_nodes()
        link_list = links if links is not None else get_default_links()
        sub_list = subscribers if subscribers is not None else get_default_subscribers()

        for n in node_list:
            self.graph.nodes[n.id] = n
        for l in link_list:
            self.graph.links[l.id] = l
        for s in sub_list:
            self.graph.subscribers[s.id] = s

        self.seed_count += 1
        return {
            "status": "seeded",
            "nodes_count": len(self.graph.nodes),
            "links_count": len(self.graph.links),
            "subscribers_count": len(self.graph.subscribers),
        }

    def get_topology(self, prefix: Optional[str] = None) -> NetworkTopology:
        """Returns the current network topology, optionally filtered by prefix."""
        nodes = list(self.graph.nodes.values())
        links = list(self.graph.links.values())
        if prefix:
            nodes = [n for n in nodes if n.id.startswith(prefix)]
            links = [l for l in links if l.id.startswith(prefix)]

        return NetworkTopology(
            nodes=nodes,
            links=links,
            data_source="simulated",
        )

    def get_affected_subscribers(
        self,
        suspected_component_id: str,
        component_type: str = "link",
    ) -> AffectedSubscribersResponse:
        """Returns affected subscribers based on the graph topology."""
        subs = self.graph.get_affected_subscribers(
            suspected_component_id=suspected_component_id,
            component_type=component_type,
        )
        return AffectedSubscribersResponse(count=len(subs), subscribers=subs)

    def delete_isolated_test_data(self, prefix: str = "TEST_") -> None:
        """Removes test nodes and subscribers starting with prefix."""
        if not prefix:
            raise ValueError("Prefix cannot be empty for safe test data cleanup.")
        self.graph.nodes = {k: v for k, v in self.graph.nodes.items() if not k.startswith(prefix)}
        self.graph.links = {k: v for k, v in self.graph.links.items() if not k.startswith(prefix)}
        self.graph.subscribers = {
            k: v for k, v in self.graph.subscribers.items() if not k.startswith(prefix)
        }

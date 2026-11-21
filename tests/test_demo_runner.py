"""Unit test for the hackathon live demo runner script."""

from unittest.mock import MagicMock, patch
import pytest

from scripts.run_demo import make_probe_payload, run_demo


def test_make_probe_payload_structure():
    """make_probe_payload produces payload conforming to PathProbeRequest schema."""
    # 1. Healthy payload
    p_healthy = make_probe_payload()
    assert len(p_healthy["results"]) == 14
    assert all(r["reachable"] is True for r in p_healthy["results"])

    # 2. Outage payload at WB3 and descendants
    p_outage = make_probe_payload(unreachable=["WB3", "WB4", "R2", "AP3", "AP4"])
    unreach = [r["node_id"] for r in p_outage["results"] if not r["reachable"]]
    assert set(unreach) == {"WB3", "WB4", "R2", "AP3", "AP4"}

    # 3. Degraded payload
    p_deg = make_probe_payload(degraded={"WB2": 65.0})
    wb2 = next(r for r in p_deg["results"] if r["node_id"] == "WB2")
    assert wb2["reachable"] is True
    assert wb2["latency_ms"] == 65.0


def test_run_demo_executes_all_phases_in_auto_mode():
    """run_demo executes phases 1 through 5 successfully with mocked backend responses."""
    def fake_api_request(url, method="GET", data=None, timeout=6.0):
        if "/api/v1/health" in url:
            return {"status": "ok"}
        if "/api/v1/probes/path" in url:
            if data and any(not r["reachable"] for r in data.get("results", [])):
                return {
                    "status": "ok",
                    "derived_links": 14,
                    "first_failed_nodes": ["WB3"],
                    "incident_id": "inc-demo-123",
                }
            return {
                "status": "ok",
                "derived_links": 14,
                "first_failed_nodes": [],
                "incident_id": None,
            }
        if "/api/v1/topology/sla" in url:
            return {
                "window_hours": 24,
                "villages": {
                    "rampur": {"village_name": "Rampur", "uptime_pct": 100.0, "status": "healthy"},
                    "bhatpur": {"village_name": "Bhatpur", "uptime_pct": 98.5, "status": "degraded"},
                    "daulatpur": {"village_name": "Daulatpur", "uptime_pct": 100.0, "status": "healthy"},
                },
            }
        if "/api/v1/incidents/inc-demo-123/affected-subscribers" in url:
            return {"count": 6, "subscribers": []}
        if "/api/v1/incidents/inc-demo-123" in url or "/api/v1/incidents/latest" in url:
            return {
                "id": "inc-demo-123",
                "status": "closed",
                "suspected_component_id": "L6",
                "cause": "hardware_power_outage",
                "cause_confidence": 0.82,
                "summary": "Outage on L6",
                "resolved_at": "2026-11-19T16:00:00Z",
                "duration_seconds": 120,
            }
        if "/api/v1/agent/heartbeat" in url:
            return {"status": "ok"}
        if "/api/v1/agent/status" in url:
            return {"agents": [{"agent_id": "agent-bhatpur-1", "buffered_count": 8, "status": "online"}]}
        return {}

    with patch("scripts.run_demo.api_request", side_effect=fake_api_request):
        with patch("time.sleep", return_value=None):
            # Run in auto mode (non-interactive)
            run_demo("http://localhost:8000", interactive=False)

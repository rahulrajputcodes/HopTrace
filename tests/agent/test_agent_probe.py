"""Unit tests for HopTrace Agent (stdlib-only) path probing."""

import json
from unittest.mock import MagicMock, patch
import pytest

from agent.hoptrace_agent import (
    collect_path_probes,
    load_config,
    probe_node,
    send_path_probes,
)


def test_agent_probe_node_success():
    """probe_node maps ping_target return values to probe result dict."""
    with patch("agent.hoptrace_agent.ping_target") as mock_ping:
        mock_ping.return_value = (True, 12.4, 0.0)
        res = probe_node({"node_id": "R1", "host": "192.0.2.1"}, count=3, timeout_sec=2)

        assert res["node_id"] == "R1"
        assert res["reachable"] is True
        assert res["latency_ms"] == 12.4
        assert res["packet_loss_pct"] == 0.0


def test_agent_probe_node_unreachable():
    """probe_node handles unreachable host."""
    with patch("agent.hoptrace_agent.ping_target") as mock_ping:
        mock_ping.return_value = (False, None, 100.0)
        res = probe_node({"node_id": "WB3", "host": "192.0.2.6"}, count=3, timeout_sec=2)

        assert res["node_id"] == "WB3"
        assert res["reachable"] is False
        assert res["latency_ms"] is None
        assert res["packet_loss_pct"] == 100.0


def test_agent_collect_path_probes_concurrent():
    """collect_path_probes probes all nodes using ThreadPoolExecutor."""
    nodes = [
        {"node_id": "R1", "host": "192.0.2.1"},
        {"node_id": "WB1", "host": "192.0.2.2"},
        {"node_id": "WB3", "host": "192.0.2.6"},
    ]
    with patch("agent.hoptrace_agent.ping_target") as mock_ping:
        mock_ping.return_value = (True, 10.0, 0.0)
        results = collect_path_probes(nodes, count=1, timeout_sec=1, max_workers=4)

        assert len(results) == 3
        node_ids = {r["node_id"] for r in results}
        assert node_ids == {"R1", "WB1", "WB3"}


def test_agent_send_path_probes_request_format():
    """send_path_probes delivers JSON with User-Agent and X-API-Key."""
    payload = {
        "agent_id": "agent-rampur-1",
        "vantage_node_id": "GW1",
        "results": [{"node_id": "R1", "reachable": True, "latency_ms": 12.4, "packet_loss_pct": 0.0}],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"status": "ok", "derived_links": 1}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = send_path_probes("http://localhost:8000", payload, api_key="secret-key")

        assert res["status"] == "ok"
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:8000/api/v1/probes/path"
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("X-api-key") == "secret-key"

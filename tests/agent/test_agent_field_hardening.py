"""Unit tests for agent field hardening: --check diagnostic mode, jitter extraction, and backoff."""

import io
from unittest.mock import MagicMock, patch
import pytest

from agent.hoptrace_agent import (
    ping_target,
    probe_node,
    run_diagnostic_check,
)


def test_ping_target_parses_unix_jitter():
    """ping_target parses standard deviation / mdev jitter when include_jitter is True."""
    mock_stdout = (
        "PING 192.0.2.1 (192.0.2.1) 56(84) bytes of data.\n"
        "64 bytes from 192.0.2.1: icmp_seq=1 ttl=64 time=12.4 ms\n"
        "64 bytes from 192.0.2.1: icmp_seq=2 ttl=64 time=14.8 ms\n"
        "\n"
        "--- 192.0.2.1 ping statistics ---\n"
        "2 packets transmitted, 2 received, 0% packet loss, time 1002ms\n"
        "rtt min/avg/max/mdev = 12.400/13.600/14.800/1.200 ms\n"
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = mock_stdout

    with patch("subprocess.run", return_value=mock_proc):
        # 1. Backward compatible call without include_jitter
        res3 = ping_target("192.0.2.1", count=2, timeout_sec=1)
        assert len(res3) == 3
        conn_ok, lat, loss = res3
        assert conn_ok is True
        assert lat == 13.6
        assert loss == 0.0

        # 2. Call with include_jitter=True
        res4 = ping_target("192.0.2.1", count=2, timeout_sec=1, include_jitter=True)
        assert len(res4) == 4
        conn_ok, lat, loss, jitter = res4
        assert conn_ok is True
        assert lat == 13.6
        assert loss == 0.0
        assert jitter == 1.2


def test_probe_node_includes_jitter_when_present():
    """probe_node adds jitter_ms to probe dictionary if detected."""
    with patch("agent.hoptrace_agent.ping_target") as mock_ping:
        mock_ping.return_value = (True, 15.2, 0.0, 1.8)
        res = probe_node({"node_id": "WB1", "host": "192.0.2.2"}, count=2, timeout_sec=1)
        assert res["node_id"] == "WB1"
        assert res["reachable"] is True
        assert res["latency_ms"] == 15.2
        assert res["packet_loss_pct"] == 0.0
        assert res["jitter_ms"] == 1.8


def test_run_diagnostic_check_all_healthy(capsys):
    """run_diagnostic_check returns 0 when API is 200 OK and all nodes reachable."""
    config = {
        "api_base": "http://localhost:8000",
        "agent_id": "test-agent",
        "site_id": "rampur",
        "vantage_node_id": "GW1",
        "buffer_path": "agent/buffer.jsonl",
        "nodes": [
            {"node_id": "R1", "host": "192.0.2.1"},
            {"node_id": "WB1", "host": "192.0.2.2"},
        ],
    }

    mock_api_resp = MagicMock()
    mock_api_resp.status = 200
    mock_api_resp.__enter__.return_value = mock_api_resp

    with patch("urllib.request.urlopen", return_value=mock_api_resp):
        with patch("agent.hoptrace_agent.ping_target", return_value=(True, 10.0, 0.0)):
            code = run_diagnostic_check(config)

    assert code == 0
    captured = capsys.readouterr().out
    assert "ONLINE (200 OK)" in captured
    assert "ALL SYSTEMS OPERATIONAL" in captured


def test_run_diagnostic_check_unreachable_node(capsys):
    """run_diagnostic_check returns 1 when nodes or API fail."""
    config = {
        "api_base": "http://localhost:8000",
        "nodes": [{"node_id": "WB3", "host": "192.0.2.6"}],
    }

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        with patch("agent.hoptrace_agent.ping_target", return_value=(False, None, 100.0)):
            code = run_diagnostic_check(config)

    assert code == 1
    captured = capsys.readouterr().out
    assert "OFFLINE / UNREACHABLE" in captured
    assert "WARNINGS DETECTED" in captured

"""Unit tests for HopTrace Agent store-and-forward local buffering and heartbeats."""

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from agent.hoptrace_agent import (
    append_to_buffer,
    count_buffered,
    flush_buffer,
    send_heartbeat,
)


def test_buffer_append_and_count(tmp_path):
    """append_to_buffer creates file and increments buffered count."""
    buf_file = str(tmp_path / "buffer.jsonl")

    assert count_buffered(buf_file) == 0

    batch1 = {"type": "path_probes", "payload": {"vantage_node_id": "GW1", "results": []}}
    c1 = append_to_buffer(buf_file, batch1)
    assert c1 == 1
    assert count_buffered(buf_file) == 1

    batch2 = {"type": "path_probes", "payload": {"vantage_node_id": "GW1", "results": [{"node_id": "R1"}]}}
    c2 = append_to_buffer(buf_file, batch2)
    assert c2 == 2
    assert count_buffered(buf_file) == 2


def test_buffer_cap_drops_oldest(tmp_path):
    """When buffer exceeds max_buffer_size, oldest items are dropped."""
    buf_file = str(tmp_path / "buffer.jsonl")

    for i in range(10):
        append_to_buffer(buf_file, {"batch_num": i}, max_buffer_size=5)

    assert count_buffered(buf_file) == 5

    with open(buf_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) == 5
    # Should contain items 5 through 9 (oldest 0..4 dropped)
    assert [item["batch_num"] for item in lines] == [5, 6, 7, 8, 9]


def test_buffer_flush_oldest_first(tmp_path):
    """flush_buffer sends items in FIFO order and truncates buffer."""
    buf_file = str(tmp_path / "buffer.jsonl")

    for i in range(5):
        append_to_buffer(buf_file, {"type": "path_probes", "payload": {"seq": i}})

    assert count_buffered(buf_file) == 5

    flushed_items = []

    def fake_send(api_base, payload, api_key=None):
        flushed_items.append(payload)
        return {"status": "ok"}

    with patch("agent.hoptrace_agent.send_path_probes", side_effect=fake_send):
        flushed_count = flush_buffer("http://localhost:8000", buf_file, max_flush=3)

    assert flushed_count == 3
    assert len(flushed_items) == 3
    assert [item["seq"] for item in flushed_items] == [0, 1, 2]
    assert count_buffered(buf_file) == 2

    # Flush remaining
    with patch("agent.hoptrace_agent.send_path_probes", side_effect=fake_send):
        flushed_remaining = flush_buffer("http://localhost:8000", buf_file, max_flush=3)

    assert flushed_remaining == 2
    assert [item["seq"] for item in flushed_items] == [0, 1, 2, 3, 4]
    assert count_buffered(buf_file) == 0


def test_buffer_flush_skips_corrupt_line(tmp_path):
    """Corrupt lines in buffer are skipped without crashing flush."""
    buf_file = str(tmp_path / "buffer.jsonl")

    with open(buf_file, "w", encoding="utf-8") as f:
        f.write("{bad-json-line}\n")
        f.write(json.dumps({"type": "path_probes", "payload": {"seq": 1}}) + "\n")

    sent = []
    with patch("agent.hoptrace_agent.send_path_probes", side_effect=lambda u, p, api_key=None: sent.append(p)):
        flushed = flush_buffer("http://localhost:8000", buf_file, max_flush=5)

    assert flushed == 1
    assert len(sent) == 1
    assert sent[0]["seq"] == 1
    assert count_buffered(buf_file) == 0


def test_buffer_flush_stops_on_send_failure(tmp_path):
    """When a network error occurs during flush, remaining items stay in buffer."""
    buf_file = str(tmp_path / "buffer.jsonl")

    for i in range(4):
        append_to_buffer(buf_file, {"type": "path_probes", "payload": {"seq": i}})

    attempts = []

    def mock_send(api_base, payload, api_key=None):
        attempts.append(payload["seq"])
        if payload["seq"] == 1:
            raise ConnectionResetError("Connection dropped")
        return {"status": "ok"}

    with patch("agent.hoptrace_agent.send_path_probes", side_effect=mock_send):
        flushed = flush_buffer("http://localhost:8000", buf_file, max_flush=4)

    assert flushed == 1
    assert attempts == [0, 1]
    # Items 1, 2, 3 must still be preserved in buffer!
    assert count_buffered(buf_file) == 3

    with open(buf_file, "r", encoding="utf-8") as f:
        remaining = [json.loads(line)["payload"]["seq"] for line in f if line.strip()]
    assert remaining == [1, 2, 3]


def test_send_heartbeat_success():
    """send_heartbeat formats request body and headers correctly."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"status": "ok", "agent_id": "agent-rampur-1"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        res = send_heartbeat(
            api_base="http://localhost:8000",
            agent_id="agent-rampur-1",
            site_id="rampur",
            buffered_count=12,
            version="2.1",
            api_key="my-key",
        )

        assert res is not None
        assert res["status"] == "ok"
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:8000/api/v1/agent/heartbeat"
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("X-api-key") == "my-key"

        data = json.loads(req.data.decode("utf-8"))
        assert data["agent_id"] == "agent-rampur-1"
        assert data["site_id"] == "rampur"
        assert data["buffered_count"] == 12
        assert data["version"] == "2.1"
        assert "timestamp" in data


def test_send_heartbeat_non_fatal_on_failure():
    """send_heartbeat catches network exceptions and returns None without raising."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Server unreachable")):
        res = send_heartbeat(
            api_base="http://localhost:8000",
            agent_id="agent-rampur-1",
            site_id="rampur",
            buffered_count=0,
        )
        assert res is None

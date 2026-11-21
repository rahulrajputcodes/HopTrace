#!/usr/bin/env python3
"""HopTrace Standalone Telemetry Collector Agent.

Lightweight, zero-dependency monitoring daemon that measures network latency,
packet loss, reachability, and jitter across physical or virtual targets and nodes.
Ingests observed metrics via:
  - POST /api/v1/probes/path (hop-by-hop node path probes, v2.1)
  - POST /api/v1/measurements/ingest (legacy direct link telemetry)
  - POST /api/v1/agent/heartbeat (heartbeat & buffer status)

Store-and-forward resilience & field-hardening:
  - When backend is unreachable, batches are buffered to local JSONL storage.
  - When connection recovers, buffer drains oldest-first in batches.
  - Exponential backoff on persistent connection failures.
  - Graceful signal handling (SIGINT/SIGTERM) with zero orphan temp files.
  - Pre-flight field diagnostic mode (--check) for rural technician verification.

Uses exclusively the Python Standard Library (no pip dependencies required).
Compatible with Windows, Linux, and macOS.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def ping_target(
    host: str,
    count: int = 3,
    timeout_sec: int = 2,
    include_jitter: bool = False,
) -> Tuple[Any, ...]:
    """Pings a target host and returns (connectivity_ok, latency_ms, packet_loss_pct, [jitter_ms]).

    Standard library subprocess implementation for Windows and POSIX systems.
    """
    is_win = platform.system().lower() == "windows"
    if is_win:
        # -n count, -w timeout_in_milliseconds
        cmd = ["ping", "-n", str(count), "-w", str(int(timeout_sec * 1000)), host]
    else:
        # -c count, -W timeout_in_seconds
        cmd = ["ping", "-c", str(count), "-W", str(int(timeout_sec)), host]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=float(timeout_sec * count + 5),
        )
        stdout = proc.stdout
    except Exception:
        if include_jitter:
            return False, None, 100.0, None
        return False, None, 100.0

    # Parse packet loss
    loss_pct: Optional[float] = None
    win_loss = re.search(r"\((\d+(?:\.\d+)?)%\s*loss\)", stdout, re.IGNORECASE)
    unix_loss = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", stdout, re.IGNORECASE)

    if win_loss:
        loss_pct = float(win_loss.group(1))
    elif unix_loss:
        loss_pct = float(unix_loss.group(1))

    # Parse average latency
    latency_ms: Optional[float] = None
    win_avg = re.search(r"Average\s*=\s*(\d+(?:\.\d+)?)\s*ms", stdout, re.IGNORECASE)
    unix_avg = re.search(r"min/avg/max/(?:mdev|stddev)\s*=\s*[\d\.]+/([\d\.]+)/", stdout, re.IGNORECASE)

    if win_avg:
        latency_ms = float(win_avg.group(1))
    elif unix_avg:
        latency_ms = float(unix_avg.group(1))

    # Parse jitter (standard deviation / mdev)
    jitter_ms: Optional[float] = None
    unix_jitter = re.search(
        r"min/avg/max/(?:mdev|stddev)\s*=\s*[\d\.]+/[\d\.]+/[\d\.]+/([\d\.]+)",
        stdout,
        re.IGNORECASE,
    )
    if unix_jitter:
        jitter_ms = float(unix_jitter.group(1))

    # Connectivity evaluation
    if loss_pct is not None and loss_pct >= 100.0:
        if include_jitter:
            return False, None, 100.0, None
        return False, None, 100.0

    if proc.returncode == 0:
        connectivity_ok = True
        if loss_pct is None:
            loss_pct = 0.0
    else:
        connectivity_ok = bool(latency_ms is not None or (loss_pct is not None and loss_pct < 100.0))
        if loss_pct is None:
            loss_pct = 100.0

    if include_jitter:
        return connectivity_ok, latency_ms, loss_pct, jitter_ms
    return connectivity_ok, latency_ms, loss_pct


# ── Legacy link-based measurement collection ──────────────────────────────────

def collect_measurements(targets: List[Dict[str, Any]], count: int, timeout_sec: int) -> List[Dict[str, Any]]:
    """Polls each configured target and returns measurement dicts conforming to ingest schema."""
    now_iso = datetime.now(timezone.utc).isoformat()
    measurements = []

    for target in targets:
        comp_id = target.get("component_id")
        host = target.get("host")
        if not comp_id or not host:
            continue

        conn_ok, latency, loss = ping_target(host, count=count, timeout_sec=timeout_sec)
        throughput = target.get("throughput_mbps")

        measurements.append({
            "component_id": comp_id,
            "latency_ms": latency,
            "packet_loss_pct": loss,
            "throughput_mbps": throughput,
            "connectivity_ok": conn_ok,
            "timestamp": now_iso,
        })

    return measurements


def send_telemetry(api_url: str, measurements: List[Dict[str, Any]], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Posts telemetry batch to HopTrace ingest API endpoint using urllib."""
    payload = json.dumps(measurements).encode("utf-8")
    req = urllib.request.Request(
        url=api_url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "HopTrace-Agent/2.1",
        },
    )

    if api_key and api_key.strip():
        req.add_header("X-API-Key", api_key.strip())

    with urllib.request.urlopen(req, timeout=10.0) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


# ── Hop-by-hop path probe collection (v2.1) ───────────────────────────────────

def probe_node(node: Dict[str, Any], count: int, timeout_sec: int) -> Dict[str, Any]:
    """Pings a single node and returns probe result dict."""
    node_id = node.get("node_id", "unknown")
    host = node.get("host", "")
    if not host:
        return {"node_id": node_id, "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0}

    res_tuple = ping_target(host, count=count, timeout_sec=timeout_sec, include_jitter=True)
    conn_ok = res_tuple[0]
    latency = res_tuple[1]
    loss = res_tuple[2]
    jitter = res_tuple[3] if len(res_tuple) > 3 else None
    res = {
        "node_id": node_id,
        "reachable": conn_ok,
        "latency_ms": latency,
        "packet_loss_pct": loss,
    }
    if jitter is not None:
        res["jitter_ms"] = jitter
    return res


def collect_path_probes(
    nodes: List[Dict[str, Any]],
    count: int,
    timeout_sec: int,
    max_workers: int = 16,
) -> List[Dict[str, Any]]:
    """Pings all nodes in parallel using concurrent.futures.ThreadPoolExecutor."""
    results: List[Dict[str, Any]] = []
    workers = min(max_workers, max(1, len(nodes)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(probe_node, node, count, timeout_sec): node
            for node in nodes
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                node = futures[future]
                print(f"[HopTrace Agent] Error probing {node.get('node_id')}: {exc}", file=sys.stderr)
                results.append({
                    "node_id": node.get("node_id", "unknown"),
                    "reachable": False,
                    "latency_ms": None,
                    "packet_loss_pct": 100.0,
                })
    return results


def send_path_probes(
    api_base: str,
    payload: Dict[str, Any],
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """POSTs path probe batch to /api/v1/probes/path."""
    url = f"{api_base.rstrip('/')}/api/v1/probes/path"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "HopTrace-Agent/2.1",
        },
    )

    if api_key and api_key.strip():
        req.add_header("X-API-Key", api_key.strip())

    with urllib.request.urlopen(req, timeout=10.0) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


# ── Agent heartbeat & blind-spot detection ────────────────────────────────────

def send_heartbeat(
    api_base: str,
    agent_id: str,
    site_id: str,
    buffered_count: int,
    version: str = "2.1",
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Sends heartbeat ping to HopTrace /api/v1/agent/heartbeat.

    Non-fatal: network errors log a warning and return None without raising.
    """
    url = f"{api_base.rstrip('/')}/api/v1/agent/heartbeat"
    payload = {
        "agent_id": agent_id,
        "site_id": site_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "buffered_count": buffered_count,
        "version": version,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "HopTrace-Agent/2.1",
        },
    )
    if api_key and api_key.strip():
        req.add_header("X-API-Key", api_key.strip())

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except Exception as exc:
        print(f"[HopTrace Agent] Heartbeat failed (non-fatal): {exc}", file=sys.stderr)
        return None


# ── Store-and-forward local buffer ───────────────────────────────────────────

def count_buffered(buffer_path: str) -> int:
    """Returns the count of buffered lines in buffer_path (0 if missing)."""
    if not os.path.exists(buffer_path):
        return 0
    try:
        with open(buffer_path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def append_to_buffer(buffer_path: str, batch: Dict[str, Any], max_buffer_size: int = 5000) -> int:
    """Appends a batch to local JSONL buffer.

    If buffer exceeds max_buffer_size lines, oldest lines are dropped and logged.
    Returns the new buffered count.
    """
    buf_dir = os.path.dirname(os.path.abspath(buffer_path))
    if buf_dir and not os.path.exists(buf_dir):
        os.makedirs(buf_dir, exist_ok=True)

    lines: List[str] = []
    if os.path.exists(buffer_path):
        try:
            with open(buffer_path, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
        except Exception as exc:
            print(f"[HopTrace Agent] Error reading buffer before append: {exc}", file=sys.stderr)
            lines = []

    lines.append(json.dumps(batch) + "\n")

    if len(lines) > max_buffer_size:
        dropped = len(lines) - max_buffer_size
        print(
            f"[HopTrace Agent] Buffer exceeded {max_buffer_size} items; dropping {dropped} oldest record(s).",
            file=sys.stderr,
        )
        lines = lines[dropped:]

    tmp_path = f"{buffer_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.replace(tmp_path, buffer_path)

    return len(lines)


def flush_buffer(
    api_base: str,
    buffer_path: str,
    max_flush: int = 20,
    api_key: Optional[str] = None,
) -> int:
    """Flushes up to max_flush buffered batches oldest-first.

    Atomically rewrites buffer with remaining items. Stops flushing on send failure.
    Skips and discards corrupt lines. Returns number of successfully flushed batches.
    """
    if not os.path.exists(buffer_path):
        return 0

    try:
        with open(buffer_path, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
    except Exception as exc:
        print(f"[HopTrace Agent] Error reading buffer: {exc}", file=sys.stderr)
        return 0

    if not lines:
        return 0

    batch_slice = lines[:max_flush]
    flushed_count = 0
    stopped_early = False
    remaining_lines: List[str] = []

    for idx, raw_line in enumerate(batch_slice):
        try:
            item = json.loads(raw_line)
        except Exception as parse_err:
            print(f"[HopTrace Agent] Skipping corrupt buffer line: {parse_err}", file=sys.stderr)
            continue

        try:
            if isinstance(item, dict) and (item.get("type") == "path_probes" or "results" in item):
                payload = item.get("payload", item)
                send_path_probes(api_base, payload, api_key=api_key)
            elif isinstance(item, dict) and item.get("type") == "telemetry":
                payload = item.get("payload", [])
                api_url = f"{api_base.rstrip('/')}/api/v1/measurements/ingest"
                send_telemetry(api_url, payload, api_key=api_key)
            elif isinstance(item, list):
                api_url = f"{api_base.rstrip('/')}/api/v1/measurements/ingest"
                send_telemetry(api_url, item, api_key=api_key)
            else:
                send_path_probes(api_base, item, api_key=api_key)
            flushed_count += 1
        except Exception as exc:
            print(f"[HopTrace Agent] Flush failed at record {idx}: {exc}", file=sys.stderr)
            remaining_lines = lines[idx:]
            stopped_early = True
            break

    if not stopped_early:
        remaining_lines = lines[max_flush:]

    if remaining_lines:
        tmp_path = f"{buffer_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.writelines(remaining_lines)
        os.replace(tmp_path, buffer_path)
    else:
        try:
            os.remove(buffer_path)
        except Exception:
            with open(buffer_path, "w", encoding="utf-8") as f:
                pass

    return flushed_count


# ── Field Pre-Flight Diagnostic Check (--check) ──────────────────────────────

def run_diagnostic_check(config: Dict[str, Any]) -> int:
    """Pre-flight diagnostic report for rural field installation engineers.

    Tests connectivity to all nodes, API endpoint, and local storage.
    Returns 0 on success, 1 on failure.
    """
    api_base = config.get("api_base", "http://127.0.0.1:8000")
    agent_id = config.get("agent_id", "agent-rampur-1")
    site_id = config.get("site_id", "rampur")
    vantage_node_id = config.get("vantage_node_id", "GW1")
    nodes = config.get("nodes", [])
    targets = config.get("targets", [])
    buffer_path = config.get("buffer_path", "agent/buffer.jsonl")

    print("\n" + "=" * 68)
    print(" HopTrace Field Pre-Flight Diagnostic Report")
    print(f" Agent ID: {agent_id} | Site: {site_id} | Vantage Node: {vantage_node_id}")
    print(f" Target API: {api_base}")
    print("=" * 68)

    # 1. Check API endpoint
    api_online = False
    try:
        req = urllib.request.Request(
            f"{api_base.rstrip('/')}/api/v1/health",
            headers={"User-Agent": "HopTrace-Agent/2.1"},
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                api_online = True
    except Exception:
        api_online = False

    api_str = "ONLINE (200 OK)" if api_online else "OFFLINE / UNREACHABLE"
    print(f"[*] API Service Connectivity: {api_str}")

    # 2. Check local buffer
    buf_count = count_buffered(buffer_path)
    print(f"[*] Local Offline Storage: {buffer_path} ({buf_count} queued items)")

    # 3. Probe targets/nodes concurrently
    items = nodes if nodes else targets
    print("-" * 68)
    print(f"{'Target ID':<12} {'Host':<18} {'Status':<14} {'Latency':<12} {'Loss'}")
    print("-" * 68)

    def _check_item(it: Dict[str, Any]) -> Tuple[str, str, bool, Optional[float], Optional[float]]:
        nid = it.get("node_id") or it.get("component_id", "unknown")
        h = it.get("host", "")
        c_ok, lt, ls = ping_target(h, count=2, timeout_sec=1)
        return nid, h, c_ok, lt, ls

    workers = min(16, max(1, len(items)))
    all_reachable = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for nid, h, conn_ok, lat, loss in executor.map(_check_item, items):
            status_label = "REACHABLE" if conn_ok else "UNREACHABLE"
            if not conn_ok:
                all_reachable = False
            lat_str = f"{lat:.1f}ms" if lat is not None else "--"
            loss_str = f"{loss:.0f}%" if loss is not None else "--"
            print(f"{nid:<12} {h:<18} {status_label:<14} {lat_str:<12} {loss_str}")

    print("=" * 68)
    if all_reachable and api_online:
        print("[+] VERDICT: ALL SYSTEMS OPERATIONAL — READY FOR FIELD DEPLOYMENT")
        print("=" * 68 + "\n")
        return 0
    else:
        print("[-] VERDICT: WARNINGS DETECTED — CHECK NETWORK / POWER BEFORE PROCEEDING")
        print("=" * 68 + "\n")
        return 1


# ── Configuration & Execution ────────────────────────────────────────────────

def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration JSON file."""
    if not os.path.isabs(config_path):
        if not os.path.exists(config_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.join(script_dir, config_path)
            if os.path.exists(candidate):
                config_path = candidate

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_agent(config: Dict[str, Any], once: bool = False) -> None:
    """Main collection loop with store-and-forward, backoff, and graceful shutdown."""
    api_base = config.get("api_base", "http://127.0.0.1:8000")
    api_key = config.get("api_key", "")
    interval = int(config.get("interval_seconds", 5))
    ping_count = int(config.get("ping_count", 3))
    timeout = int(config.get("timeout_seconds", 2))

    agent_id = config.get("agent_id", "agent-rampur-1")
    site_id = config.get("site_id", "rampur")
    vantage_node_id = config.get("vantage_node_id", "GW1")
    buffer_path = config.get("buffer_path", "agent/buffer.jsonl")
    nodes = config.get("nodes", [])
    targets = config.get("targets", [])

    is_node_mode = bool(nodes)
    if is_node_mode:
        print(f"[HopTrace Agent] Starting path-probe collection for {len(nodes)} nodes (vantage: {vantage_node_id})")
        print(f"[HopTrace Agent] Target endpoint: {api_base}/api/v1/probes/path")
    else:
        api_url = config.get("api_url", f"{api_base}/api/v1/measurements/ingest")
        print(f"[HopTrace Agent] Starting legacy telemetry collection for {len(targets)} targets")
        print(f"[HopTrace Agent] Ingest endpoint: {api_url}")

    print(f"[HopTrace Agent] Agent ID: {agent_id} | Site: {site_id} | Buffer: {buffer_path}")
    print(f"[HopTrace Agent] Interval: {interval}s | Ping count: {ping_count}")

    # Graceful shutdown handler
    shutdown_requested = [False]

    def _handle_signal(signum: int, frame: Any) -> None:
        print("\n[HopTrace Agent] Shutdown signal received. Exiting cleanly...", file=sys.stderr)
        shutdown_requested[0] = True

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        pass

    backoff = interval

    while not shutdown_requested[0]:
        # 1. Check local buffer count and send heartbeat
        buf_count = count_buffered(buffer_path)
        send_heartbeat(
            api_base=api_base,
            agent_id=agent_id,
            site_id=site_id,
            buffered_count=buf_count,
            version="2.1",
            api_key=api_key,
        )

        # 2. Collect measurements / path probes
        batch_to_buffer: Optional[Dict[str, Any]] = None
        send_successful = False

        try:
            if is_node_mode:
                probe_results = collect_path_probes(nodes, count=ping_count, timeout_sec=timeout)
                now_iso = datetime.now(timezone.utc).isoformat()
                payload = {
                    "agent_id": agent_id,
                    "vantage_node_id": vantage_node_id,
                    "timestamp": now_iso,
                    "results": probe_results,
                }
                batch_to_buffer = {"type": "path_probes", "payload": payload}
                print(f"[HopTrace Agent] Probed {len(probe_results)} nodes, sending path probe...")
                res = send_path_probes(api_base, payload, api_key=api_key)
                print(
                    f"[HopTrace Agent] Path probe success: derived_links={res.get('derived_links')} "
                    f"failed_nodes={res.get('first_failed_nodes')} incident={res.get('incident_id')}"
                )
                send_successful = True
            else:
                api_url = config.get("api_url", f"{api_base}/api/v1/measurements/ingest")
                measurements = collect_measurements(targets, count=ping_count, timeout_sec=timeout)
                batch_to_buffer = {"type": "telemetry", "payload": measurements}
                print(f"[HopTrace Agent] Collected {len(measurements)} measurements, posting to ingest...")
                res = send_telemetry(api_url, measurements, api_key=api_key)
                print(
                    f"[HopTrace Agent] Ingest success: status={res.get('status')} "
                    f"count={res.get('ingested_count')} incident={res.get('incident_id')}"
                )
                send_successful = True

        except urllib.error.HTTPError as http_err:
            print(f"[HopTrace Agent] HTTP Error {http_err.code}: {http_err.reason}", file=sys.stderr)
            try:
                err_body = http_err.read().decode("utf-8")
                print(f"[HopTrace Agent] Error detail: {err_body}", file=sys.stderr)
            except Exception:
                pass
        except Exception as exc:
            print(f"[HopTrace Agent] Failed to send telemetry/probes: {exc}", file=sys.stderr)

        # 3. Store-and-forward management & backoff adjustment
        if not send_successful and batch_to_buffer:
            new_count = append_to_buffer(buffer_path, batch_to_buffer)
            print(f"[HopTrace Agent] Buffered batch locally (backlog: {new_count})")
            backoff = min(60, backoff * 2)
            if backoff > interval:
                print(f"[HopTrace Agent] Backing off next transmission attempt to {backoff}s")
        elif send_successful:
            backoff = interval
            current_buffered = count_buffered(buffer_path)
            if current_buffered > 0:
                flushed = flush_buffer(api_base, buffer_path, max_flush=20, api_key=api_key)
                if flushed > 0:
                    print(f"[HopTrace Agent] Successfully flushed {flushed} batch(es) from buffer.")

        if once or shutdown_requested[0]:
            break

        # Responsive sleep loop allowing prompt exit on SIGINT
        for _ in range(backoff):
            if shutdown_requested[0]:
                break
            time.sleep(1)

    if shutdown_requested[0]:
        remaining = count_buffered(buffer_path)
        print(f"[HopTrace Agent] Shutdown completed. Local queue: {remaining} unsent batches.")


def main() -> None:
    parser = argparse.ArgumentParser(description="HopTrace Telemetry Collector Agent")
    parser.add_argument(
        "--config",
        default="agent/config.json",
        help="Path to agent JSON config file (default: agent/config.json)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute a single collection and ingest cycle, then exit",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run non-destructive diagnostic pre-flight check across all nodes & API, then exit",
    )
    parser.add_argument(
        "--url",
        help="Override the target ingest API URL or base URL",
    )
    parser.add_argument(
        "--api-key",
        help="Override or specify the X-API-Key header",
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Override collection interval in seconds",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.url:
        if "probes" in args.url or "measurements" in args.url:
            cfg["api_url"] = args.url
            cfg["api_base"] = args.url.split("/api/v1")[0]
        else:
            cfg["api_base"] = args.url
    if args.api_key:
        cfg["api_key"] = args.api_key
    if args.interval:
        cfg["interval_seconds"] = args.interval

    if args.check:
        sys.exit(run_diagnostic_check(cfg))

    run_agent(cfg, once=args.once)


if __name__ == "__main__":
    main()

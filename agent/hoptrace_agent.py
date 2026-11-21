#!/usr/bin/env python3
"""HopTrace Standalone Telemetry Collector Agent.

Lightweight, zero-dependency monitoring daemon that measures network latency,
packet loss, and reachability across physical or virtual targets and ingests
the observed metrics into HopTrace via POST /api/v1/measurements/ingest.

Uses exclusively the Python Standard Library (no pip dependencies required).
Compatible with Windows, Linux, and macOS.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def ping_target(host: str, count: int = 3, timeout_sec: int = 2) -> Tuple[bool, Optional[float], Optional[float]]:
    """Pings a target host and returns (connectivity_ok, latency_ms, packet_loss_pct).

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
    except Exception as exc:
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

    # Connectivity evaluation
    if loss_pct is not None and loss_pct >= 100.0:
        return False, None, 100.0

    if proc.returncode == 0:
        connectivity_ok = True
        if loss_pct is None:
            loss_pct = 0.0
    else:
        connectivity_ok = bool(latency_ms is not None or (loss_pct is not None and loss_pct < 100.0))
        if loss_pct is None:
            loss_pct = 100.0

    return connectivity_ok, latency_ms, loss_pct


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
            "User-Agent": "HopTrace-Agent/2.0",
        },
    )

    if api_key and api_key.strip():
        req.add_header("X-API-Key", api_key.strip())

    with urllib.request.urlopen(req, timeout=10.0) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration JSON file."""
    if not os.path.isabs(config_path):
        # Look relative to current working dir, then relative to agent script dir
        if not os.path.exists(config_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.join(script_dir, config_path)
            if os.path.exists(candidate):
                config_path = candidate

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_agent(config: Dict[str, Any], once: bool = False) -> None:
    """Main collection loop."""
    api_url = config.get("api_url", "http://127.0.0.1:8000/api/v1/measurements/ingest")
    api_key = config.get("api_key", "")
    interval = int(config.get("interval_seconds", 5))
    ping_count = int(config.get("ping_count", 3))
    timeout = int(config.get("timeout_seconds", 2))
    targets = config.get("targets", [])

    print(f"[HopTrace Agent] Starting telemetry collection for {len(targets)} targets")
    print(f"[HopTrace Agent] Ingest endpoint: {api_url}")
    print(f"[HopTrace Agent] Interval: {interval}s, Ping count: {ping_count}")

    while True:
        try:
            measurements = collect_measurements(targets, count=ping_count, timeout_sec=timeout)
            print(f"[HopTrace Agent] Collected {len(measurements)} measurements, posting to ingest...")
            res = send_telemetry(api_url, measurements, api_key=api_key)
            print(f"[HopTrace Agent] Ingest success: status={res.get('status')} count={res.get('ingested_count')} incident={res.get('incident_id')}")
        except urllib.error.HTTPError as http_err:
            print(f"[HopTrace Agent] HTTP Error {http_err.code}: {http_err.reason}", file=sys.stderr)
            try:
                err_body = http_err.read().decode("utf-8")
                print(f"[HopTrace Agent] Error detail: {err_body}", file=sys.stderr)
            except Exception:
                pass
        except Exception as exc:
            print(f"[HopTrace Agent] Failed to ingest telemetry: {exc}", file=sys.stderr)

        if once:
            break

        time.sleep(interval)


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
        "--url",
        help="Override the target ingest API URL",
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
        cfg["api_url"] = args.url
    if args.api_key:
        cfg["api_key"] = args.api_key
    if args.interval:
        cfg["interval_seconds"] = args.interval

    run_agent(cfg, once=args.once)


if __name__ == "__main__":
    main()

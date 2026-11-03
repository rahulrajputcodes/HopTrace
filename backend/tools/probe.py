#!/usr/bin/env python3
"""HopTrace Standalone Network Telemetry Probe (Task 5).

A lightweight, zero-dependency probe script using only Python standard library.
Pings 1 to 3 target hosts at an interval and appends live metrics to a CSV file.

Output CSV Columns:
  timestamp,link_id,latency_ms,packet_loss_pct,throughput_mbps,connectivity_ok

Usage:
  python backend/tools/probe.py --targets 127.0.0.1,8.8.8.8 --interval 3.0 --iterations 10 --out live_telemetry.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def ping_host(host: str, count: int = 3, timeout_ms: int = 1500) -> Tuple[Optional[float], Optional[float], bool]:
    """Pings a host and returns (latency_ms, packet_loss_pct, connectivity_ok)."""
    system = platform.system().lower()

    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    elif system == "darwin":  # macOS
        cmd = ["ping", "-c", str(count), "-W", str(timeout_ms), host]
    else:  # Linux
        cmd = ["ping", "-c", str(count), "-W", str(max(1, timeout_ms // 1000)), host]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = proc.stdout
    except Exception:
        return None, 100.0, False

    # Extract packet loss percentage
    loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", output)
    loss_pct = float(loss_match.group(1)) if loss_match else (0.0 if proc.returncode == 0 else 100.0)

    # Extract round-trip latency average
    # macOS/BSD: round-trip min/avg/max/stddev = 12.3/14.5/18.9/2.1 ms
    # Linux: rtt min/avg/max/mdev = 12.3/14.5/18.9/2.1 ms
    # Windows: Average = 14ms
    rtt_match = re.search(r"(?:round-trip|rtt)[^=]*=\s*[\d\.]+/([\d\.]+)/", output)
    if not rtt_match:
        win_rtt = re.search(r"Average\s*=\s*(\d+)ms", output)
        avg_lat = float(win_rtt.group(1)) if win_rtt else None
    else:
        avg_lat = float(rtt_match.group(1))

    conn_ok = loss_pct < 100.0 and avg_lat is not None
    return avg_lat, loss_pct, conn_ok


def run_probe(
    targets: List[Tuple[str, str]],
    interval: float,
    iterations: Optional[int],
    out_path: str,
) -> None:
    """Runs the probe loop and appends rows to CSV."""
    file_exists = os.path.exists(out_path)

    print(f"Starting HopTrace live telemetry probe...")
    print(f"Targets: {targets}")
    print(f"Interval: {interval}s | Iterations: {iterations or 'continuous'} | Output: {out_path}")

    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists or os.path.getsize(out_path) == 0:
            writer.writerow(["timestamp", "link_id", "latency_ms", "packet_loss_pct", "throughput_mbps", "connectivity_ok"])
            f.flush()

        it = 0
        try:
            while iterations is None or it < iterations:
                now_str = datetime.now(timezone.utc).isoformat()
                for link_id, host in targets:
                    lat, loss, conn = ping_host(host)
                    # Simulated nominal throughput placeholder for probe
                    tp = 100.0 if conn else 0.0
                    writer.writerow([
                        now_str,
                        link_id,
                        f"{lat:.2f}" if lat is not None else "",
                        f"{loss:.1f}" if loss is not None else "100.0",
                        f"{tp:.1f}",
                        str(conn).lower(),
                    ])
                    f.flush()
                    status_sym = "✓" if conn else "✗"
                    print(f"[{now_str}] {link_id} ({host}): {status_sym} lat={lat}ms loss={loss}%")

                it += 1
                if iterations is None or it < iterations:
                    time.sleep(interval)
        except KeyboardInterrupt:
            print("\nProbe stopped by operator.")

    print(f"Probe completed. Metrics logged to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="HopTrace Live Network Probe")
    parser.add_argument("--targets", default="L1=127.0.0.1,L3=8.8.8.8", help="Link ID to host mapping, e.g. L1=127.0.0.1,L3=8.8.8.8")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between probe ticks")
    parser.add_argument("--iterations", type=int, default=10, help="Number of probe iterations (default: 10, None for continuous)")
    parser.add_argument("--out", default="telemetry_live.csv", help="CSV output destination")
    args = parser.parse_args()

    # Parse link=host pairs
    target_pairs = []
    for item in args.targets.split(","):
        if "=" in item:
            lid, host = item.split("=", 1)
            target_pairs.append((lid.strip(), host.strip()))
        else:
            target_pairs.append((f"L_{item.strip()}", item.strip()))

    run_probe(target_pairs, args.interval, args.iterations, args.out)


if __name__ == "__main__":
    main()

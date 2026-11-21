"""
In-memory Agent Monitoring Service for HopTrace Part 1.

Tracks agent heartbeats and provides status snapshots with blind-spot detection.
Integration I-2: Track A calls agent_monitor.get_status_snapshot() in WS loop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings


class AgentMonitor:
    def __init__(self) -> None:
        self._agents: Dict[str, Dict[str, Any]] = {}

    def record_heartbeat(
        self,
        agent_id: str,
        site_id: str,
        timestamp: Optional[str] = None,
        buffered_count: int = 0,
        version: str = "2.1",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record heartbeat from an agent. Auto-registers unknown agents."""
        if now is None:
            now_dt = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now_dt = now.replace(tzinfo=timezone.utc)
        else:
            now_dt = now

        last_seen_utc = now_dt.isoformat()

        record = {
            "agent_id": agent_id,
            "site_id": site_id,
            "timestamp": timestamp or last_seen_utc,
            "last_seen_utc": last_seen_utc,
            "last_seen_dt": now_dt,
            "buffered_count": buffered_count,
            "version": version,
        }
        self._agents[agent_id] = record
        return record

    def get_status_snapshot(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Return status snapshot of all known agents per contract §2.4.

        status = 'online' if now - last_seen <= settings.agent_silent_seconds else 'silent'.
        """
        if now is None:
            now_dt = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now_dt = now.replace(tzinfo=timezone.utc)
        else:
            now_dt = now

        silent_limit = float(settings.agent_silent_seconds)
        snapshot: List[Dict[str, Any]] = []

        for agent_id, info in sorted(self._agents.items()):
            last_seen_dt = info["last_seen_dt"]
            silent_for_seconds = max(0.0, (now_dt - last_seen_dt).total_seconds())
            is_online = silent_for_seconds <= silent_limit

            snapshot.append({
                "agent_id": agent_id,
                "site_id": info["site_id"],
                "last_seen_utc": info["last_seen_utc"],
                "status": "online" if is_online else "silent",
                "silent_for_seconds": int(round(silent_for_seconds)),
                "buffered_count": info.get("buffered_count", 0),
            })

        return snapshot

    def reset(self) -> None:
        """Reset all monitored agents (useful for test isolation)."""
        self._agents.clear()


# Global singleton instance
agent_monitor = AgentMonitor()

# Module-level functions delegating to singleton
record_heartbeat = agent_monitor.record_heartbeat
get_status_snapshot = agent_monitor.get_status_snapshot
reset_agent_monitor = agent_monitor.reset

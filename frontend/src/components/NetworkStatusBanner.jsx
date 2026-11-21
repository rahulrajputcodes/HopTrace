import { useEffect, useState } from 'react';
import useStore from '../store/appStore';

function formatElapsed(createdIso) {
  if (!createdIso) return '0s';
  const created = new Date(createdIso).getTime();
  if (isNaN(created)) return '0s';
  const diffSec = Math.max(0, Math.floor((Date.now() - created) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const m = Math.floor(diffSec / 60);
  const s = diffSec % 60;
  return `${m}m ${s}s`;
}

export default function NetworkStatusBanner() {
  const activeIncident = useStore(s => s.activeIncident);
  const affectedSubscribers = useStore(s => s.affectedSubscribers);
  const allSubscribers = useStore(s => s.allSubscribers);
  const villages = useStore(s => s.villages);

  const [, setTick] = useState(0);

  // Ticker for elapsed time during active fault
  useEffect(() => {
    if (!activeIncident) return undefined;
    const interval = setInterval(() => {
      setTick(t => t + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [activeIncident]);

  const totalSubs = allSubscribers.length || 20;
  const affectedCount = affectedSubscribers.length;
  const connectedSubs = Math.max(0, totalSubs - affectedCount);

  const villageList = (villages || []).filter(
    v => v && v.village_id !== 'block_hq' && v.village_id !== 'gw1'
  );
  const villageCount = villageList.length || 3;

  if (!activeIncident) {
    return (
      <aside
        data-testid="network-status-banner"
        aria-label="Network Health Status"
        className="w-full bg-emerald-950/50 border-b border-emerald-800/60 px-4 py-1.5 flex items-center justify-between text-xs text-emerald-300 shrink-0 select-none transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
          <span className="font-semibold tracking-wide">
            All {villageCount} villages healthy · {connectedSubs}/{totalSubs} connected
          </span>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-emerald-400/80 text-xs">
          <span>Zero active incidents</span>
          <span>·</span>
          <span>Baseline nominal</span>
        </div>
      </aside>
    );
  }

  const suspected = activeIncident.suspected_component_id || 'Unknown';
  const timeSince = formatElapsed(activeIncident.created_at);
  const householdsText = `${affectedCount} household${affectedCount === 1 ? '' : 's'}`;

  return (
    <aside
      data-testid="network-status-banner"
      aria-label="Network Fault Alert"
      className="w-full bg-red-950/90 border-b border-red-700 px-4 py-2 flex items-center justify-between text-xs text-red-200 shrink-0 select-none shadow-md transition-colors"
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="w-2.5 h-2.5 rounded-full bg-red-400 animate-pulse shrink-0" />
        <span className="font-bold text-white tracking-wide">
          FAULT DETECTED:
        </span>
        <span className="font-semibold text-red-100">
          Suspected link {suspected}
        </span>
        <span>·</span>
        <span>{householdsText} affected</span>
        <span>·</span>
        <span>Detected {timeSince} ago</span>
      </div>
      {activeIncident.summary && (
        <div className="hidden md:block text-red-300/80 text-xs truncate max-w-md">
          {activeIncident.summary}
        </div>
      )}
    </aside>
  );
}

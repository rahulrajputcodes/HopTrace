/**
 * M4 — SLAView component
 *
 * Displays per-village SLA metrics (uptime %, downtime, incident counts)
 * from GET /api/v1/topology/sla?window_hours=N.
 *
 * Rules:
 * - Uses useApi().fetchSla() — never raw fetch.
 * - Nothing fake in live mode: loading/error/empty states shown honestly.
 * - No invented percentages or timestamps ever rendered.
 * - Window selector: 24h / 7d / 30d. Manual refresh + "as of" timestamp.
 *
 * Mounting: imported and rendered in App.jsx under {/* M4 SLA view *\/}
 * as a full-width section below SubscriberOps.
 */

import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../../hooks/useApi';
import {
  formatUptime,
  formatDowntime,
  slaStatusConfig,
  windowLabel,
  formatTimestamp,
} from './slaHelpers';

// Window options presented to the user
const WINDOW_OPTIONS = [
  { label: '24 h', hours: 24 },
  { label: '7 d',  hours: 168 },
  { label: '30 d', hours: 720 },
];

// ---------------------------------------------------------------------------
// VillageSlaRow — one row in the SLA table
// ---------------------------------------------------------------------------
function VillageSlaRow({ item }) {
  const cfg = slaStatusConfig(item.status);

  return (
    <tr className="border-t border-slate-800 hover:bg-slate-800/30 transition-colors">
      {/* Village name */}
      <td className="px-4 py-3 text-sm font-medium text-slate-200 whitespace-nowrap">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dotClass}`} aria-hidden="true" />
          {item.village_name}
        </div>
      </td>

      {/* Status pill */}
      <td className="px-4 py-3">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${cfg.badgeClass}`}>
          {cfg.label}
        </span>
      </td>

      {/* Uptime % with mini bar */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 min-w-[80px]">
          <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden" aria-hidden="true">
            <div
              className={`h-full rounded-full transition-all ${cfg.dotClass}`}
              style={{ width: `${Math.min(100, Math.max(0, item.uptime_pct ?? 0))}%` }}
            />
          </div>
          <span className={`text-sm font-mono font-semibold ${cfg.colorClass} whitespace-nowrap`}>
            {formatUptime(item.uptime_pct)}
          </span>
        </div>
      </td>

      {/* Downtime */}
      <td className="px-4 py-3 text-sm font-mono text-slate-300 whitespace-nowrap">
        {formatDowntime(item.downtime_minutes)}
      </td>

      {/* Total incidents */}
      <td className="px-4 py-3 text-sm text-slate-300 text-center">
        {item.total_incidents ?? '–'}
      </td>

      {/* Active incidents */}
      <td className="px-4 py-3 text-center">
        {item.active_incidents > 0 ? (
          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-900/80 text-red-300 text-xs font-bold border border-red-700/60">
            {item.active_incidents}
          </span>
        ) : (
          <span className="text-slate-600 text-sm">—</span>
        )}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// SLAView — main component
// ---------------------------------------------------------------------------
export default function SLAView() {
  const { fetchSla } = useApi();

  const [windowHours, setWindowHours] = useState(24);
  const [slaData, setSlaData] = useState(null);       // null = never loaded
  const [lastGoodData, setLastGoodData] = useState(null);
  const [fetchState, setFetchState] = useState('loading'); // 'loading' | 'ok' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  const doFetch = useCallback(async (hours) => {
    setFetchState(prev => prev === 'ok' ? 'ok' : 'loading'); // keep 'ok' while refreshing
    try {
      const data = await fetchSla(hours);
      setSlaData(data);
      setLastGoodData(data);
      setFetchState('ok');
      setErrorMsg('');
    } catch (e) {
      setFetchState('error');
      setErrorMsg(e?.message || 'Failed to load SLA data');
      // keep lastGoodData visible
    }
  }, [fetchSla]);

  // Fetch on mount and whenever window changes.
  // setTimeout(..., 0) defers setState calls out of the synchronous effect body
  // to satisfy react-hooks/set-state-in-effect.
  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(() => {
      if (cancelled) return;
      setSlaData(null);
      setFetchState('loading');
      doFetch(windowHours);
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [windowHours, doFetch]);

  const handleWindowChange = (hours) => {
    if (hours !== windowHours) setWindowHours(hours);
  };

  const handleRefresh = () => doFetch(windowHours);

  // Determine display data: prefer fresh, fall back to lastGoodData on error
  const displayData = fetchState === 'error' ? lastGoodData : slaData;
  const villageList = displayData
    ? Object.values(displayData.villages).sort((a, b) =>
        a.village_name.localeCompare(b.village_name)
      )
    : [];

  return (
    <div className="bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-slate-800">
        <span className="text-blue-400 text-sm" aria-hidden="true">📊</span>
        <span className="text-white font-semibold text-sm">SLA Dashboard</span>

        {/* Window selector */}
        <div
          role="group"
          aria-label="SLA time window"
          className="flex items-center gap-1 ml-1"
        >
          {WINDOW_OPTIONS.map(opt => (
            <button
              key={opt.hours}
              onClick={() => handleWindowChange(opt.hours)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                windowHours === opt.hours
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
              aria-pressed={windowHours === opt.hours}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* "As of" timestamp — only real data, never invented */}
        {displayData?.timestamp_utc && (
          <span className="text-xs text-slate-500 ml-auto">
            As of {formatTimestamp(displayData.timestamp_utc)}
          </span>
        )}

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={fetchState === 'loading' && !lastGoodData}
          className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded transition-colors disabled:opacity-40 ml-1"
          aria-label="Refresh SLA data"
          title="Refresh"
        >
          {fetchState === 'loading' ? '↻' : '⟳'}
        </button>
      </div>

      {/* Window label subtitle */}
      <div className="px-4 py-1.5 bg-slate-900/40 border-b border-slate-800/60">
        <span className="text-xs text-slate-500">{windowLabel(windowHours)}</span>
        {fetchState === 'error' && (
          <span className="ml-3 text-xs text-amber-500">
            ⚠ {errorMsg} — {lastGoodData ? 'showing last known data' : 'no data available'}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="p-3">
        {/* Loading state — no fake data ever shown here */}
        {fetchState === 'loading' && !lastGoodData && (
          <div className="flex items-center justify-center gap-3 py-10 text-slate-500">
            <div className="w-5 h-5 border-2 border-slate-600 border-t-blue-400 rounded-full animate-spin" />
            <span className="text-sm">Loading SLA data…</span>
          </div>
        )}

        {/* Error with no prior data */}
        {fetchState === 'error' && !lastGoodData && (
          <div className="flex flex-col items-center justify-center gap-3 py-10 text-slate-500">
            <span className="text-2xl" aria-hidden="true">⚠️</span>
            <p className="text-sm text-slate-400">{errorMsg}</p>
            <button
              onClick={handleRefresh}
              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty: API returned successfully but no villages */}
        {fetchState === 'ok' && villageList.length === 0 && (
          <div className="flex items-center justify-center py-10 text-slate-500 text-sm">
            No SLA data available for this window.
          </div>
        )}

        {/* SLA table — only rendered when we have real data */}
        {villageList.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left" aria-label="Village SLA metrics">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-2 font-medium">Village</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Uptime</th>
                  <th className="px-4 py-2 font-medium">Downtime</th>
                  <th className="px-4 py-2 font-medium text-center">Incidents</th>
                  <th className="px-4 py-2 font-medium text-center">Active</th>
                </tr>
              </thead>
              <tbody>
                {villageList.map(item => (
                  <VillageSlaRow key={item.village_id} item={item} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Stale banner: showing old data while refreshing or after error */}
        {fetchState === 'loading' && lastGoodData && (
          <div className="mt-2 flex items-center gap-2 px-2 py-1.5 bg-slate-900/60 rounded text-xs text-slate-500">
            <div className="w-3 h-3 border border-slate-600 border-t-blue-400 rounded-full animate-spin flex-shrink-0" />
            Refreshing…
          </div>
        )}
      </div>
    </div>
  );
}

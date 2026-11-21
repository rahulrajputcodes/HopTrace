import { useEffect, useState, useCallback } from 'react';
import useStore from '../store/appStore';
import { useApi } from '../hooks/useApi';
import {
  formatElapsed,
  formatRevenue,
  getNextStep,
} from './networkStatusHelpers';

export default function NetworkStatusBanner() {
  const activeIncident = useStore(s => s.activeIncident);
  const affectedSubscribers = useStore(s => s.affectedSubscribers);
  const allSubscribers = useStore(s => s.allSubscribers);
  const villages = useStore(s => s.villages);
  const aiReport = useStore(s => s.aiReport);
  const agents = useStore(s => s.agents);
  const addToast = useStore(s => s.addToast);

  const { fetchBusinessImpact, fetchNotificationStatus, notifyIncident } = useApi();

  const [impactData, setImpactData] = useState(null);
  const [providerStatus, setProviderStatus] = useState({
    available: false,
    reason: 'Checking notification provider status…',
  });
  const [notifying, setNotifying] = useState(false);
  const [notified, setNotified] = useState(false);
  const [, setTick] = useState(0);

  // Live timer tick during active fault
  useEffect(() => {
    if (!activeIncident) return undefined;
    const interval = setInterval(() => {
      setTick(t => t + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [activeIncident]);

  // Fetch business impact data and notification provider status when incident changes
  useEffect(() => {
    const incidentId = activeIncident?.id;
    if (!incidentId) {
      setImpactData(null);
      setNotified(false);
      return;
    }

    let ignore = false;

    // 1. Fetch business impact (revenue at risk, affected count)
    fetchBusinessImpact(incidentId)
      .then((data) => {
        if (!ignore) setImpactData(data);
      })
      .catch(() => {
        if (!ignore) setImpactData(null);
      });

    // 2. Fetch notification provider availability
    fetchNotificationStatus()
      .then((status) => {
        if (!ignore) setProviderStatus(status);
      })
      .catch((err) => {
        if (!ignore) {
          setProviderStatus({
            available: false,
            reason: err.message || 'Notification provider is unavailable.',
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeIncident?.id, fetchBusinessImpact, fetchNotificationStatus]);

  const handleNotify = useCallback(async () => {
    if (!activeIncident?.id || !providerStatus.available || notifying) return;
    setNotifying(true);
    try {
      const res = await notifyIncident(activeIncident.id);
      setNotified(true);
      const count = res.sent_count || res.total_targeted || affectedSubscribers.length;
      addToast(`Dispatched outage alert to ${count} subscriber(s) via ${res.provider || 'provider'}`, 'success');
    } catch (err) {
      setProviderStatus(prev => ({
        ...prev,
        available: false,
        reason: err.message || 'Notification dispatch failed.',
      }));
      addToast(`Notification dispatch failed: ${err.message}`, 'error');
    } finally {
      setNotifying(false);
    }
  }, [activeIncident?.id, providerStatus.available, notifying, notifyIncident, affectedSubscribers.length, addToast]);

  const totalSubs = allSubscribers.length || 20;
  const affectedCount = impactData?.affected_count ?? affectedSubscribers.length;
  const connectedSubs = Math.max(0, totalSubs - affectedCount);

  const villageList = (villages || []).filter(
    v => v && v.village_id !== 'block_hq' && v.village_id !== 'gw1'
  );
  const villageCount = villageList.length || 3;

  // ── Blind-Spot Warning (when monitoring agent is silent or missing in live mode) ─
  const dataMode = useStore(s => s.dataMode);
  const silentAgent = Array.isArray(agents) ? agents.find(a => a.status === 'silent') : null;
  const isBlindSpot = Boolean(silentAgent || (dataMode === 'live' && (!agents || agents.length === 0)));

  const blindSpotBanner = isBlindSpot ? (
    <div
      data-testid="agent-silent-banner"
      role="alert"
      className="w-full bg-red-950/95 border-b-2 border-red-600 px-4 py-2 flex items-center justify-between text-xs text-red-100 shrink-0 select-none shadow-md"
    >
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="relative flex items-center justify-center w-2.5 h-2.5 shrink-0">
          <span className="absolute inline-flex w-full h-full rounded-full bg-red-400 opacity-75 animate-ping" />
          <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,1)]" />
        </span>
        <span className="bg-red-700 text-white font-extrabold text-[11px] px-1.5 py-0.5 rounded tracking-wide uppercase">
          BLIND SPOT
        </span>
        <span className="font-semibold text-white">
          {silentAgent
            ? `Monitoring agent silent for ${silentAgent.silent_for_seconds ?? 0}s — network state unknown. Check router or run agent.`
            : 'Monitoring agent not connected — network state unknown. Check router or run agent.'}
        </span>
      </div>
      {silentAgent && (
        <span className="text-red-300 text-[11px] font-mono hidden sm:inline">
          Agent: {silentAgent.agent_id} ({silentAgent.site_id})
        </span>
      )}
    </div>
  ) : null;

  // ── Healthy Nominal State ────────────────────────────────────────────────
  if (!activeIncident) {
    if (blindSpotBanner) {
      return blindSpotBanner;
    }

    return (
      <aside
        data-testid="network-status-banner"
        role="status"
        aria-live="polite"
        aria-label="Network Health Status"
        className="w-full bg-emerald-950/80 border-b border-emerald-800/80 px-4 py-2 flex items-center justify-between text-xs text-emerald-300 shrink-0 select-none shadow-sm motion-safe:transition-all motion-safe:duration-200 motion-reduce:transition-none"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          <span className="font-semibold tracking-wide text-emerald-100">
            All {villageCount} villages healthy · {connectedSubs}/{totalSubs} connected
          </span>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-emerald-400/90 text-xs">
          <span>Zero active incidents</span>
          <span>·</span>
          <span>Baseline nominal</span>
        </div>
      </aside>
    );
  }

  // ── Active Fault State ───────────────────────────────────────────────────
  const suspected = activeIncident.suspected_component_id || 'Unknown';
  const timeSince = formatElapsed(activeIncident.created_at);
  const householdsText = `${affectedCount} household${affectedCount === 1 ? '' : 's'}`;

  // Monthly revenue at risk from existing business-impact response
  const rawRevenue = impactData?.monthly_revenue_at_risk ?? impactData?.revenue_at_risk;
  const revenueText = formatRevenue(rawRevenue);

  const nextStep = getNextStep(activeIncident, aiReport);

  const isAvailable = Boolean(providerStatus.available);
  const tooltipText = isAvailable
    ? 'Send localized outage notifications to all affected subscribers'
    : providerStatus.reason || 'Outage notification provider is not configured. Set NOTIFICATION_PROVIDER=console or twilio.';

  return (
    <>
      {blindSpotBanner}
      <aside
        data-testid="network-status-banner"
        role="status"
        aria-live="polite"
        aria-label="Network Fault Alert"
        className="w-full bg-gradient-to-r from-[#2a0808] via-[#3d0b0b] to-[#2a0808] border-b-2 border-red-600 px-4 py-2.5 flex flex-col gap-1.5 text-xs text-red-100 shrink-0 select-none shadow-2xl motion-safe:transition-all motion-safe:duration-200 motion-reduce:transition-none"
      >
        {/* Primary fault bar: Beacon, Badges, Metrics, and Action Button */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Animated beacon beacon (respects reduced motion) */}
            <span className="relative flex items-center justify-center w-3 h-3 shrink-0">
              <span className="absolute inline-flex w-full h-full rounded-full bg-red-400 opacity-75 motion-safe:animate-ping motion-reduce:animate-none" />
              <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,1)]" />
            </span>

            {/* Fault Badge */}
            <span className="bg-red-600 text-white font-extrabold text-xs px-2 py-0.5 rounded tracking-wide uppercase shadow-sm">
              FAULT DETECTED
            </span>

            {/* Suspected Link */}
            <span className="text-red-200 font-medium">
              Suspected link{' '}
              <span className="font-mono font-bold text-white bg-red-900/90 border border-red-500 px-1.5 py-0.5 rounded shadow-inner">
                {suspected}
              </span>
            </span>

            <span className="text-red-500 font-bold">·</span>

            {/* Affected Households */}
            <span className="bg-red-950/70 border border-red-700/60 px-2 py-0.5 rounded text-red-200 font-semibold flex items-center gap-1">
              <span>👥</span>
              <span>{householdsText} affected</span>
            </span>

            <span className="text-red-500 font-bold">·</span>

            {/* Monthly Revenue at Risk */}
            <span className="bg-red-950/70 border border-red-700/60 px-2 py-0.5 rounded font-semibold text-amber-300 flex items-center gap-1">
              <span>₹</span>
              <span>{revenueText ? `${revenueText}/mo at risk` : 'Calculating revenue…'}</span>
            </span>

            <span className="text-red-500 font-bold">·</span>

            {/* Outage Duration Timer */}
            <span className="bg-red-950/70 border border-red-700/60 px-2 py-0.5 rounded text-red-200 font-medium flex items-center gap-1">
              <span>⏱</span>
              <span>Outage: {timeSince}</span>
            </span>
          </div>

          {/* Primary Action Button: Notify affected subscribers */}
          <div className="flex items-center">
            <button
              type="button"
              onClick={handleNotify}
              disabled={!isAvailable || notifying}
              title={tooltipText}
              aria-disabled={!isAvailable || notifying}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 shadow-md ${
                notified
                  ? 'bg-emerald-700 text-white cursor-default'
                  : isAvailable
                  ? 'bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-slate-950 cursor-pointer shadow-amber-500/20'
                  : 'bg-slate-800/80 border border-slate-700 text-slate-400 cursor-not-allowed opacity-60'
              }`}
            >
              {notifying ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin shrink-0" />
                  <span>Sending notifications…</span>
                </>
              ) : notified ? (
                <>
                  <span>✓</span>
                  <span>Notifications Sent</span>
                </>
              ) : (
                <>
                  <span>📢</span>
                  <span>Notify affected subscribers</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Short Next step line (from explanation or fault class) */}
        {nextStep && (
          <div className="flex items-center gap-2 text-xs font-medium text-amber-200/95 bg-black/40 border border-amber-500/40 px-2.5 py-1 rounded-md max-w-fit shadow-inner">
            <span className="text-amber-400 font-bold">⚡ Next step:</span>
            <span>{nextStep}</span>
          </div>
        )}
      </aside>
    </>
  );
}

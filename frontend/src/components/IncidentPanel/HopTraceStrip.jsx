import { useMemo } from 'react';
import useStore from '../../store/appStore';
import { buildFailurePath } from '../../lib/hopTrace';

const STATUS_CONFIG = {
  ok: {
    bg: 'bg-emerald-950/70 border-emerald-600/70 text-emerald-300',
    icon: '✓',
    label: 'OK',
    dot: 'bg-emerald-400',
  },
  degraded: {
    bg: 'bg-amber-950/70 border-amber-600/70 text-amber-300',
    icon: '⚠',
    label: 'Degraded',
    dot: 'bg-amber-400',
  },
  failed: {
    bg: 'bg-red-950/80 border-red-500 text-red-200 ring-1 ring-red-500/50',
    icon: '✗',
    label: 'Failed',
    dot: 'bg-red-400 animate-pulse',
  },
  behind_failure: {
    bg: 'bg-slate-900 border-slate-700 text-slate-400',
    icon: '○',
    label: 'Behind Failure',
    dot: 'bg-slate-500',
  },
  no_data: {
    bg: 'bg-slate-900 border-slate-700 text-slate-400',
    icon: '—',
    label: 'No Data',
    dot: 'bg-slate-500',
  },
};

/**
 * HopTraceStrip component displays the active fault boundary path
 * derived from proactive vantage node probes.
 *
 * @param {{ hopTrace?: Array<Object> }} props
 */
export default function HopTraceStrip({ hopTrace = [] }) {
  const topology = useStore((s) => s.topology);

  const { path, behind } = useMemo(() => {
    const topologyLinks = topology?.links || [];
    return buildFailurePath(hopTrace, topologyLinks);
  }, [hopTrace, topology]);

  if (!path || path.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="hop-trace-strip"
      className="p-3 bg-slate-900/90 border border-slate-700/80 rounded-xl space-y-2 text-xs"
      aria-label="Probe Hop Trace Fault Boundary"
    >
      <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-1.5">
        <div className="flex items-center gap-1.5 font-semibold text-slate-200">
          <span>🔍</span>
          <span>Probe Path Trace</span>
        </div>
        <span className="text-[11px] text-slate-400 font-mono">
          Vantage: {path[0]?.node_id || 'GW1'}
        </span>
      </div>

      {/* Path sequence */}
      <div className="flex items-center gap-1.5 flex-wrap overflow-x-auto py-1">
        {path.map((hop, idx) => {
          const cfg = STATUS_CONFIG[hop.status] || STATUS_CONFIG.no_data;
          const isLast = idx === path.length - 1;

          return (
            <div key={`${hop.node_id}-${idx}`} className="flex items-center gap-1.5">
              <div
                className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border font-mono text-xs ${cfg.bg}`}
                title={`Hop ${hop.depth}: ${hop.node_id} (${cfg.label})${
                  hop.packet_loss_pct !== null && hop.packet_loss_pct !== undefined
                    ? ` · Loss: ${hop.packet_loss_pct}%`
                    : ''
                }${
                  hop.latency_ms !== null && hop.latency_ms !== undefined
                    ? ` · RTT: ${hop.latency_ms}ms`
                    : ''
                }`}
              >
                <span className="font-bold">{hop.node_id}</span>
                <span className="text-[11px] font-bold" aria-hidden="true">
                  {cfg.icon}
                </span>
                <span className="sr-only">({cfg.label})</span>
              </div>

              {!isLast && (
                <span className="text-slate-500 font-bold select-none text-xs">
                  &rarr;
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Behind failure informational notice */}
      {behind && behind.length > 0 && (
        <div
          data-testid="nodes-behind-failure"
          className="text-[11px] text-slate-400 pt-1 border-t border-slate-800/80 flex items-start gap-1"
        >
          <span className="text-slate-500">↳</span>
          <span>
            <strong className="text-slate-300 font-medium">
              {behind.length} node{behind.length === 1 ? '' : 's'} behind failure (not blamed):
            </strong>{' '}
            <span className="font-mono text-slate-300">{behind.join(', ')}</span>
          </span>
        </div>
      )}
    </div>
  );
}

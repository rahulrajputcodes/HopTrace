import { useState, useEffect } from 'react';
import useStore from '../../store/appStore';
import { useApi } from '../../hooks/useApi';
import HopTraceStrip from './HopTraceStrip';

const SEV_COLORS = {
  critical: 'bg-red-900 border-red-600 text-red-300',
  high:     'bg-orange-900 border-orange-600 text-orange-300',
  medium:   'bg-amber-900 border-amber-600 text-amber-300',
  low:      'bg-blue-900 border-blue-600 text-blue-300',
};



const DISPATCH_SOP = {
  fiber_cut: {
    target: 'Optical Splicer Crew (Block HQ)',
    etr: '~3.5 Hours',
    tools: 'OTDR & Fusion Splicer',
    procedure: 'Shoot OTDR from GW1 to locate physical break distance along Right-of-Way; dispatch linesman for optical re-splice.',
  },
  power_outage: {
    target: 'Village Linesman / Site Custodian',
    etr: '~45 Minutes',
    tools: 'Multimeter & Battery/Generator Jump',
    procedure: 'Verify grid mains at Gram Panchayat tower; test 24V/48V UPS battery bank and reset PoE injectors.',
  },
  rf_degradation: {
    target: 'Tower Rigging Crew',
    etr: '~1.5 Hours',
    tools: 'RSSI Spectrum Analyzer & Alignment Kit',
    procedure: 'Inspect dish bracket azimuth/elevation; clear line-of-sight foliage in 60% Fresnel clearance zone.',
  },
  upstream_failure: {
    target: 'Tier-1 ISP NOC Escalation (Remote)',
    etr: 'Upstream Transit Dependent',
    tools: 'NOC BGP Ticket Terminal',
    procedure: 'Do not dispatch local field technicians; escalate urgent P1 incident to upstream transit provider NOC.',
  },
  unknown: {
    target: 'Vantage Point Probe Triage',
    etr: 'Under Investigation',
    tools: 'Remote Probe & Syslog Terminal',
    procedure: 'Run vantage probe trace from GW1; inspect radio interface error logs and power supply continuity.',
  },
};

const CAUSE_META = {
  fiber_cut: {
    label: 'Fibre cut',
    badgeClass: 'bg-rose-950/80 border-rose-600/80 text-rose-300',
    icon: '✂️',
  },
  power_outage: {
    label: 'Likely power outage',
    badgeClass: 'bg-amber-950/80 border-amber-600/80 text-amber-300',
    icon: '⚡',
  },
  rf_degradation: {
    label: 'Radio link degradation',
    badgeClass: 'bg-yellow-950/80 border-yellow-600/80 text-yellow-300',
    icon: '📡',
  },
  upstream_failure: {
    label: 'Upstream failure',
    badgeClass: 'bg-purple-950/80 border-purple-600/80 text-purple-300',
    icon: '🌐',
  },
  unknown: {
    label: 'Cause undetermined',
    badgeClass: 'bg-slate-800 border-slate-700 text-slate-400',
    icon: '❓',
  },
};

const FAULT_CLASS_META = {
  upstream: { label: 'Upstream Failure', icon: '🔴', color: 'text-red-400' },
  cascade:  { label: 'Cascade Fault',    icon: '💥', color: 'text-orange-400' },
  isolated: { label: 'Isolated Fault',   icon: '🔵', color: 'text-blue-400' },
  flapping: { label: 'Flapping Link',    icon: '〰', color: 'text-purple-400' },
  unknown:  { label: 'Unknown Fault',    icon: '❓', color: 'text-slate-400' },
};

function parseFaultClass(summary) {
  if (!summary) return 'unknown';
  if (summary.startsWith('[upstream]')) return 'upstream';
  if (summary.startsWith('[cascade]'))  return 'cascade';
  if (summary.startsWith('[isolated]')) return 'isolated';
  if (summary.startsWith('[flapping]')) return 'flapping';
  return 'unknown';
}

function useElapsedTime(createdAt) {
  const [elapsed, setElapsed] = useState('');
  useEffect(() => {
    if (!createdAt) return;
    const update = () => {
      const diff = Math.floor((Date.now() - new Date(createdAt)) / 1000);
      if (diff < 60)        setElapsed(`${diff}s ago`);
      else if (diff < 3600) setElapsed(`${Math.floor(diff / 60)}m ago`);
      else                  setElapsed(`${Math.floor(diff / 3600)}h ago`);
    };
    update();
    const t = setInterval(update, 5000);
    return () => clearInterval(t);
  }, [createdAt]);
  return elapsed;
}

function EvidenceItem({ ev }) {
  const sev = ev.severity || 'medium';
  const col = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#3b82f6' }[sev] || '#64748b';
  return (
    <div className="flex items-start gap-2 px-3 py-2 bg-slate-900/60 rounded-lg border border-slate-800">
      <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0" style={{ background: col }} />
      <div className="min-w-0 flex-1">
        <div className="text-xs text-slate-300 font-medium">{ev.metric || ev.description}</div>
        {ev.observed !== undefined && (
          <div className="text-xs text-slate-500 mt-0.5">
            Observed: <span className="text-slate-300">{typeof ev.observed === 'number' ? ev.observed.toFixed(1) : ev.observed}</span>
            {ev.baseline !== undefined && (
              <> · Baseline: <span className="text-slate-400">{typeof ev.baseline === 'number' ? ev.baseline.toFixed(1) : ev.baseline}</span></>
            )}
          </div>
        )}
      </div>
      <span
        className="text-xs font-semibold uppercase px-1.5 py-0.5 rounded border shrink-0"
        style={{ color: col, borderColor: col + '55', background: col + '11' }}
      >
        {sev}
      </span>
    </div>
  );
}

export default function IncidentPanel() {
  const activeIncident = useStore(s => s.activeIncident);
  const affectedSubscribers = useStore(s => s.affectedSubscribers);
  const aiLoading = useStore(s => s.aiLoading);
  const aiReport = useStore(s => s.aiReport);
  const sarvamLanguage = useStore(s => s.sarvamLanguage);
  const { explainIncident } = useApi();
  const [explainError, setExplainError] = useState(null);

  const elapsed = useElapsedTime(activeIncident?.created_at);

  if (!activeIncident) {
    return null;
  }

  const faultClass = parseFaultClass(activeIncident.summary);
  const faultMeta = FAULT_CLASS_META[faultClass];
  const severity = activeIncident.severity || 'medium';
  const confidence = Math.round((activeIncident.confidence_score || 0.9) * 100);
  const evidence = Array.isArray(activeIncident.evidence) ? activeIncident.evidence : [];

  // Group affected subscribers by village
  const byVillage = {};
  (affectedSubscribers || []).forEach(s => {
    const v = s.village || 'Unknown';
    if (!byVillage[v]) byVillage[v] = [];
    byVillage[v].push(s);
  });

  const handleExplain = async () => {
    setExplainError(null);
    try {
      await explainIncident(activeIncident.id, sarvamLanguage);
    } catch (err) {
      const msg = err?.message || '';
      if (msg.includes('503') || msg.toLowerCase().includes('not configured')) {
        setExplainError('AI explanation unavailable — not configured on server');
      } else {
        setExplainError(msg || 'AI explanation unavailable');
      }
    }
  };

  return (
    <div className="bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      {/* Header */}
      <div className={`px-4 py-3 border-b border-slate-800 flex items-start gap-3 ${
        severity === 'critical' ? 'bg-red-950/30' : 'bg-orange-950/20'
      }`}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded border ${SEV_COLORS[severity] || SEV_COLORS.medium}`}>
              {severity}
            </span>
            <span className={`text-sm font-bold ${faultMeta.color}`}>
              {faultMeta.icon} {faultMeta.label}
            </span>
            <span className="text-slate-400 text-xs">{elapsed}</span>
          </div>
          <div className="text-white font-semibold text-sm mt-1 truncate">
            Component: <span className="text-amber-300">{activeIncident.suspected_component_id || '—'}</span>
          </div>
          <div className="text-slate-400 text-xs mt-0.5 line-clamp-2">
            {(activeIncident.summary || '').replace(/^\[.*?\]\s*/, '') || 'Network anomaly detected'}
          </div>

          {/* Deterministic Root Cause Chip & Reasoning */}
          {activeIncident.cause && (
            <div className="mt-2 pt-2 border-t border-slate-700/60">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  data-testid="cause-chip"
                  className={`px-2 py-0.5 rounded-full border text-xs font-semibold flex items-center gap-1.5 ${
                    (CAUSE_META[activeIncident.cause] || CAUSE_META.unknown).badgeClass
                  }`}
                >
                  <span>{(CAUSE_META[activeIncident.cause] || CAUSE_META.unknown).icon}</span>
                  <span>{(CAUSE_META[activeIncident.cause] || CAUSE_META.unknown).label}</span>
                </span>
                {typeof activeIncident.cause_confidence === 'number' && (
                  <span className="text-[11px] text-slate-300 font-mono">
                    {Math.round(activeIncident.cause_confidence * 100)}% confidence
                  </span>
                )}
              </div>
              {Array.isArray(activeIncident.cause_reasoning) && activeIncident.cause_reasoning.length > 0 && (
                <ul className="mt-1.5 space-y-0.5 text-xs text-slate-300 pl-4 list-disc marker:text-slate-500">
                  {activeIncident.cause_reasoning.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}

              {/* Actionable Field Dispatch SOP */}
              {(() => {
                const sop = DISPATCH_SOP[activeIncident.cause] || DISPATCH_SOP.unknown;
                return (
                  <div className="mt-2.5 p-2 bg-slate-900/90 border border-slate-700/80 rounded-lg space-y-1 text-xs">
                    <div className="flex items-center justify-between text-slate-200 font-semibold border-b border-slate-800 pb-1">
                      <span className="flex items-center gap-1.5 text-sky-400">
                        <span>🛠️</span>
                        <span>Field SOP & Dispatch</span>
                      </span>
                      <span className="text-[11px] font-mono text-amber-400">
                        Est. Restore: {sop.etr}
                      </span>
                    </div>
                    <div className="text-slate-300 text-xs">
                      <strong className="text-slate-400 font-medium">Crew:</strong> {sop.target}
                    </div>
                    <div className="text-slate-300 text-xs">
                      <strong className="text-slate-400 font-medium">Tools:</strong> {sop.tools}
                    </div>
                    <div className="text-slate-400 text-[11px] italic mt-0.5">
                      {sop.procedure}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
        <div className="shrink-0 text-right">
          <div className="text-white font-bold text-lg">{confidence}%</div>
          <div className="text-slate-500 text-xs">Confidence</div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 max-h-72">
        {/* Hop Trace Strip (proactive vantage probe fault boundary) */}
        {Array.isArray(activeIncident.hop_trace) && activeIncident.hop_trace.length > 0 && (
          <HopTraceStrip hopTrace={activeIncident.hop_trace} />
        )}

        {/* Evidence chain */}
        {evidence.length > 0 && (
          <div>
            <div className="text-xs text-slate-500 font-medium uppercase mb-1.5">
              Evidence Chain ({evidence.length})
            </div>
            <div className="space-y-1.5">
              {evidence.slice(0, 5).map((ev, i) => <EvidenceItem key={i} ev={ev} />)}
            </div>
          </div>
        )}

        {/* Affected subscribers */}
        {affectedSubscribers.length > 0 && (
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 font-medium uppercase mb-1.5">
              <span>Affected Subscribers ({affectedSubscribers.length})</span>
              {affectedSubscribers.some(s => s.is_essential) && (
                <span className="text-emerald-400 font-bold lowercase tracking-normal text-[11px]">
                  ({affectedSubscribers.filter(s => s.is_essential).length} essential services)
                </span>
              )}
            </div>
            {Object.entries(byVillage).map(([village, subs]) => (
              <div key={village} className="mb-2">
                <div className="text-xs text-slate-400 mb-1 font-semibold">{village}</div>
                <div className="flex flex-wrap gap-1.5">
                  {subs.map(s => (
                    <div
                      key={s.id}
                      className={`px-2 py-1 rounded-lg text-xs flex items-center gap-1.5 border ${
                        s.is_essential
                          ? 'bg-emerald-950/70 border-emerald-600/80 text-emerald-200 font-medium'
                          : 'bg-red-950/40 border-red-800/50 text-red-300'
                      }`}
                    >
                      {s.is_essential && <span className="text-[11px]" title="Essential Public Service">🏥</span>}
                      <span>{s.display_name || s.id}</span>
                      <span className={s.is_essential ? 'text-emerald-400 font-mono text-[10px]' : 'text-red-500 font-mono text-[10px]'}>
                        ({s.is_essential ? 'Essential' : s.plan})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Friendly 503 error state */}
        {explainError && (
          <div className="p-3 bg-slate-900 border border-slate-700/80 rounded-lg text-xs text-slate-300 flex items-center gap-2">
            <span className="text-amber-400">ℹ</span>
            <span>{explainError}</span>
          </div>
        )}

        {/* AI Report preview */}
        {aiReport && !aiLoading && (
          <div className="p-3 bg-purple-950/30 border border-purple-800/50 rounded-lg">
            <div className="text-xs text-purple-400 font-medium uppercase mb-1.5">Sarvam AI Analysis</div>
            {typeof aiReport === 'object' ? (
              <div className="space-y-1.5 text-xs">
                {aiReport.executive_summary && (
                  <p className="text-slate-200 font-medium">{aiReport.executive_summary}</p>
                )}
                {aiReport.field_operator_steps && (
                  <div className="text-slate-400">
                    <div className="text-xs text-slate-500 mb-0.5">Field Steps:</div>
                    {Array.isArray(aiReport.field_operator_steps)
                      ? aiReport.field_operator_steps.slice(0, 3).map((s, i) => <div key={i}>• {s}</div>)
                      : <div>{aiReport.field_operator_steps}</div>}
                  </div>
                )}
                {aiReport.eta && (
                  <div className="text-emerald-400 text-xs">ETA: {aiReport.eta}</div>
                )}
              </div>
            ) : (
              <p className="text-slate-300 text-xs whitespace-pre-line line-clamp-6">{aiReport}</p>
            )}
          </div>
        )}
      </div>

      {/* Explain button */}
      <div className="px-3 pb-3 pt-1 border-t border-slate-800">
        <button
          onClick={handleExplain}
          disabled={aiLoading}
          className="w-full py-2 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {aiLoading ? (
            <>
              <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Generating AI Analysis...
            </>
          ) : (
            `🤖 Explain in ${sarvamLanguage.toUpperCase()} via Sarvam AI`
          )}
        </button>
      </div>
    </div>
  );
}

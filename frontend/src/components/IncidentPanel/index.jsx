import { useState, useEffect } from 'react';
import useStore from '../../store/appStore';
import { useApi } from '../../hooks/useApi';

const SEV_COLORS = {
  critical: 'bg-red-900 border-red-600 text-red-300',
  high:     'bg-orange-900 border-orange-600 text-orange-300',
  medium:   'bg-amber-900 border-amber-600 text-amber-300',
  low:      'bg-blue-900 border-blue-600 text-blue-300',
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
  const sarvamApiKey = useStore(s => s.sarvamApiKey);
  const { explainIncident } = useApi();

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

  const handleExplain = () => {
    explainIncident(activeIncident.id, sarvamLanguage, sarvamApiKey);
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
        </div>
        <div className="shrink-0 text-right">
          <div className="text-white font-bold text-lg">{confidence}%</div>
          <div className="text-slate-500 text-xs">Confidence</div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 max-h-72">
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
            <div className="text-xs text-slate-500 font-medium uppercase mb-1.5">
              Affected Subscribers ({affectedSubscribers.length})
            </div>
            {Object.entries(byVillage).map(([village, subs]) => (
              <div key={village} className="mb-2">
                <div className="text-xs text-slate-500 mb-1">{village}</div>
                <div className="flex flex-wrap gap-1.5">
                  {subs.map(s => (
                    <div key={s.id} className="px-2 py-1 bg-red-950/40 border border-red-800/50 rounded-lg text-xs text-red-300">
                      {s.display_name || s.id}
                      <span className="text-red-500 ml-1">({s.plan})</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
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

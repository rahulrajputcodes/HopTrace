import { useState } from 'react';
import { useApi } from '../../hooks/useApi';
import useStore from '../../store/appStore';

const PRESETS = [
  { label: 'Baseline Restore', icon: '✓', scenario: 'baseline', target_link_id: null, severity: 'low', color: 'emerald' },
  { label: 'Degrade L3 High', icon: '⚡', scenario: 'degrade_link', target_link_id: 'L3', severity: 'high', color: 'amber' },
  { label: 'Cascade Fault', icon: '💥', scenario: 'cascade_fault', target_link_id: 'L3', severity: 'high', color: 'red' },
  { label: 'Upstream Failure', icon: '🔴', scenario: 'degrade_link', target_link_id: 'L1', severity: 'critical', color: 'red' },
  { label: 'Flapping L7', icon: '〰', scenario: 'flapping_link', target_link_id: 'L7', severity: 'medium', color: 'purple' },
  { label: 'Degrade AP Branch', icon: '📡', scenario: 'degrade_link', target_link_id: 'L5', severity: 'medium', color: 'amber' },
];

const SCENARIOS = ['baseline', 'degrade_link', 'degrade_node', 'cascade_fault', 'flapping_link'];
const SEVERITIES = ['low', 'medium', 'high', 'critical'];
const LINK_IDS = ['L1','L2','L3','L4','L5','L6','L7','L8','L9','L10','L11','L12','L13','L14'];

const PRESET_COLORS = {
  emerald: 'border-emerald-700 bg-emerald-950/80 text-emerald-300 hover:bg-emerald-900',
  amber: 'border-amber-700 bg-amber-950/80 text-amber-300 hover:bg-amber-900',
  red: 'border-red-700 bg-red-950/80 text-red-300 hover:bg-red-900',
  purple: 'border-purple-700 bg-purple-950/80 text-purple-300 hover:bg-purple-900',
};

export default function LabPanel() {
  const [collapsed, setCollapsed] = useState(true);
  const [scenario, setScenario] = useState('degrade_link');
  const [targetLinkId, setTargetLinkId] = useState('L3');
  const [severity, setSeverity] = useState('high');
  const [history, setHistory] = useState([]);
  const [running, setRunning] = useState(null);
  const loading = useStore(s => s.loading);
  const { runScenario } = useApi();

  const execute = async (payload, label) => {
    setRunning(label);
    try {
      const result = await runScenario(payload);
      setHistory(prev => [
        { label, ts: new Date().toLocaleTimeString(), status: result?.incident ? 'incident' : 'ok', result },
        ...prev.slice(0, 4),
      ]);
    } catch (e) {
      setHistory(prev => [
        { label, ts: new Date().toLocaleTimeString(), status: 'error', result: { error: e.message } },
        ...prev.slice(0, 4),
      ]);
    } finally {
      setRunning(null);
    }
  };

  const handlePreset = (p) => {
    const payload = { scenario: p.scenario, severity: p.severity };
    if (p.target_link_id) payload.target_link_id = p.target_link_id;
    execute(payload, p.label);
  };

  const handleCustomRun = () => {
    const payload = { scenario, severity, target_link_id: targetLinkId };
    execute(payload, `Custom: ${scenario}/${targetLinkId}`);
  };

  return (
    <div className="bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden transition-colors">
      <button
        type="button"
        onClick={() => setCollapsed(c => !c)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-800/40 transition-colors"
        aria-expanded={!collapsed}
      >
        <div className="flex items-center gap-2">
          <span className="text-blue-400 text-sm">🔬</span>
          <span className="text-white font-semibold text-sm">Demo controls</span>
          <span className="text-xs text-slate-500">— Quick scenario injection</span>
        </div>
        <span className="text-slate-400 text-xs font-medium">
          {collapsed ? '▾ Expand' : '▴ Collapse'}
        </span>
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 pt-1 space-y-3 border-t border-slate-800/60">
          {/* Compact toolbar of small buttons */}
          <div className="flex flex-wrap items-center gap-2" role="toolbar" aria-label="Demo scenarios toolbar">
            {PRESETS.map(p => (
              <button
                key={p.label}
                type="button"
                onClick={() => handlePreset(p)}
                disabled={!!running || loading}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-colors disabled:opacity-50 whitespace-nowrap shadow-sm ${PRESET_COLORS[p.color]}`}
              >
                <span>{p.icon}</span>
                <span>{p.label}</span>
                {running === p.label && <span className="text-xs opacity-70 animate-pulse">…</span>}
              </button>
            ))}
          </div>

          {/* Advanced section with custom builder dropdowns */}
          <details className="group border border-slate-800 rounded-lg bg-slate-900/40">
            <summary className="px-3 py-2 text-xs text-slate-400 font-semibold cursor-pointer hover:text-slate-200 select-none flex items-center justify-between">
              <span>⚙ Advanced</span>
              <span className="text-slate-500 group-open:rotate-180 transition-transform">▾</span>
            </summary>
            <div className="p-3 pt-1 border-t border-slate-800/60 flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1 min-w-[140px]">
                <label className="text-xs text-slate-400 font-medium uppercase">Scenario</label>
                <select
                  value={scenario}
                  onChange={e => setScenario(e.target.value)}
                  className="bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                >
                  {SCENARIOS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1 min-w-[100px]">
                <label className="text-xs text-slate-400 font-medium uppercase">Link Target</label>
                <select
                  value={targetLinkId}
                  onChange={e => setTargetLinkId(e.target.value)}
                  className="bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                >
                  {LINK_IDS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1 min-w-[100px]">
                <label className="text-xs text-slate-400 font-medium uppercase">Severity</label>
                <select
                  value={severity}
                  onChange={e => setSeverity(e.target.value)}
                  className="bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                >
                  {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <button
                type="button"
                onClick={handleCustomRun}
                disabled={!!running || loading}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50 self-end"
              >
                ▶ Run Scenario
              </button>
            </div>
          </details>

          {/* Run history */}
          {history.length > 0 && (
            <div className="space-y-1 pt-1">
              <div className="text-xs text-slate-400 font-semibold uppercase mb-1">Recent Runs</div>
              {history.map((h, i) => (
                <div key={i} className="flex items-center gap-3 text-xs px-3 py-1.5 bg-slate-900 rounded-lg">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${h.status === 'incident' ? 'bg-amber-400' : h.status === 'ok' ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  <span className="text-slate-300 font-medium">{h.label}</span>
                  <span className="text-slate-500 flex-1">{h.result?.incident ? `→ ${h.result.incident.suspected_component_id}` : h.status}</span>
                  <span className="text-slate-500">{h.ts}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { useApi } from '../../hooks/useApi';
import useStore from '../../store/appStore';

const LINK_IDS = ['L1','L2','L3','L4','L5','L6','L7','L8','L9','L10','L11','L12','L13','L14'];

const METRICS = [
  { key: 'latency_ms',      ewmaKey: 'ewma_latency',    label: 'Latency (ms)',      color: '#3b82f6', unit: 'ms'   },
  { key: 'packet_loss_pct', ewmaKey: 'ewma_loss',       label: 'Packet Loss (%)',   color: '#ef4444', unit: '%'    },
  { key: 'throughput_mbps', ewmaKey: 'ewma_throughput', label: 'Throughput (Mbps)', color: '#10b981', unit: 'Mbps' },
];

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <div className="text-slate-400 mb-1">Tick {label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color }} className="flex items-center gap-2">
          <span className="font-medium">{p.name}:</span>
          <span>{typeof p.value === 'number' ? p.value.toFixed(2) : p.value}{unit}</span>
        </div>
      ))}
    </div>
  );
}

function RiskGauge({ value }) {
  const clamp = Math.min(100, Math.max(0, value || 0));
  const color = clamp >= 80 ? '#ef4444' : clamp >= 60 ? '#f97316' : clamp >= 40 ? '#f59e0b' : '#10b981';
  const pct = clamp / 100;
  const circumference = 141.3;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="text-xs text-slate-400 uppercase font-semibold text-center whitespace-nowrap">
        Risk score / 100
      </div>
      <div className="relative w-24 h-14">
        <svg viewBox="0 0 100 60" className="w-full h-full">
          <path d="M10 55 A45 45 0 0 1 90 55" fill="none" stroke="#1e293b" strokeWidth="8" strokeLinecap="round"/>
          <path
            d="M10 55 A45 45 0 0 1 90 55"
            fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
            strokeDasharray={`${pct * circumference} ${circumference}`}
          />
        </svg>
        <div className="absolute inset-0 flex items-end justify-center pb-1">
          <span className="text-lg font-bold" style={{ color }}>{clamp.toFixed(0)}</span>
        </div>
      </div>
    </div>
  );
}

export default function TelemetryCharts() {
  const [selectedLink, setSelectedLink] = useState('L3');
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const riskSnapshot = useStore(s => s.riskSnapshot);
  const liveMeasurements = useStore(s => s.liveMeasurements);
  const { fetchLinkHistory } = useApi();

  const currentRisk = riskSnapshot[selectedLink]?.risk_score
    ?? liveMeasurements.find(m => m.link_id === selectedLink)?.risk_score
    ?? 0;

  const liveTick = liveMeasurements.find(m => m.link_id === selectedLink);

  const loadHistory = useCallback(async (linkId) => {
    setLoading(true);
    try {
      const data = await fetchLinkHistory(linkId, 50);
      setSamples((data.samples || []).map((s, i) => ({ ...s, tick: i + 1 })));
    } catch {
      setSamples([]);
    } finally {
      setLoading(false);
    }
  }, [fetchLinkHistory]);

  useEffect(() => {
    let ignore = false;
    fetchLinkHistory(selectedLink, 50)
      .then((data) => {
        if (!ignore) {
          setSamples((data.samples || []).map((s, i) => ({ ...s, tick: i + 1 })));
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setSamples([]);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [selectedLink, fetchLinkHistory]);

  // Re-fetch on each live tick to keep charts current
  const liveTick_latency = liveTick?.latency_ms;
  useEffect(() => {
    if (liveTick_latency === undefined) return;
    let ignore = false;
    fetchLinkHistory(selectedLink, 50)
      .then((data) => {
        if (!ignore) {
          setSamples((data.samples || []).map((s, i) => ({ ...s, tick: i + 1 })));
        }
      })
      .catch(() => {});
    return () => {
      ignore = true;
    };
  }, [liveTick_latency, selectedLink, fetchLinkHistory]);

  return (
    <div className="bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
        <span className="text-blue-400 text-sm">📈</span>
        <span className="text-white font-semibold text-sm">Telemetry History</span>
        <select
          value={selectedLink}
          onChange={e => setSelectedLink(e.target.value)}
          className="ml-auto bg-slate-800 border border-slate-600 text-slate-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-blue-500"
        >
          {LINK_IDS.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <button
          onClick={() => loadHistory(selectedLink)}
          disabled={loading}
          className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded transition-colors disabled:opacity-50"
        >
          {loading ? '↻' : '⟳'}
        </button>
      </div>

      <div className="p-3">
        {samples.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-slate-500 text-xs">
            {loading ? 'Loading history...' : 'No telemetry data yet — run a scenario or wait for WS data'}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Risk gauge + live values */}
            <div className="flex items-center gap-4 px-2">
              <RiskGauge value={currentRisk} />
              {liveTick && (
                <div className="flex-1 grid grid-cols-3 gap-2">
                  {[
                    ['Latency', `${(liveTick.latency_ms || 0).toFixed(1)}ms`, '#3b82f6'],
                    ['Loss',    `${(liveTick.packet_loss_pct || 0).toFixed(1)}%`, '#ef4444'],
                    ['Throughput', `${(liveTick.throughput_mbps || 0).toFixed(1)}`, '#10b981'],
                  ].map(([label, val, color]) => (
                    <div key={label} className="flex flex-col items-center p-2 bg-slate-900 rounded-lg">
                      <span className="text-xs font-medium text-slate-400">{label}</span>
                      <span className="text-base font-bold" style={{ color }}>{val}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Per-metric area charts */}
            {METRICS.map(m => (
              <div key={m.key}>
                <div className="text-xs text-slate-400 font-medium mb-1">{m.label}</div>
                <ResponsiveContainer width="100%" height={60}>
                  <AreaChart data={samples} margin={{ top: 2, right: 4, left: -22, bottom: 0 }}>
                    <defs>
                      <linearGradient id={`grad-${m.key}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={m.color} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={m.color} stopOpacity={0.02}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="2 4" stroke="#1e293b" vertical={false}/>
                    <XAxis dataKey="tick" hide/>
                    <YAxis tick={{ fontSize: 12, fill: '#64748b' }} width={34}/>
                    <Tooltip content={<CustomTooltip unit={m.unit}/>}/>
                    <Area
                      type="monotone" dataKey={m.key} name="Raw"
                      stroke={m.color} strokeWidth={1.5}
                      fill={`url(#grad-${m.key})`} dot={false} isAnimationActive={false}
                    />
                    {samples[0]?.[m.ewmaKey] !== undefined && (
                      <Area
                        type="monotone" dataKey={m.ewmaKey} name="EWMA"
                        stroke={m.color} strokeWidth={2} strokeDasharray="4 2"
                        fill="none" dot={false} isAnimationActive={false} strokeOpacity={0.6}
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

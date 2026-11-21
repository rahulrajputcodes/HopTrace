import { useEffect, useState } from 'react';
import useStore from './store/appStore';
import { useLiveTelemetry } from './hooks/useLiveTelemetry';
import { useApi } from './hooks/useApi';

import TopBar from './components/TopBar';
import KPIRibbon from './components/KPIRibbon';
import NetworkView from './components/NetworkView';
import IncidentPanel from './components/IncidentPanel';
import AIExplanationCard from './components/AIExplanationCard';
import TelemetryCharts from './components/TelemetryCharts';
import SubscriberOps from './components/SubscriberOps';
import LabPanel from './components/LabPanel';
import SarvamKeyModal from './components/SarvamKeyModal';
import ToastStack from './components/ToastStack';

export default function App() {
  useLiveTelemetry();

  const { fetchAll } = useApi();
  const [sarvamOpen, setSarvamOpen] = useState(false);
  const selectedElement = useStore(s => s.selectedElement);
  const setSelectedElement = useStore(s => s.setSelectedElement);

  useEffect(() => {
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-[#050d1a] text-slate-200 flex flex-col overflow-hidden" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* ── Top Bar ──────────────────────────────────────────────────── */}
      <TopBar onOpenSarvam={() => setSarvamOpen(true)} onRefresh={fetchAll} />

      {/* ── KPI Ribbon ───────────────────────────────────────────────── */}
      <KPIRibbon />

      {/* ── Main Grid ────────────────────────────────────────────────── */}
      <main className="flex-1 grid grid-cols-12 gap-2.5 p-2.5 min-h-0 overflow-y-auto">

        {/* Left: Topology Canvas (large) */}
        <section className="col-span-12 lg:col-span-8 flex flex-col gap-2.5 min-h-0">
          <div
            className="flex-1 relative"
            style={{ minHeight: 480 }}
          >
            {/* Card wrapper */}
            <div className="absolute inset-0 bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden flex flex-col">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-800 shrink-0">
                <span className="text-blue-400 text-sm">🌐</span>
                <span className="text-white font-semibold text-sm">Network Topology</span>
                <span className="text-slate-500 text-xs">— 15 nodes · 3 villages · Real-time risk heatmap</span>
              </div>
              <div className="flex-1 min-h-0">
                <NetworkView />
              </div>
            </div>
          </div>

          {/* Lab Panel below topology */}
          <LabPanel />
        </section>

        {/* Right panel: Incident + AI + Charts */}
        <section className="col-span-12 lg:col-span-4 flex flex-col gap-2.5 min-h-0">
          <IncidentPanel />
          <AIExplanationCard />
          <TelemetryCharts />
        </section>

        {/* Full-width: Subscriber Ops */}
        <section className="col-span-12">
          <SubscriberOps />
        </section>
      </main>

      {/* ── Selected Element Drawer ───────────────────────────────────── */}
      {selectedElement && (
        <div
          className="fixed inset-0 z-40 flex items-end sm:items-center justify-end pointer-events-none"
        >
          <div
            className="pointer-events-auto w-full sm:w-96 bg-[#0d1829] border border-slate-700 rounded-t-2xl sm:rounded-2xl sm:mr-4 shadow-2xl overflow-hidden"
            style={{ maxHeight: '70vh' }}
          >
            {/* Drawer header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-800/50">
              <div className="flex items-center gap-2">
                <span className="text-blue-400">{selectedElement.type === 'node' ? '🖥' : '🔗'}</span>
                <span className="text-white font-semibold text-sm capitalize">
                  {selectedElement.type}: {selectedElement.id}
                </span>
              </div>
              <button
                onClick={() => setSelectedElement(null)}
                className="text-slate-400 hover:text-white text-xl leading-none"
              >
                ✕
              </button>
            </div>

            {/* Drawer body */}
            <div className="p-4 overflow-y-auto space-y-2 text-xs">
              {selectedElement.data && Object.entries(selectedElement.data).map(([k, v]) => (
                v !== null && v !== undefined && typeof v !== 'object' ? (
                  <div key={k} className="flex gap-2">
                    <span className="text-slate-500 font-medium w-32 shrink-0 capitalize">{k.replace(/_/g, ' ')}</span>
                    <span className="text-slate-200 break-all">{String(v)}</span>
                  </div>
                ) : null
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Sarvam Key Modal ──────────────────────────────────────────── */}
      {sarvamOpen && <SarvamKeyModal onClose={() => setSarvamOpen(false)} />}

      {/* ── Toast Stack ───────────────────────────────────────────────── */}
      <ToastStack />
    </div>
  );
}

import { create } from 'zustand';

const useStore = create((set, get) => ({
  // ── Backend connection ──────────────────────────────────────────────────
  backendOnline: false,
  wsConnected: false,
  setBackendOnline: (v) => set({ backendOnline: v }),
  setWsConnected: (v) => set({ wsConnected: v }),

  // ── Topology ────────────────────────────────────────────────────────────
  topology: { nodes: [], links: [], data_source: 'loading' },
  setTopology: (t) => set({ topology: t }),

  // ── Live telemetry ──────────────────────────────────────────────────────
  liveMeasurements: [],        // [{link_id, latency_ms, packet_loss_pct, throughput_mbps, connectivity_ok, risk_score, trend, alert_level}]
  lastTick: 0,
  networkStatus: 'healthy',   // healthy | degraded | critical
  cascadeDetected: false,
  flappingLinks: [],
  setLiveTelemetry: (payload) => {
    const hasActiveIncident = 'active_incident' in payload;
    const nextActiveIncident = hasActiveIncident ? payload.active_incident : get().activeIncident;
    const shouldClearAffected = hasActiveIncident && payload.active_incident === null;

    set({
      liveMeasurements: payload.measurements || [],
      lastTick: payload.tick || 0,
      networkStatus: payload.network_status || 'healthy',
      cascadeDetected: payload.cascade_detected || false,
      flappingLinks: payload.flapping_links || [],
      activeIncident: nextActiveIncident,
      ...(shouldClearAffected ? { affectedSubscribers: [] } : {}),
    });
  },

  // ── Risk snapshot ───────────────────────────────────────────────────────
  riskSnapshot: {},   // { link_id -> risk_score }
  setRiskSnapshot: (snap) => {
    const map = {};
    (snap || []).forEach(r => { map[r.link_id] = r; });
    set({ riskSnapshot: map });
  },

  // ── Incident ────────────────────────────────────────────────────────────
  activeIncident: null,
  setActiveIncident: (inc) => set({ activeIncident: inc }),

  // ── Affected subscribers ────────────────────────────────────────────────
  affectedSubscribers: [],
  setAffectedSubscribers: (subs) => set({ affectedSubscribers: subs }),

  // ── All subscribers ─────────────────────────────────────────────────────
  allSubscribers: [],
  setAllSubscribers: (subs) => set({ allSubscribers: subs }),

  // ── Villages ────────────────────────────────────────────────────────────
  villages: [],
  setVillages: (v) => set({ villages: v }),

  // ── AI explanation ──────────────────────────────────────────────────────
  aiReport: null,
  aiLoading: false,
  setAiReport: (r) => set({ aiReport: r }),
  setAiLoading: (v) => set({ aiLoading: v }),

  // ── Audio playback ──────────────────────────────────────────────────────
  isPlayingAudio: false,
  setIsPlayingAudio: (v) => set({ isPlayingAudio: v }),

  // ── Sarvam config ───────────────────────────────────────────────────────
  sarvamApiKey: localStorage.getItem('ht_sarvam_key') || '',
  sarvamLanguage: 'hi',
  sarvamSpeaker: 'meera',
  setSarvamKey: (k) => { localStorage.setItem('ht_sarvam_key', k); set({ sarvamApiKey: k }); },
  setSarvamLanguage: (l) => set({ sarvamLanguage: l }),
  setSarvamSpeaker: (s) => set({ sarvamSpeaker: s }),

  // ── Selected element (topology click) ───────────────────────────────────
  selectedElement: null,
  setSelectedElement: (el) => set({ selectedElement: el }),

  // ── UI mode ─────────────────────────────────────────────────────────────
  dashboardMode: localStorage.getItem('ht_mode') || 'noc',  // noc | business
  setDashboardMode: (m) => { localStorage.setItem('ht_mode', m); set({ dashboardMode: m }); },

  // ── Toast ───────────────────────────────────────────────────────────────
  toasts: [],
  addToast: (msg, type = 'info') => {
    const id = Date.now();
    set(s => ({ toasts: [...s.toasts, { id, msg, type }] }));
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), 3500);
  },

  // ── Loading ─────────────────────────────────────────────────────────────
  loading: false,
  setLoading: (v) => set({ loading: v }),
}));

export default useStore;

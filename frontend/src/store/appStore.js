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
  liveMeasurements: [],        // [{link_id, latency_ms, packet_loss_pct, throughput_mbps, connectivity_ok, risk_score, trend, alert_level, data_source}]
  telemetryDataSource: 'simulated',
  lastTick: 0,
  networkStatus: 'healthy',   // healthy | degraded | critical
  cascadeDetected: false,
  flappingLinks: [],
  setLiveTelemetry: (payload) => {
    const hasActiveIncident = 'active_incident' in payload;
    const nextActiveIncident = hasActiveIncident ? payload.active_incident : get().activeIncident;
    const shouldClearAffected = hasActiveIncident && payload.active_incident === null;

    const hasLive = payload.data_source === 'live' || (payload.measurements || []).some(m => m.data_source === 'live');
    const source = hasLive ? 'live' : (payload.data_source || 'simulated');

    set({
      liveMeasurements: payload.measurements || [],
      telemetryDataSource: source,
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
  setAllSubscribers: (subs) => {
    const AP_TO_VILLAGE = {
      AP1: 'Rampur',
      AP2: 'Rampur',
      AP3: 'Bhatpur',
      AP4: 'Bhatpur',
      AP5: 'Daulatpur',
      AP6: 'Daulatpur',
    };
    const enriched = (subs || []).map((s) => {
      const ap = s.access_point_id || s.ap_id;
      const village = s.village || (ap ? AP_TO_VILLAGE[ap] : null);
      return {
        ...s,
        ap_id: ap,
        access_point_id: ap,
        ...(village ? { village } : {}),
      };
    });
    set({ allSubscribers: enriched });
  },

  // ── Alert overlay & voice demo controls ─────────────────────────────────
  alertArmed: true,
  voiceMuted: false,
  alertOpen: false,
  setAlertArmed: (v) => set(typeof v === 'function' ? s => ({ alertArmed: v(s.alertArmed) }) : { alertArmed: v }),
  setVoiceMuted: (v) => set(typeof v === 'function' ? s => ({ voiceMuted: v(s.voiceMuted) }) : { voiceMuted: v }),
  setAlertOpen: (v) => set(typeof v === 'function' ? s => ({ alertOpen: v(s.alertOpen) }) : { alertOpen: v }),

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
  sarvamApiKey: (typeof localStorage !== 'undefined' ? localStorage.getItem('ht_sarvam_key') : '') || '',
  sarvamLanguage: 'hi',
  sarvamSpeaker: 'meera',
  setSarvamKey: (k) => {
    if (typeof localStorage !== 'undefined') localStorage.setItem('ht_sarvam_key', k);
    set({ sarvamApiKey: k });
  },
  setSarvamLanguage: (l) => set({ sarvamLanguage: l }),
  setSarvamSpeaker: (s) => set({ sarvamSpeaker: s }),

  // ── Selected element (topology click) ───────────────────────────────────
  selectedElement: null,
  setSelectedElement: (el) => set({ selectedElement: el }),

  // ── UI mode ─────────────────────────────────────────────────────────────
  dashboardMode: (typeof localStorage !== 'undefined' ? localStorage.getItem('ht_mode') : '') || 'noc',  // noc | business
  setDashboardMode: (m) => {
    if (typeof localStorage !== 'undefined') localStorage.setItem('ht_mode', m);
    set({ dashboardMode: m });
  },

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

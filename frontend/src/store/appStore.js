function classifyEssential(name = '') {
  const lower = name.toLowerCase();
  if (lower.includes('health') || lower.includes('phc') || lower.includes('hospital') || lower.includes('telemedicine')) {
    return { is_essential: true, category: 'health', badge: '🏥 Health' };
  }
  if (lower.includes('panchayat') || lower.includes('sarpanch') || lower.includes('ration') || lower.includes('pds')) {
    return { is_essential: true, category: 'governance', badge: '🏛️ Governance' };
  }
  if (lower.includes('school') || lower.includes('anganwadi') || lower.includes('library') || lower.includes('college')) {
    return { is_essential: true, category: 'education', badge: '📚 Education' };
  }
  if (lower.includes('police') || lower.includes('chowki') || lower.includes('fire')) {
    return { is_essential: true, category: 'emergency', badge: '🚨 Emergency' };
  }
  if (lower.includes('csc') || lower.includes('bank') || lower.includes('e-seva') || lower.includes('e-district')) {
    return { is_essential: true, category: 'citizen_services', badge: '🏦 Citizen Services' };
  }
  return { is_essential: false, category: 'commercial', badge: null };
}

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
  liveMeasurements: [],        // [{link_id, latency_ms, packet_loss_pct, throughput_mbps, connectivity_ok, risk_score, trend, alert_level, data_source, freshness, last_seen_utc}]
  telemetryDataSource: 'simulated',
  dataMode: 'demo',            // 'demo' | 'live'
  agents: [],                  // [{agent_id, site_id, last_seen_utc, status, silent_for_seconds, buffered_count}]
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

    const measurements = (payload.measurements || []).map(m => ({
      ...m,
      freshness: m.freshness || (m.data_source === 'live' ? 'live' : 'simulated'),
      last_seen_utc: m.last_seen_utc !== undefined ? m.last_seen_utc : null,
    }));

    set({
      liveMeasurements: measurements,
      agents: payload.agents !== undefined ? payload.agents : get().agents,
      dataMode: payload.data_mode || get().dataMode || (hasLive ? 'live' : 'demo'),
      telemetryDataSource: source,
      lastTick: payload.tick || 0,
      networkStatus: payload.network_status || 'healthy',
      cascadeDetected: payload.cascade_detected || false,
      flappingLinks: payload.flapping_links || [],
      activeIncident: nextActiveIncident,
      ...(shouldClearAffected ? { affectedSubscribers: [] } : {}),
    });
  },

  setAgents: (agents) => set({ agents: agents || [] }),
  setDataMode: (mode) => set({ dataMode: mode }),

  // ── Risk snapshot ───────────────────────────────────────────────────────
  riskSnapshot: {},   // { link_id -> risk_score }
  setRiskSnapshot: (snap) => {
    const map = {};
    (snap || []).forEach(r => {
      map[r.link_id] = {
        ...r,
        freshness: r.freshness || (r.data_source === 'live' ? 'live' : 'simulated'),
        last_seen_utc: r.last_seen_utc !== undefined ? r.last_seen_utc : null,
      };
    });
    set({ riskSnapshot: map });
  },

  // ── Incident ────────────────────────────────────────────────────────────
  activeIncident: null,
  setActiveIncident: (inc) => set({ activeIncident: inc }),

  // ── Affected subscribers ────────────────────────────────────────────────
  affectedSubscribers: [],
  setAffectedSubscribers: (subs) => {
    const enriched = (subs || []).map((s) => {
      const ess = classifyEssential(s.display_name || s.name || s.id);
      return {
        ...s,
        is_essential: ess.is_essential,
        essential_category: ess.category,
        essential_badge: ess.badge,
      };
    }).sort((a, b) => (b.is_essential ? 1 : 0) - (a.is_essential ? 1 : 0));
    set({ affectedSubscribers: enriched });
  },

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
      const ess = classifyEssential(s.display_name || s.name || s.id);
      return {
        ...s,
        ap_id: ap,
        access_point_id: ap,
        ...(village ? { village } : {}),
        is_essential: ess.is_essential,
        essential_category: ess.category,
        essential_badge: ess.badge,
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
  sarvamLanguage: 'hi',
  sarvamSpeaker: 'meera',
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

  // ── M3: User role (operator | viewer) ───────────────────────────────────
  userRole: 'operator',
  setUserRole: (role) => set({ userRole: role }),
}));

export default useStore;

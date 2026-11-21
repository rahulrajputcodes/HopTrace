import { useCallback } from 'react';
import useStore from '../store/appStore.js';
import { useAuth } from '../store/authStore.js';

const BASE = '/api/v1';

export async function publicApi(path, opts = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  const res = await fetch(BASE + path, {
    ...opts,
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function api(path, opts = {}) {
  const token = useAuth.getState().token;
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers || {}),
  };

  const res = await fetch(BASE + path, {
    ...opts,
    headers,
  });

  if (res.status === 401) {
    useAuth.getState().logout();
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Session expired. Please log in again.');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function useApi() {
  const store = useStore();

  const fetchAll = useCallback(async () => {
    store.setLoading(true);
    try {
      // Health
      const health = await api('/health').catch(() => null);
      store.setBackendOnline(!!health);
      if (!health) return;

      // Topology
      const topo = await api('/topology').catch(() => null);
      if (topo) store.setTopology(topo);

      // Subscribers
      const subs = await api('/subscribers').catch(() => null);
      if (subs) store.setAllSubscribers(subs.subscribers || []);

      // Villages
      const villages = await api('/villages').catch(() => null);
      if (villages) store.setVillages(villages.villages || []);

      // Latest incident
      const inc = await api('/incidents/latest').catch(() => null);
      if (inc && inc.id) {
        store.setActiveIncident(inc);
        try {
          const aff = await api(`/incidents/${inc.id}/affected-subscribers`);
          store.setAffectedSubscribers(aff?.subscribers || []);
        } catch (affErr) {
          console.warn('Failed to load affected subscribers:', affErr);
          store.setAffectedSubscribers([]);
        }
      } else {
        store.setActiveIncident(null);
        store.setAffectedSubscribers([]);
      }
    } catch (e) {
      store.addToast(`Sync error: ${e.message}`, 'error');
    } finally {
      store.setLoading(false);
    }
  }, [store]);

  const runScenario = useCallback(async (payload) => {
    store.setLoading(true);
    try {
      const result = await api('/lab/run', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (payload.scenario === 'baseline') {
        store.setActiveIncident(null);
        store.setAffectedSubscribers([]);
        store.addToast('Baseline restored — All links healthy', 'success');
      } else if (result.incident) {
        store.setActiveIncident(result.incident);
        store.setAffectedSubscribers(result.affected_subscribers || []);
        store.addToast(`Incident detected: ${result.incident.suspected_component_id || '—'}`, 'warning');
      }

      // Refresh topology
      const topo = await api('/topology').catch(() => null);
      if (topo) store.setTopology(topo);

      return result;
    } catch (e) {
      store.addToast(`Lab error: ${e.message}`, 'error');
      throw e;
    } finally {
      store.setLoading(false);
    }
  }, [store]);

  const explainIncident = useCallback(async (incidentId, language) => {
    store.setAiLoading(true);
    store.setAiReport(null);
    try {
      const result = await api(`/incidents/${incidentId}/explain`, {
        method: 'POST',
        body: JSON.stringify({ language }),
      });
      // result.explanation may be a JSON string or object
      let report = result.explanation;
      if (typeof report === 'string') {
        try { report = JSON.parse(report); } catch { /* ignore invalid JSON string */ }
      }
      store.setAiReport(report);
      store.setSarvamLanguage(language);
      store.addToast(`Explanation ready (${result.provider || 'AI'})`, 'success');
      return report;
    } catch (e) {
      store.addToast(`Explanation error: ${e.message}`, 'error');
      throw e;
    } finally {
      store.setAiLoading(false);
    }
  }, [store]);

  const synthesizeAudio = useCallback(async (text, languageCode, speaker) => {
    try {
      const result = await api('/explanations/audio', {
        method: 'POST',
        body: JSON.stringify({ text, language_code: languageCode, speaker }),
      });
      return result?.audio_base64 || null;
    } catch (err) {
      console.warn('Audio synthesis failed:', err);
      store.addToast(`Audio synthesis failed: ${err.message}`, 'error');
      return null;
    }
  }, [store]);

  const sendReminder = useCallback(async (subscriberId, language = 'hi') => {
    const result = await api(`/subscribers/${subscriberId}/remind`, {
      method: 'POST',
      body: JSON.stringify({ language }),
    });
    store.addToast(`Reminder recorded for ${subscriberId}`, 'success');
    return result;
  }, [store]);

  const fetchLinkHistory = useCallback(async (linkId, n = 50) => {
    return api(`/topology/history/${linkId}?n=${n}`).catch(() => ({ samples: [] }));
  }, []);

  const fetchRiskSnapshot = useCallback(async () => {
    const result = await api('/topology/risk').catch(() => null);
    if (result?.links) store.setRiskSnapshot(result.links);
    return result;
  }, [store]);

  const fetchBusinessImpact = useCallback(async (incidentId) => {
    return api(`/incidents/${incidentId}/business-impact`);
  }, []);

  const fetchNotificationStatus = useCallback(async () => {
    try {
      return await api('/notifications/status');
    } catch {
      return {
        available: false,
        provider: 'unavailable',
        reason: 'Outage notification provider is not configured. Set NOTIFICATION_PROVIDER=console or twilio.',
      };
    }
  }, []);

  const notifyIncident = useCallback(async (incidentId, channel = 'sms') => {
    return api(`/incidents/${incidentId}/notify`, {
      method: 'POST',
      body: JSON.stringify({ channel }),
    });
  }, []);

  const fetchAgentStatus = useCallback(async () => {
    try {
      const res = await api('/agent/status');
      if (res?.agents) {
        store.setAgents(res.agents);
      }
      return res;
    } catch {
      return null;
    }
  }, [store]);

  const runPathProbe = useCallback(async (failedNodeId = 'WB3') => {
    store.setLoading(true);
    try {
      const isFailed = Boolean(failedNodeId);
      const results = [
        { node_id: 'GW1', reachable: true, latency_ms: 0.5, packet_loss_pct: 0.0 },
        { node_id: 'R1', reachable: true, latency_ms: 12.4, packet_loss_pct: 0.0 },
        { node_id: 'WB1', reachable: true, latency_ms: 14.2, packet_loss_pct: 0.0 },
        { node_id: 'WB2', reachable: true, latency_ms: 22.0, packet_loss_pct: 0.0 },
        { node_id: 'AP1', reachable: true, latency_ms: 24.1, packet_loss_pct: 0.0 },
        { node_id: 'AP2', reachable: true, latency_ms: 15.0, packet_loss_pct: 0.0 },
        { node_id: 'WB3', reachable: !isFailed, latency_ms: isFailed ? null : 16.0, packet_loss_pct: isFailed ? 100.0 : 0.0 },
        { node_id: 'WB4', reachable: !isFailed, latency_ms: isFailed ? null : 28.0, packet_loss_pct: isFailed ? 100.0 : 0.0 },
        { node_id: 'R2', reachable: !isFailed, latency_ms: isFailed ? null : 30.0, packet_loss_pct: isFailed ? 100.0 : 0.0 },
        { node_id: 'AP3', reachable: !isFailed, latency_ms: isFailed ? null : 33.0, packet_loss_pct: isFailed ? 100.0 : 0.0 },
        { node_id: 'AP4', reachable: !isFailed, latency_ms: isFailed ? null : 34.0, packet_loss_pct: isFailed ? 100.0 : 0.0 },
        { node_id: 'WB5', reachable: true, latency_ms: 15.0, packet_loss_pct: 0.0 },
        { node_id: 'WB6', reachable: true, latency_ms: 29.0, packet_loss_pct: 0.0 },
        { node_id: 'AP5', reachable: true, latency_ms: 32.0, packet_loss_pct: 0.0 },
        { node_id: 'AP6', reachable: true, latency_ms: 33.0, packet_loss_pct: 0.0 },
      ];

      const res = await api('/probes/path', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: 'agent-rampur-1',
          vantage_node_id: 'GW1',
          timestamp: new Date().toISOString(),
          results,
        }),
      });

      if (res?.incident_id) {
        const inc = await api(`/incidents/${res.incident_id}`).catch(() => null);
        if (inc) {
          store.setActiveIncident(inc);
          const aff = await api(`/incidents/${inc.id}/affected-subscribers`).catch(() => null);
          if (aff?.subscribers) store.setAffectedSubscribers(aff.subscribers);
        }
      }

      const topo = await api('/topology').catch(() => null);
      if (topo) store.setTopology(topo);

      store.addToast(`Path probe from GW1: ${res.first_failed_nodes?.length ? `Fault boundary isolated at ${res.first_failed_nodes.join(', ')}` : 'All hops verified OK'}`, 'success');
      return res;
    } catch (err) {
      store.addToast(`Probe failed: ${err.message}`, 'error');
      throw err;
    } finally {
      store.setLoading(false);
    }
  }, [store]);

  return {
    fetchAll,
    runScenario,
    explainIncident,
    synthesizeAudio,
    sendReminder,
    fetchLinkHistory,
    fetchRiskSnapshot,
    fetchBusinessImpact,
    fetchNotificationStatus,
    notifyIncident,
    fetchAgentStatus,
    runPathProbe,
  };
}

import { useCallback } from 'react';
import useStore from '../store/appStore';

const BASE = '/api/v1';

async function api(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
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

  const explainIncident = useCallback(async (incidentId, language, apiKey) => {
    store.setAiLoading(true);
    store.setAiReport(null);
    try {
      const result = await api(`/incidents/${incidentId}/explain`, {
        method: 'POST',
        body: JSON.stringify({ language, api_key: apiKey || undefined }),
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

  const synthesizeAudio = useCallback(async (text, languageCode, speaker, apiKey) => {
    try {
      const result = await api('/explanations/audio', {
        method: 'POST',
        body: JSON.stringify({ text, language_code: languageCode, speaker, api_key: apiKey || undefined }),
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

  return {
    fetchAll,
    runScenario,
    explainIncident,
    synthesizeAudio,
    sendReminder,
    fetchLinkHistory,
    fetchRiskSnapshot,
    fetchBusinessImpact,
  };
}

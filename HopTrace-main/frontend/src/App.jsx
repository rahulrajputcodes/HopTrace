import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import AlertOverlay from './components/AlertOverlay/AlertOverlay';
import { appStore } from './store/appStore';
import './App.css';

const API_BASE = '/api/v1';

// Rural ISP Plan configuration & pricing (INR)
const PLAN_DETAILS = {
  Basic: { price: 399, speed: '20 Mbps', label: 'Basic Kirana / Home' },
  Enterprise: { price: 999, speed: '100 Mbps', label: 'Enterprise / Panchayat' },
  Community: { price: 0, speed: '50 Mbps', label: 'Govt Community (Free)' },
};

// Tower Solar & Power specifications (Rural India Off-Grid Telemetry)
const TOWER_POWER_INFO = {
  GW1: { powerSource: 'Grid Mains 230V', batteryVoltage: 52.8, solarAmps: 0.0, status: 'nominal', type: 'Fiber PoP' },
  R1:  { powerSource: 'Grid + 48V UPS', batteryVoltage: 51.4, solarAmps: 0.0, status: 'nominal', type: 'Core Tower' },
  WB1: { powerSource: 'Solar + 12V LiFePO4', batteryVoltage: 12.8, solarAmps: 5.2, status: 'nominal', type: 'Hilltop Bridge Tx' },
  WB2: { powerSource: 'Solar + 12V LiFePO4', batteryVoltage: 12.5, solarAmps: 4.6, status: 'nominal', type: 'Village Bridge Rx' },
  AP1: { powerSource: 'PoE 24V Switch', batteryVoltage: 24.0, solarAmps: 0.0, status: 'nominal', type: 'North Ward AP' },
  AP2: { powerSource: 'PoE 24V Switch', batteryVoltage: 24.0, solarAmps: 0.0, status: 'nominal', type: 'South Ward AP' },
};

export default function App() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Selected topology element for drawer inspection
  const [selectedElement, setSelectedElement] = useState(null);

  // Topology state with coordinates
  const [topology, setTopology] = useState({
    data_source: 'local_mock',
    nodes: [
      { id: 'GW1', label: 'Upstream Gateway', type: 'gateway', status: 'healthy', x: 90, y: 150 },
      { id: 'R1', label: 'Village Core Router', type: 'router', status: 'healthy', x: 260, y: 150 },
      { id: 'WB1', label: 'Wireless Bridge Tx', type: 'wireless_bridge', status: 'healthy', x: 440, y: 80 },
      { id: 'WB2', label: 'Wireless Bridge Rx', type: 'wireless_bridge', status: 'healthy', x: 600, y: 80 },
      { id: 'AP1', label: 'North Village AP', type: 'access_point', status: 'healthy', x: 740, y: 80 },
      { id: 'AP2', label: 'South Village AP', type: 'access_point', status: 'healthy', x: 440, y: 220 },
    ],
    links: [
      { id: 'L1', source: 'GW1', target: 'R1', latency_ms: 15.0, packet_loss_pct: 0.0, throughput_mbps: 100, status: 'healthy' },
      { id: 'L2', source: 'R1', target: 'WB1', latency_ms: 2.0, packet_loss_pct: 0.0, throughput_mbps: 80, status: 'healthy' },
      { id: 'L3', source: 'WB1', target: 'WB2', latency_ms: 25.0, packet_loss_pct: 0.5, throughput_mbps: 35, status: 'healthy' },
      { id: 'L4', source: 'WB2', target: 'AP1', latency_ms: 3.0, packet_loss_pct: 0.0, throughput_mbps: 50, status: 'healthy' },
      { id: 'L5', source: 'R1', target: 'AP2', latency_ms: 5.0, packet_loss_pct: 0.0, throughput_mbps: 60, status: 'healthy' },
    ],
  });

  // Subscribers
  const [allSubscribers, setAllSubscribers] = useState([]);
  const [subscriberFilter, setSubscriberFilter] = useState('all'); // 'all' | 'affected' | 'due'

  // Active Incident and Related Context
  const [activeIncident, setActiveIncident] = useState(null);
  const [incidentSubscribers, setIncidentSubscribers] = useState([]);
  const [runMeasurements, setRunMeasurements] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);

  // Reminder tracking (stores exact backend record: status, delivery_status)
  const [reminderRecords, setReminderRecords] = useState({});

  // Risk snapshot: map of link_id -> { predicted_eta_minutes, prediction_confidence, prediction_r2 }
  const [riskByLink, setRiskByLink] = useState({});

  // Lab Controls
  const [scenario, setScenario] = useState('degrade_link');
  const [targetType, setTargetType] = useState('link');
  const [targetId, setTargetId] = useState('L3');
  const [severity, setSeverity] = useState('high');

  // Sarvam AI Indian Regional Language & Neural Voice State
  const [sarvamApiKey, setSarvamApiKey] = useState(() => localStorage.getItem('hoptrace_sarvam_key') || '');
  const [sarvamLanguage, setSarvamLanguage] = useState('hi');
  const [sarvamSpeaker, setSarvamSpeaker] = useState('meera');
  const [sarvamModalOpen, setSarvamModalOpen] = useState(false);
  const [sarvamTempKey, setSarvamTempKey] = useState(() => localStorage.getItem('hoptrace_sarvam_key') || '');
  const [sarvamProviderUsed, setSarvamProviderUsed] = useState('');
  const [sarvamTesting, setSarvamTesting] = useState(false);
  const [dashboardMode, setDashboardMode] = useState(() => localStorage.getItem('hoptrace_mode') || 'business');

  const [hindiExplanation, setHindiExplanation] = useState('');
  const [explainingHindi, setExplainingHindi] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const audioRef = useRef(null);

  // Modals (UPI Payment & WhatsApp Broadcast)
  const [upiModalSub, setUpiModalSub] = useState(null);
  const [broadcastModalOpen, setBroadcastModalOpen] = useState(false);
  const [toastMsg, setToastMsg] = useState('');

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3500);
  };

  // Fetch /topology/risk and merge prediction data into riskByLink state.
  // Never crashes when the endpoint is absent or returns unexpected data.
  const fetchRisk = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/topology/risk`, { signal: AbortSignal.timeout(2000) });
      if (!res.ok) return;
      const data = await res.json();
      if (!Array.isArray(data)) return;
      const map = {};
      data.forEach((entry) => {
        if (entry && entry.link_id) map[entry.link_id] = entry;
      });
      setRiskByLink(map);
    } catch {
      // Network error or timeout — silently ignore; badge simply won't appear
    }
  }, []);

  // 1. Health check
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
      if (res.ok) {
        setBackendOnline(true);
        return true;
      }
      setBackendOnline(false);
      return false;
    } catch {
      setBackendOnline(false);
      return false;
    }
  }, []);

  // 2. Fetch all subscribers
  const fetchSubscribers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/subscribers`);
      if (res.ok) {
        const data = await res.json();
        setAllSubscribers(data.subscribers || []);
      }
    } catch (err) {
      console.warn('Failed to load subscribers:', err);
    }
  }, []);

  // 3. Fetch Incident-specific affected subscribers
  const fetchAffectedSubscribers = async (incidentId) => {
    if (!incidentId) {
      setIncidentSubscribers([]);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/incidents/${incidentId}/affected-subscribers`);
      if (res.ok) {
        const data = await res.json();
        setIncidentSubscribers(Array.isArray(data) ? data : (data.subscribers || []));
      } else {
        setIncidentSubscribers([]);
      }
    } catch {
      setIncidentSubscribers([]);
    }
  };

  // 4. Fetch Run measurements
  const fetchRunMeasurements = async (runId) => {
    if (!runId) {
      setRunMeasurements([]);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/runs/${runId}/measurements`);
      if (res.ok) {
        const data = await res.json();
        setRunMeasurements(Array.isArray(data) ? data : (data.measurements || []));
      } else {
        setRunMeasurements([]);
      }
    } catch {
      setRunMeasurements([]);
    }
  };

  // 5. Fetch Core Data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg('');
    const isOnline = await checkHealth();

    if (!isOnline) {
      setLoading(false);
      return;
    }

    try {
      await fetchSubscribers();

      // Topology
      const topoRes = await fetch(`${API_BASE}/topology`);
      if (topoRes.ok) {
        const topoData = await topoRes.json();
        const posMap = {
          GW1: { x: 90,  y: 150 },
          R1:  { x: 260, y: 150 },
          WB1: { x: 440, y: 80 },
          WB2: { x: 600, y: 80 },
          AP1: { x: 740, y: 80 },
          AP2: { x: 440, y: 220 },
        };

        const nodesWithCoords = (topoData.nodes || []).map((node, idx) => ({
          ...node,
          x: posMap[node.id]?.x ?? (90 + (idx % 3) * 180),
          y: posMap[node.id]?.y ?? (80 + Math.floor(idx / 3) * 120),
          power: TOWER_POWER_INFO[node.id] || { powerSource: 'POE', batteryVoltage: 12.0, solarAmps: 0.0, status: 'nominal' },
        }));

        setTopology({
          ...topoData,
          nodes: nodesWithCoords,
        });
      }

      // Latest Incident
      try {
        const incRes = await fetch(`${API_BASE}/incidents/latest`);
        if (incRes.ok && incRes.status !== 204) {
          const incData = await incRes.json();
          if (incData && incData.id) {
            setActiveIncident(incData);
            appStore.notifyIncident(incData, incidentSubscribers, false);
            fetchAffectedSubscribers(incData.id);
            if (incData.run_id) {
              setActiveRunId(incData.run_id);
              fetchRunMeasurements(incData.run_id);
            }
          } else {
            setActiveIncident(null);
            appStore.notifyIncident(null);
            setIncidentSubscribers([]);
          }
        } else {
          setActiveIncident(null);
          appStore.notifyIncident(null);
          setIncidentSubscribers([]);
        }
      } catch {
        setActiveIncident(null);
        appStore.notifyIncident(null);
        setIncidentSubscribers([]);
      }

      // Risk snapshot for predictive badges
      await fetchRisk();
    } catch (err) {
      setErrorMsg(`Failed to sync backend state: ${err.message}`);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkHealth, fetchSubscribers, fetchRisk]);

  // Initial load
  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (isMounted) await fetchData();
    })();
    return () => { isMounted = false; };
  }, [fetchData]);

  // Poll /topology/risk every 5 seconds for predictive ETA badges.
  useEffect(() => {
    const id = setInterval(fetchRisk, 5000);
    return () => clearInterval(id);
  }, [fetchRisk]);

  // Auto-refresh timer (5s)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchData();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchData]);

  // Run Scenario
  const handleRunScenario = async (scenarioOverride = null, targetTypeOverride = null, targetIdOverride = null, severityOverride = null) => {
    const sc = scenarioOverride || scenario;
    const tt = targetTypeOverride || targetType;
    const tid = targetIdOverride || targetId;
    const sev = severityOverride || severity;
    setLoading(true);
    setErrorMsg('');
    setHindiExplanation('');
    if (isPlayingAudio && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsPlayingAudio(false);
    }

    const payload = {
      scenario: sc,
      severity: sev,
      ...(tt === 'link' ? { target_link_id: tid } : { target_node_id: tid }),
    };

    try {
      const res = await fetch(`${API_BASE}/lab/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned status ${res.status}`);
      }

      const runResult = await res.json();
      const newRunId = runResult.run_id || runResult.id;
      const associatedIncidentId = runResult.incident_id;

      if (newRunId) {
        setActiveRunId(newRunId);
        await fetchRunMeasurements(newRunId);
      }

      if (sc === 'baseline' || !associatedIncidentId) {
        setActiveIncident(null);
        appStore.notifyIncident(null);
        setIncidentSubscribers([]);
        setHindiExplanation('');
        showToast('Baseline restored — All network links healthy.');
      } else {
        if (runResult.incident) {
          setActiveIncident(runResult.incident);
        } else {
          setActiveIncident({ id: associatedIncidentId, summary: runResult.summary || 'Incident detected by engine.' });
        }
        await fetchAffectedSubscribers(associatedIncidentId);
        showToast(`Incident detected: ${associatedIncidentId}`);
      }

      const topoRes = await fetch(`${API_BASE}/topology`);
      if (topoRes.ok) {
        const topoData = await topoRes.json();
        setTopology((prev) => ({
          ...topoData,
          nodes: (topoData.nodes || []).map((n) => ({
            ...n,
            x: prev.nodes.find((pn) => pn.id === n.id)?.x ?? n.x ?? 90,
            y: prev.nodes.find((pn) => pn.id === n.id)?.y ?? n.y ?? 150,
            power: TOWER_POWER_INFO[n.id] || { powerSource: 'POE', batteryVoltage: 12.0, solarAmps: 0.0, status: 'nominal' },
          })),
        }));
      }
    } catch (err) {
      setErrorMsg(`Lab simulation error: ${err.message}.`);
    } finally {
      setLoading(false);
    }
  };

  // Sarvam AI Localized Explanation & Speech Synthesis
  const handleExplainLocalized = async (langOverride = null) => {
    if (!activeIncident?.id) {
      setErrorMsg('No active incident available to explain. Run a simulation scenario below.');
      return;
    }

    const lang = langOverride || sarvamLanguage || 'hi';
    setSarvamLanguage(lang);
    setExplainingHindi(true);
    setHindiExplanation('');
    setErrorMsg('');

    try {
      const res = await fetch(`${API_BASE}/incidents/${activeIncident.id}/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          language: lang,
          api_key: sarvamApiKey.trim() || undefined,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setHindiExplanation(data.explanation);
        setSarvamProviderUsed(data.provider || 'sarvam');
        showToast(`Grounded explanation generated (${data.provider === 'sarvam' ? 'Sarvam AI 105B Cloud' : 'HopTrace Diagnostics'})`);
        return;
      }

      const comp = activeIncident.suspected_component_id || 'घटक';
      const summary = activeIncident.summary || 'नेटवर्क खराबी';
      const score = Math.round((activeIncident.confidence_score || 0.9) * 100);
      let evList = [];
      if (Array.isArray(activeIncident.evidence) && activeIncident.evidence.length > 0) {
        evList = activeIncident.evidence.map(e => typeof e === 'object' ? (e.description || e.metric) : String(e));
      }

      const localBriefing = lang.startsWith('hi')
        ? `HopTrace नेटवर्क डायग्नोस्टिक (हिंदी): घटक '${comp}' पर गंभीर असामान्यता दर्ज की गई है (विश्वास स्तर: ${score}%)। सारांश: ${summary}।\n\nमुख्य साक्ष्य:\n• ${evList.join('\n• ') || 'पैकेट हानि और उच्च लेटेंसी दर्ज की गई।'}\n\n(💡 लाइव Sarvam AI मॉडल सक्षम करने के लिए ऊपर '🔑 Sarvam AI' बटन दबाकर अपनी API Key दर्ज करें)`
        : `HopTrace Network Diagnostic: Component '${comp}' anomaly detected (Confidence: ${score}%). Summary: ${summary}.\n\nKey Evidence:\n• ${evList.join('\n• ') || 'Elevated packet loss and latency.'}\n\n(💡 Connect Sarvam AI API Key in the top bar for live regional LLM generation)`;

      setHindiExplanation(localBriefing);
      setSarvamProviderUsed('simulated');
    } catch (err) {
      setErrorMsg(`Sarvam AI Explanation error: ${err.message}`);
    } finally {
      setExplainingHindi(false);
    }
  };

  // Sarvam Bulbul Neural TTS Audio with device speech fallback
  const toggleSpeechAudio = async () => {
    if (isPlayingAudio) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      setIsPlayingAudio(false);
      return;
    }

    const textToSpeak = (hindiExplanation || activeIncident?.summary || '').replace(/[•*_~#]/g, '');
    if (!textToSpeak) return;

    setIsPlayingAudio(true);

    // 1. First attempt: Sarvam Bulbul neural TTS via backend
    try {
      const res = await fetch(`${API_BASE}/incidents/${activeIncident?.id || 'incident-001'}/explain/audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: textToSpeak.slice(0, 480),
          language_code: sarvamLanguage === 'en' ? 'en-IN' : 'hi-IN',
          speaker: sarvamSpeaker,
          api_key: sarvamApiKey.trim() || undefined,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.audio_base64) {
          const snd = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
          audioRef.current = snd;
          snd.onended = () => {
            setIsPlayingAudio(false);
            audioRef.current = null;
          };
          snd.onerror = () => {
            fallbackDeviceSpeech(textToSpeak);
          };
          await snd.play();
          showToast(`Playing Sarvam Bulbul neural voice (${sarvamSpeaker})`);
          return;
        }
      }
    } catch {
      // Fallback
    }

    // 2. Fallback to Browser Speech Synthesis
    fallbackDeviceSpeech(textToSpeak);
  };

  const fallbackDeviceSpeech = (text) => {
    if (!('speechSynthesis' in window)) {
      setIsPlayingAudio(false);
      showToast('Speech audio is not supported in this browser.');
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const hindiVoice = voices.find((v) => v.lang.startsWith('hi') || v.lang.includes('Hindi'));
    if (hindiVoice) utterance.voice = hindiVoice;
    utterance.lang = sarvamLanguage === 'en' ? 'en-IN' : 'hi-IN';
    utterance.rate = 0.92;
    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);

    window.speechSynthesis.speak(utterance);
    showToast('Playing voice readout via device synthesizer');
  };

  // Test Sarvam API key connection
  const handleTestSarvamKey = async () => {
    if (!sarvamTempKey.trim()) {
      showToast('Please enter a Sarvam API key first');
      return;
    }
    setSarvamTesting(true);
    try {
      const res = await fetch(`${API_BASE}/explanations/audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: 'नमस्ते',
          language_code: 'hi-IN',
          speaker: 'meera',
          api_key: sarvamTempKey.trim(),
        }),
      });
      if (res.ok) {
        showToast('✓ Sarvam AI connection verified successfully!');
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(`Verification note: ${err.detail || 'Could not verify key'}`);
      }
    } catch (e) {
      showToast(`Connection test failed: ${e.message}`);
    } finally {
      setSarvamTesting(false);
    }
  };

  // Send Reminder Request to Backend
  const handleSendReminder = async (subscriberId) => {
    setErrorMsg('');
    try {
      const res = await fetch(`${API_BASE}/subscribers/${subscriberId}/remind`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: 'hi' }),
      });

      if (!res.ok) {
        throw new Error(`Backend responded with status ${res.status}`);
      }

      const data = await res.json();
      if (data.status === 'recorded') {
        setReminderRecords((prev) => ({
          ...prev,
          [subscriberId]: {
            status: 'recorded',
            delivery_status: data.delivery_status || 'not_sent',
          },
        }));
        showToast(`Payment reminder recorded for ${subscriberId}`);
      } else {
        throw new Error(data.message || 'Status is not recorded');
      }
    } catch (err) {
      setErrorMsg(`Failed to record reminder: ${err.message}`);
    }
  };

  // Generate NPCI UPI Payment URI
  const getUpiUri = (subscriber) => {
    if (!subscriber) return '';
    const plan = PLAN_DETAILS[subscriber.plan] || { price: 399 };
    const amount = plan.price;
    const vpa = 'hoptrace.gramin@sbi';
    const payeeName = 'HopTrace Rural ISP';
    const note = `${subscriber.id} Internet Bill`;
    return `upi://pay?pa=${vpa}&pn=${encodeURIComponent(payeeName)}&am=${amount}&tn=${encodeURIComponent(note)}&cu=INR`;
  };

  // WhatsApp Outage Broadcast Link generator
  const getWhatsAppBroadcastLink = (sub, incident) => {
    const comp = incident?.suspected_component_id || 'Network Link';
    const msg = `नमस्ते ${sub.display_name},\n\nग्राम नेट सूचना: गाँव में नेटवर्क घटक (${comp}) में अस्थायी तकनीकी समस्या के कारण आपकी इंटरनेट सेवा बाधित है। हमारी फील्ड टीम सुधार कार्य कर रही है। असुविधा के लिए खेद है। — हॉपट्रेस ग्रामीण इंटरनेट`;
    return `https://wa.me/?text=${encodeURIComponent(msg)}`;
  };

  // Financial & Operational Metrics (Theme T3.2)
  const metrics = useMemo(() => {
    const totalSubs = allSubscribers.length || 5;
    let mrr = 0;
    let paidCount = 0;
    allSubscribers.forEach((s) => {
      const p = PLAN_DETAILS[s.plan]?.price ?? 399;
      mrr += p;
      if (s.payment_status === 'paid') paidCount += 1;
    });

    const collectionRate = totalSubs > 0 ? Math.round((paidCount / totalSubs) * 100) : 100;
    const affectedCount = incidentSubscribers.length;
    const avgBattery = 12.6;

    return { totalSubs, mrr, paidCount, collectionRate, affectedCount, avgBattery };
  }, [allSubscribers, incidentSubscribers]);

  // Filtered subscribers list
  const filteredSubscribers = useMemo(() => {
    if (subscriberFilter === 'affected') {
      const affectedIds = new Set(incidentSubscribers.map((s) => s.id));
      return allSubscribers.filter((s) => affectedIds.has(s.id));
    }
    if (subscriberFilter === 'due') {
      return allSubscribers.filter((s) => s.payment_status === 'due');
    }
    return allSubscribers;
  }, [allSubscribers, incidentSubscribers, subscriberFilter]);

  return (
    <div className="dashboard-container">
      {/* ── Top Header ──────────────────────────────────────────────────────── */}
      <header className="dashboard-header">
        <div className="header-brand">
          <div className="brand-logo">HT</div>
          <div>
            <h1>HopTrace Network Intelligence & Business Hub</h1>
            <p className="subtitle">Rural Village ISP Diagnostics · Solar Fleet · Subscriber Operations (T3.2)</p>
          </div>
        </div>

        <div className="header-controls">
          {/* Executive Mode Switcher (Theme T3.2 vs Pure NOC) */}
          <div className="mode-switcher">
            <button
              className={`mode-btn ${dashboardMode === 'business' ? 'active' : ''}`}
              onClick={() => {
                setDashboardMode('business');
                localStorage.setItem('hoptrace_mode', 'business');
                showToast('Switched to Village Business Mode (Billing & QR Enabled)');
              }}
              title="Village ISP Business Hub: Subscriber Billing, BharatPe QR, and WhatsApp Outage Notices"
            >
              🏪 Village Business & QR
            </button>
            <button
              className={`mode-btn ${dashboardMode === 'noc' ? 'active' : ''}`}
              onClick={() => {
                setDashboardMode('noc');
                localStorage.setItem('hoptrace_mode', 'noc');
                showToast('Switched to Pure NOC Mode (Telemetry & AI Intelligence)');
              }}
              title="Pure Network NOC: Microwave Bridges, Latency, Loss, and Sarvam AI Diagnostics"
            >
              ⚡ Pure NOC Mode
            </button>
          </div>

          {/* Sarvam AI Key & Voice Agent Trigger */}
          <button
            className={`sarvam-badge-btn ${sarvamApiKey ? 'connected' : ''}`}
            onClick={() => {
              setSarvamTempKey(sarvamApiKey);
              setSarvamModalOpen(true);
            }}
            title="Configure Sarvam AI API Key and Neural Voice Settings"
          >
            <span>{sarvamApiKey ? '⚡ Sarvam AI: Active' : '🔑 Connect Sarvam AI'}</span>
          </button>

          <div
            className={`auto-refresh-toggle ${autoRefresh ? 'active' : ''}`}
            onClick={() => setAutoRefresh(!autoRefresh)}
            title="Auto-refresh every 5 seconds"
          >
            <span className={`pulse-dot ${autoRefresh ? 'live' : ''}`} />
            {autoRefresh ? 'Live Sync (5s)' : 'Sync Paused'}
          </div>

          <span className="source-tag">
            Source:{' '}
            {!backendOnline ? (
              <span className="badge badge-warning">DEMO MOCK</span>
            ) : (
              <span className="badge badge-online">{topology.data_source || 'live_telemetry'}</span>
            )}
          </span>

          <span className={`badge ${backendOnline ? 'badge-success' : 'badge-danger'}`}>
            {backendOnline ? '● FastAPI Online' : '○ FastAPI Offline'}
          </span>

          <button className="btn-secondary" onClick={fetchData} disabled={loading}>
            {loading ? 'Syncing...' : 'Refresh'}
          </button>
        </div>
      </header>

      {/* ── Toast Notification ────────────────────────────────────────────── */}
      {toastMsg && (
        <div className="banner-error" style={{ background: '#064e3b', borderColor: '#10b981', color: '#6ee7b7' }}>
          <span>✓ {toastMsg}</span>
          <button onClick={() => setToastMsg('')}>✕</button>
        </div>
      )}

      {/* ── Error Banner ──────────────────────────────────────────────────── */}
      {errorMsg && (
        <div className="banner-error">
          <span>⚠️ {errorMsg}</span>
          <button onClick={() => setErrorMsg('')}>✕</button>
        </div>
      )}

      {/* ── Executive KPI Ribbon (Theme T3.2: Village Business) ───────────── */}
      <section className="kpi-ribbon">
        <div className="kpi-card kpi-blue">
          <span className="kpi-title">Active Connections</span>
          <span className="kpi-value">
            {metrics.totalSubs - metrics.affectedCount} / {metrics.totalSubs}
          </span>
          <span className="kpi-subtitle">
            {metrics.affectedCount > 0 ? (
              <span style={{ color: '#ef4444' }}>⚠️ {metrics.affectedCount} subscriber(s) impacted</span>
            ) : (
              '100% Village coverage active'
            )}
          </span>
        </div>

        <div className="kpi-card kpi-green">
          <span className="kpi-title">Monthly Revenue (MRR)</span>
          <span className="kpi-value">₹{metrics.mrr.toLocaleString()}</span>
          <span className="kpi-subtitle">{metrics.collectionRate}% collected ({metrics.paidCount} paid)</span>
        </div>

        <div className="kpi-card kpi-amber">
          <span className="kpi-title">Towers & Solar Power</span>
          <span className="kpi-value">{metrics.avgBattery}V Avg</span>
          <span className="kpi-subtitle">☀️ 2 Solar Relay Towers · Grid PoP Normal</span>
        </div>

        <div className="kpi-card kpi-purple">
          <span className="kpi-title">Fault Detection</span>
          <span className="kpi-value">
            {activeIncident ? (
              <span style={{ color: '#ef4444' }}>{activeIncident.suspected_component_id || 'ALARM'}</span>
            ) : (
              <span style={{ color: '#10b981' }}>HEALTHY</span>
            )}
          </span>
          <span className="kpi-subtitle">
            {activeIncident ? `${Math.round((activeIncident.confidence_score || 0.9) * 100)}% Confidence` : 'Zero open incidents'}
          </span>
        </div>
      </section>

      {/* ── Main Operations Grid ─────────────────────────────────────────── */}
      <main className="dashboard-grid">
        {/* 1. Interactive Network Topology Canvas */}
        <section className="card col-8">
          <div className="card-header">
            <div>
              <h2>🌐 Network Topology Graph</h2>
              <span className="caption">Real-time PtP wireless & distribution tree with live status pulses</span>
            </div>
            <span className="badge badge-online">
              {topology.links.length} Links · {topology.nodes.length} Devices
            </span>
          </div>

          <div className="topology-svg-wrapper">
            <svg viewBox="0 0 840 280" className="topology-svg">
              {/* Links */}
              {topology.links.map((link) => {
                const srcNode = topology.nodes.find((n) => n.id === link.source);
                const tgtNode = topology.nodes.find((n) => n.id === link.target);
                if (!srcNode || !tgtNode) return null;

                const isSuspected = activeIncident?.suspected_component_id === link.id;
                const isSelected = selectedElement?.id === link.id;
                const isDown = link.status === 'down' || (link.packet_loss_pct >= 95);
                const isDegraded = link.status === 'degraded' || (link.packet_loss_pct > 0);

                let strokeColor = '#3b82f6';
                if (isDown) strokeColor = '#ef4444';
                else if (isSuspected) strokeColor = '#f43f5e';
                else if (isDegraded) strokeColor = '#f59e0b';

                const linkRisk = riskByLink[link.id];
                const hasEta = linkRisk && linkRisk.predicted_eta_minutes != null;
                const badgeWidth = hasEta ? 140 : 64;

                const midX = (srcNode.x + tgtNode.x) / 2;
                const midY = (srcNode.y + tgtNode.y) / 2 - 14;

                // Scaled stroke width based on throughput capacity
                const strokeWidth = link.throughput_mbps > 50 ? 3.5 : 2.5;

                return (
                  <g
                    key={link.id}
                    className="clickable-topology-item"
                    onClick={() => setSelectedElement({ type: 'link', data: link })}
                  >
                    {/* Suspected Pulsing Aura */}
                    {isSuspected && (
                      <line
                        x1={srcNode.x}
                        y1={srcNode.y}
                        x2={tgtNode.x}
                        y2={tgtNode.y}
                        stroke="#ef4444"
                        strokeWidth="8"
                        strokeOpacity="0.35"
                        className="pulse-link"
                      />
                    )}

                    {/* Base Link Line */}
                    <line
                      x1={srcNode.x}
                      y1={srcNode.y}
                      x2={tgtNode.x}
                      y2={tgtNode.y}
                      stroke={strokeColor}
                      strokeWidth={isSelected ? strokeWidth + 2 : strokeWidth}
                      strokeDasharray={isDown ? '4,4' : 'none'}
                    />

                    {/* Animated Data Flow Particles if healthy */}
                    {!isDown && (
                      <line
                        x1={srcNode.x}
                        y1={srcNode.y}
                        x2={tgtNode.x}
                        y2={tgtNode.y}
                        stroke="#60a5fa"
                        strokeWidth="1.5"
                        strokeDasharray="4,16"
                        className="flow-particle"
                        strokeOpacity="0.8"
                      />
                    )}

                    {/* Telemetry pill label */}
                    <rect
                      x={midX - badgeWidth / 2}
                      y={midY - 10}
                      width={badgeWidth}
                      height="20"
                      rx="4"
                      fill={isSelected ? '#334155' : '#1e293b'}
                      stroke={isSelected ? '#60a5fa' : isSuspected ? '#ef4444' : hasEta ? '#f59e0b' : '#475569'}
                      strokeWidth="1"
                    />
                    <text x={midX} y={midY + 4} textAnchor="middle" fill="#94a3b8" fontSize="10" fontWeight="500">
                      {link.latency_ms != null ? `${link.latency_ms}ms` : '—'} | {link.packet_loss_pct != null ? `${link.packet_loss_pct}%` : '—'}
                      {hasEta && (
                        <tspan fill="#f59e0b">{` · ~${Math.round(linkRisk.predicted_eta_minutes)} min (${linkRisk.prediction_confidence})`}</tspan>
                      )}
                    </text>
                  </g>
                );
              })}

              {/* Devices / Nodes */}
              {topology.nodes.map((node) => {
                const isSuspected = activeIncident?.suspected_component_id === node.id;
                const isSelected = selectedElement?.id === node.id;
                const nodeColor = node.status === 'down' ? '#ef4444' : node.status === 'degraded' ? '#f59e0b' : '#10b981';

                const powerMeta = TOWER_POWER_INFO[node.id];

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    className="clickable-topology-item"
                    onClick={() => setSelectedElement({ type: 'node', data: { ...node, power: powerMeta } })}
                  >
                    {/* Pulsing Alert Ring for suspected fault */}
                    {isSuspected && (
                      <circle r="38" fill="none" stroke="#ef4444" strokeWidth="2.5" strokeDasharray="4,4" className="pulse-ring" />
                    )}

                    {/* Outer Circle */}
                    <circle
                      r="26"
                      fill={isSelected ? '#1e293b' : '#0b1120'}
                      stroke={isSelected ? '#60a5fa' : nodeColor}
                      strokeWidth={isSelected ? '3.5' : '2.5'}
                    />

                    {/* Solar / Power Indicator Dot */}
                    {powerMeta?.solarAmps > 0 && (
                      <circle cx="18" cy="-18" r="6" fill="#f59e0b" stroke="#0f172a" strokeWidth="1.5" title="Solar Active" />
                    )}

                    {/* Node ID */}
                    <text y="4" textAnchor="middle" fill="#f8fafc" fontSize="11" fontWeight="bold">
                      {node.id}
                    </text>

                    {/* Node Label */}
                    <text y="42" textAnchor="middle" fill="#cbd5e1" fontSize="11" fontWeight="500">
                      {node.label}
                    </text>

                    {/* Power / Type Tag */}
                    <text y="56" textAnchor="middle" fill="#64748b" fontSize="9">
                      {powerMeta?.type || node.type} · {powerMeta?.batteryVoltage ? `${powerMeta.batteryVoltage}V` : 'Grid'}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div className="topology-legend">
            <div className="legend-item"><span className="legend-color" style={{ background: '#10b981' }} /> Healthy</div>
            <div className="legend-item"><span className="legend-color" style={{ background: '#f59e0b' }} /> Degraded</div>
            <div className="legend-item"><span className="legend-color" style={{ background: '#ef4444' }} /> Outage / Failure</div>
            <div className="legend-item"><span className="legend-color" style={{ background: '#f43f5e' }} /> Suspected Root-Cause</div>
            <div className="legend-item">☀️ Solar Powered Tower</div>
          </div>

          {/* Component Quick Inspector Drawer */}
          {selectedElement && (
            <div className="inspector-panel">
              <div className="inspector-header">
                <span>Inspecting {selectedElement.type.toUpperCase()}: <code>{selectedElement.data.id}</code></span>
                <button className="btn-inline-close" onClick={() => setSelectedElement(null)}>✕</button>
              </div>

              {selectedElement.type === 'link' ? (
                <div className="inspector-grid">
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Route</span>
                    <div className="inspector-stat-val">{selectedElement.data.source} ➔ {selectedElement.data.target}</div>
                  </div>
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Latency</span>
                    <div className="inspector-stat-val">{selectedElement.data.latency_ms ?? '—'} ms</div>
                  </div>
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Packet Loss</span>
                    <div className="inspector-stat-val" style={{ color: selectedElement.data.packet_loss_pct > 0 ? '#ef4444' : 'inherit' }}>
                      {selectedElement.data.packet_loss_pct ?? '—'}%
                    </div>
                  </div>
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Throughput</span>
                    <div className="inspector-stat-val">{selectedElement.data.throughput_mbps ?? '—'} Mbps</div>
                  </div>
                </div>
              ) : (
                <div className="inspector-grid">
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Device Type</span>
                    <div className="inspector-stat-val">{selectedElement.data.type}</div>
                  </div>
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Power Source</span>
                    <div className="inspector-stat-val">{selectedElement.data.power?.powerSource || 'Grid Mains'}</div>
                  </div>
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Battery Voltage</span>
                    <div className="inspector-stat-val">{selectedElement.data.power?.batteryVoltage || '52.0'} V</div>
                  </div>
                  <div className="inspector-stat">
                    <span className="inspector-stat-label">Solar Input</span>
                    <div className="inspector-stat-val">{selectedElement.data.power?.solarAmps || '0.0'} A</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* 2. Active Diagnosis & AI Voice Explainer */}
        <section className="card col-4">
          <div className="card-header">
            <h2>🔍 Active Diagnosis & AI</h2>
            <span className="caption">Inferred root cause & Sarvam AI</span>
          </div>

          <div className="incident-card-body">
            {activeIncident ? (
              <>
                <div className="incident-banner">
                  <div className="incident-banner-header">
                    <strong>Root-Cause Identified</strong>
                    <span className="badge badge-danger">
                      {activeIncident.suspected_component_id} ({activeIncident.suspected_component_type})
                    </span>
                  </div>
                  <p className="incident-summary">{activeIncident.summary}</p>
                </div>

                {activeIncident.evidence && activeIncident.evidence.length > 0 && (
                  <div className="evidence-box">
                    <div className="evidence-title">Telemetry Evidence:</div>
                    <ul>
                      {activeIncident.evidence.map((ev, i) => {
                        let desc;
                        if (typeof ev === 'string') {
                          desc = ev;
                        } else if (ev && typeof ev === 'object') {
                          desc = ev.description || `${ev.metric || 'Metric'}: observed ${ev.observed_value ?? '—'} vs baseline ${ev.baseline_value ?? '—'} (${ev.severity || 'anomaly'})`;
                        } else {
                          desc = String(ev);
                        }
                        return <li key={i}>{desc}</li>;
                      })}
                    </ul>
                  </div>
                )}

                {activeIncident.uncertainty_note && (
                  <div style={{ fontSize: '11px', color: '#fbbf24', background: 'rgba(245, 158, 11, 0.1)', padding: '6px 10px', borderRadius: '4px' }}>
                    ℹ️ {activeIncident.uncertainty_note}
                  </div>
                )}

                {/* Sarvam AI Localized Intelligence & Voice Agent */}
                <div className="hindi-explainer-section">
                  <div className="hindi-header" style={{ flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="hindi-title">🇮🇳 Sarvam AI Regional Intelligence</span>
                      {sarvamProviderUsed && (
                        <span className={`badge ${sarvamProviderUsed === 'sarvam' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: '10px' }}>
                          {sarvamProviderUsed === 'sarvam' ? 'Sarvam-105B Cloud' : 'Diagnostic Engine'}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        className="btn-primary"
                        style={{ fontSize: '12px', padding: '5px 12px' }}
                        onClick={() => handleExplainLocalized()}
                        disabled={explainingHindi}
                      >
                        {explainingHindi ? 'Analyzing...' : '⚡ Generate Briefing'}
                      </button>
                      <button
                        className="btn-secondary"
                        style={{ fontSize: '11px', padding: '5px 8px' }}
                        onClick={() => setSarvamModalOpen(true)}
                        title="Configure Sarvam AI Model & Keys"
                      >
                        ⚙️
                      </button>
                    </div>
                  </div>

                  {/* Regional Indian Language Quick Selector */}
                  <div className="sarvam-lang-pill-row">
                    {[
                      { code: 'hi', label: '🇮🇳 हिन्दी (Hindi)' },
                      { code: 'mr', label: '🚩 मराठी (Marathi)' },
                      { code: 'en', label: '🌐 English' },
                      { code: 'hi-Latn', label: '🗣️ Hinglish' },
                      { code: 'pa', label: '🌾 ਪੰਜਾਬੀ (Punjabi)' },
                      { code: 'ta', label: '🍇 தமிழ் (Tamil)' },
                      { code: 'te', label: '🌴 తెలుగు (Telugu)' },
                    ].map((l) => (
                      <button
                        key={l.code}
                        className={`sarvam-lang-pill ${sarvamLanguage === l.code ? 'active' : ''}`}
                        onClick={() => handleExplainLocalized(l.code)}
                        disabled={explainingHindi}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>

                  {hindiExplanation ? (
                    <div style={{ marginTop: '12px' }}>
                      <div className="hindi-box" style={{ whiteSpace: 'pre-line' }}>
                        {hindiExplanation}
                      </div>

                      <div className="audio-controls" style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <button
                            className={`audio-btn ${isPlayingAudio ? 'playing' : ''}`}
                            onClick={toggleSpeechAudio}
                          >
                            {isPlayingAudio ? (
                              <>
                                <span>⏹ Stop Voice</span>
                                <span className="audio-playing-indicator">
                                  <span className="audio-bar" />
                                  <span className="audio-bar" />
                                  <span className="audio-bar" />
                                  <span className="audio-bar" />
                                </span>
                              </>
                            ) : (
                              '🔊 Listen (Sarvam Neural Voice)'
                            )}
                          </button>

                          <select
                            value={sarvamSpeaker}
                            onChange={(e) => setSarvamSpeaker(e.target.value)}
                            style={{ background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155', borderRadius: '4px', padding: '4px 8px', fontSize: '11px' }}
                            title="Sarvam Bulbul Speaker Persona"
                          >
                            <option value="meera">Speaker: Meera (Female)</option>
                            <option value="shubh">Speaker: Shubh (Male)</option>
                          </select>
                        </div>

                        <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                          Bulbul:v1 TTS for rural field staff
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '12px', color: '#94a3b8', textAlign: 'center', padding: '14px 0' }}>
                      Select a language above or click 'Generate Briefing' to analyze root cause in Indian regional languages.
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <span style={{ fontSize: '36px' }}>🛡️</span>
                <p style={{ marginTop: '12px', fontWeight: '600', color: '#6ee7b7' }}>All Network Links Healthy</p>
                <p style={{ fontSize: '12px' }}>Normal telemetry observed across all hops. No open incidents.</p>
              </div>
            )}
          </div>
        </section>

        {/* 3. Village Subscribers & Business Operations Hub (Theme T3.2) */}
        <section className="card col-12">
          <div className="card-header">
            <div>
              <h2>👥 Village Subscriber Operations & Billing Hub</h2>
              <span className="caption">Manage accounts, collect payments via BharatPe/BHIM UPI QR, and broadcast outage updates</span>
            </div>

            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              {activeIncident && incidentSubscribers.length > 0 && (
                <button
                  className="btn-small btn-whatsapp"
                  onClick={() => setBroadcastModalOpen(true)}
                >
                  📢 Broadcast Outage Notice ({incidentSubscribers.length})
                </button>
              )}

              <div className="filter-tabs">
                <button
                  className={`tab-btn ${subscriberFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setSubscriberFilter('all')}
                >
                  All Subscribers ({allSubscribers.length})
                </button>
                <button
                  className={`tab-btn ${subscriberFilter === 'affected' ? 'active' : ''}`}
                  onClick={() => setSubscriberFilter('affected')}
                >
                  Affected ({incidentSubscribers.length})
                </button>
                <button
                  className={`tab-btn ${subscriberFilter === 'due' ? 'active' : ''}`}
                  onClick={() => setSubscriberFilter('due')}
                >
                  Payment Due ({allSubscribers.filter((s) => s.payment_status === 'due').length})
                </button>
              </div>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Subscriber ID</th>
                  <th>Customer / Business Name</th>
                  <th>Access Point</th>
                  <th>Plan & Rate</th>
                  <th>Payment Status</th>
                  <th>Due Date</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredSubscribers.length > 0 ? (
                  filteredSubscribers.map((sub) => {
                    const isImpacted = incidentSubscribers.some((is) => is.id === sub.id);
                    const planMeta = PLAN_DETAILS[sub.plan] || { price: 399, speed: '20M', label: 'Basic' };
                    const reminder = reminderRecords[sub.id];

                    return (
                      <tr key={sub.id} className={isImpacted ? 'row-alert' : ''}>
                        <td>
                          <code>{sub.id}</code>
                          {isImpacted && <span className="tag-suspect">IMPACTED</span>}
                        </td>
                        <td>
                          <strong>{sub.display_name}</strong>
                        </td>
                        <td>
                          <span className="badge badge-online">{sub.access_point_id}</span>
                        </td>
                        <td>
                          {sub.plan} (₹{planMeta.price}/mo)
                        </td>
                        <td>
                          <span className={`badge ${sub.payment_status === 'paid' ? 'badge-success' : 'badge-warning'}`}>
                            {sub.payment_status?.toUpperCase()}
                          </span>
                        </td>
                        <td>{sub.due_date}</td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {/* UPI Pay Modal Trigger */}
                            <button
                              className="btn-small btn-upi"
                              onClick={() => setUpiModalSub(sub)}
                              title="Collect via UPI QR Code"
                            >
                              ⚡ Collect UPI
                            </button>

                            {/* WhatsApp Reminder Direct Action */}
                            <a
                              href={`https://wa.me/?text=${encodeURIComponent(
                                `नमस्ते ${sub.display_name}, ग्राम नेट इंटरनेट बिल (₹${planMeta.price}) देय है। कृपया यूपीआई या सीएससी सेंटर पर भुगतान करें। धन्यवाद।`
                              )}`}
                              target="_blank"
                              rel="noreferrer"
                              className="btn-small btn-whatsapp"
                              style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}
                              onClick={() => handleSendReminder(sub.id)}
                            >
                              💬 WhatsApp
                            </a>

                            {reminder?.status === 'recorded' && (
                              <span style={{ fontSize: '10px', color: '#6ee7b7', alignSelf: 'center' }}>
                                ✓ Logged
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="7" className="empty-state">
                      No subscribers match the selected filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* 4. Fault Injection Lab (Preset Scenarios) */}
        <section className="card col-6">
          <div className="card-header">
            <h2>🧪 Telemetry & Fault Lab</h2>
            <span className="caption">Trigger controlled degradation to test explainable diagnostic engine</span>
          </div>

          <div className="preset-buttons">
            <button
              className="preset-btn"
              onClick={() => handleRunScenario('baseline', 'link', 'L1', 'low')}
            >
              🟢 Normal Baseline
            </button>
            <button
              className="preset-btn"
              onClick={() => handleRunScenario('degrade_link', 'link', 'L3', 'high')}
            >
              🟡 Degrade Bridge L3 (PtP Hop)
            </button>
            <button
              className="preset-btn"
              onClick={() => handleRunScenario('upstream_failure', 'node', 'GW1', 'high')}
            >
              🔴 Gateway L1 Failure (Fiber PoP)
            </button>
            <button
              className="preset-btn"
              onClick={() => handleRunScenario('access_point_failure', 'node', 'AP1', 'high')}
            >
              🟠 North AP1 Outage
            </button>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleRunScenario();
            }}
            className="lab-form"
          >
            <div className="form-group">
              <label>Custom Scenario</label>
              <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                <option value="degrade_link">Degrade Link (Latency / Loss)</option>
                <option value="access_point_failure">Access Point Failure</option>
                <option value="upstream_failure">Upstream Gateway Failure</option>
                <option value="ambiguous_fault">Ambiguous Flapping Link</option>
                <option value="baseline">Reset to Normal Baseline</option>
              </select>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Target Type</label>
                <select
                  value={targetType}
                  onChange={(e) => {
                    setTargetType(e.target.value);
                    setTargetId(e.target.value === 'link' ? 'L3' : 'AP1');
                  }}
                >
                  <option value="link">Link</option>
                  <option value="node">Node</option>
                </select>
              </div>

              <div className="form-group">
                <label>Target ID</label>
                <input
                  type="text"
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                  placeholder="e.g. L3 or AP1"
                  required
                />
              </div>

              <div className="form-group">
                <label>Severity</label>
                <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  <option value="low">Low (+35ms, 5% loss)</option>
                  <option value="medium">Medium (+90ms, 15% loss)</option>
                  <option value="high">High (+175ms, 25% loss)</option>
                </select>
              </div>
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Simulating Observations...' : '⚡ Inject Fault Scenario'}
            </button>
          </form>

          {activeRunId && (
            <div className="run-id-tag">
              Active Run ID: <code>{activeRunId}</code> · Injected fault kept isolated from diagnosis.
            </div>
          )}
        </section>

        {/* 5. Telemetry Measurements Table */}
        <section className="card col-6">
          <div className="card-header">
            <h2>📊 Run Observations & Telemetry</h2>
            <span className="caption">
              {activeRunId ? `Observation probe readings for: ${activeRunId}` : 'Awaiting simulation run'}
            </span>
          </div>

          {runMeasurements.length > 0 ? (
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Component</th>
                    <th>Latency</th>
                    <th>Packet Loss</th>
                    <th>Throughput</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runMeasurements.map((m, idx) => (
                    <tr key={m.component_id || idx}>
                      <td><code>{m.component_id}</code></td>
                      <td>{m.latency_ms != null ? `${m.latency_ms} ms` : '—'}</td>
                      <td style={{ color: m.packet_loss_pct > 0 ? '#ef4444' : 'inherit' }}>
                        {m.packet_loss_pct != null ? `${m.packet_loss_pct}%` : '—'}
                      </td>
                      <td>{m.throughput_mbps != null ? `${m.throughput_mbps} Mbps` : '—'}</td>
                      <td>
                        <span className={`status-pill ${m.connectivity_ok ? 'status-healthy' : 'status-down'}`}>
                          {m.connectivity_ok ? 'ONLINE' : 'DOWN'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <p>No telemetry probe observations recorded for this run.</p>
            </div>
          )}
        </section>
      </main>

      {/* ── UPI Scan & Pay Modal (Theme T3.2) ──────────────────────────────── */}
      {upiModalSub && (
        <div className="modal-overlay" onClick={() => setUpiModalSub(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚡ BharatPe / BHIM UPI Payment</h3>
              <button className="btn-inline-close" onClick={() => setUpiModalSub(null)}>✕</button>
            </div>

            <div className="upi-explainer-note">
              💡 <strong>Why QR in HopTrace?</strong> HackFront Theme T3.2 is 'Running a Village Internet Business'. In rural Bharat, ISP franchisees and field technicians collect ₹399/mo subscription fees on-the-spot from village Kirana stores and Panchayat offices using dynamic BharatPe/BHIM UPI QR links.
            </div>

            <p style={{ fontSize: '13px', color: '#94a3b8', margin: '0 0 12px 0' }}>
              Scan QR code with PhonePe, Google Pay, or Paytm to collect payment:
            </p>

            <div className="qr-wrapper">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(
                  getUpiUri(upiModalSub)
                )}`}
                alt="UPI QR Code"
                className="qr-image"
              />
            </div>

            <div className="upi-details">
              <div className="upi-row">
                <span style={{ color: '#94a3b8' }}>Subscriber:</span>
                <strong>{upiModalSub.display_name}</strong>
              </div>
              <div className="upi-row">
                <span style={{ color: '#94a3b8' }}>Plan:</span>
                <span>{upiModalSub.plan}</span>
              </div>
              <div className="upi-row">
                <span style={{ color: '#94a3b8' }}>Amount Due:</span>
                <strong style={{ color: '#10b981', fontSize: '15px' }}>
                  ₹{PLAN_DETAILS[upiModalSub.plan]?.price || 399}
                </strong>
              </div>
              <div className="upi-row">
                <span style={{ color: '#94a3b8' }}>UPI ID:</span>
                <code>hoptrace.gramin@sbi</code>
              </div>
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => {
                  navigator.clipboard.writeText(getUpiUri(upiModalSub));
                  showToast('UPI Link copied to clipboard!');
                }}
              >
                Copy UPI Link
              </button>
              <button
                className="btn-primary"
                onClick={() => {
                  setAllSubscribers((prev) =>
                    prev.map((s) => (s.id === upiModalSub.id ? { ...s, payment_status: 'paid' } : s))
                  );
                  setUpiModalSub(null);
                  showToast(`Payment collected for ${upiModalSub.display_name}!`);
                }}
              >
                ✓ Mark Paid (Cash/UPI)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Sarvam AI Configuration & Voice Agent Modal ─────────────────── */}
      {sarvamModalOpen && (
        <div className="modal-overlay" onClick={() => setSarvamModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '520px' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>🇮🇳</span>
                <h3 style={{ margin: 0 }}>Sarvam AI Cloud Intelligence</h3>
              </div>
              <button className="btn-inline-close" onClick={() => setSarvamModalOpen(false)}>✕</button>
            </div>

            <p style={{ fontSize: '12px', color: '#94a3b8', margin: '0 0 16px 0', lineHeight: '1.5' }}>
              HopTrace integrates <strong>Sarvam AI</strong> (India's premier sovereign AI platform) for natural Indian language incident analysis (<code>sarvam-105b</code>) and Bulbul neural text-to-speech (<code>bulbul:v1</code>).
            </p>

            <div className="sarvam-input-group">
              <label>Sarvam API Subscription Key (api-subscription-key)</label>
              <input
                type="password"
                placeholder="Paste your SARVAM_API_KEY here..."
                value={sarvamTempKey}
                onChange={(e) => setSarvamTempKey(e.target.value)}
              />
              <span style={{ fontSize: '11px', color: '#64748b', marginTop: '4px', display: 'block' }}>
                Stored locally in browser session & sent securely to backend endpoints. Get an API key at <strong>sarvam.ai</strong>.
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div className="sarvam-input-group" style={{ marginBottom: 0 }}>
                <label>LLM Explanation Model</label>
                <select disabled value="sarvam-105b">
                  <option value="sarvam-105b">sarvam-105b (Default)</option>
                  <option value="sarvam-2b">sarvam-2b</option>
                </select>
              </div>

              <div className="sarvam-input-group" style={{ marginBottom: 0 }}>
                <label>TTS Voice Speaker</label>
                <select value={sarvamSpeaker} onChange={(e) => setSarvamSpeaker(e.target.value)}>
                  <option value="meera">Meera (Hindi/Indian Female)</option>
                  <option value="shubh">Shubh (Hindi/Indian Male)</option>
                </select>
              </div>
            </div>

            <div style={{ background: '#0b1120', padding: '12px', borderRadius: '6px', fontSize: '12px', marginBottom: '16px', border: '1px solid #1e293b' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Connection Status:</span>
                <span className={`badge ${sarvamApiKey ? 'badge-success' : 'badge-warning'}`}>
                  {sarvamApiKey ? '● Key Configured' : '○ Offline Demo Mode'}
                </span>
              </div>
            </div>

            <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleTestSarvamKey}
                disabled={sarvamTesting || !sarvamTempKey.trim()}
              >
                {sarvamTesting ? 'Testing...' : 'Test Connection'}
              </button>

              <div style={{ display: 'flex', gap: '8px' }}>
                {sarvamApiKey && (
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ color: '#ef4444' }}
                    onClick={() => {
                      setSarvamApiKey('');
                      setSarvamTempKey('');
                      localStorage.removeItem('hoptrace_sarvam_key');
                      showToast('Sarvam API key cleared');
                    }}
                  >
                    Clear Key
                  </button>
                )}
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => {
                    const cleanKey = sarvamTempKey.trim();
                    setSarvamApiKey(cleanKey);
                    if (cleanKey) {
                      localStorage.setItem('hoptrace_sarvam_key', cleanKey);
                      showToast('Sarvam API key saved successfully!');
                    } else {
                      localStorage.removeItem('hoptrace_sarvam_key');
                    }
                    setSarvamModalOpen(false);
                  }}
                >
                  Save & Apply
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── WhatsApp Outage Broadcast Modal (Theme T3.2) ─────────────────── */}
      {broadcastModalOpen && (
        <div className="modal-overlay" onClick={() => setBroadcastModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📢 WhatsApp Outage Broadcast</h3>
              <button className="btn-inline-close" onClick={() => setBroadcastModalOpen(false)}>✕</button>
            </div>

            <p style={{ fontSize: '13px', color: '#94a3b8', margin: '0 0 10px 0' }}>
              Broadcast localized notice to all <strong>{incidentSubscribers.length} affected subscribers</strong>:
            </p>

            <div className="broadcast-box">
              <p style={{ margin: 0 }}>
                नमस्ते, ग्राम नेट सूचना: गाँव में नेटवर्क घटक ({activeIncident?.suspected_component_id || 'Tower'}) में तकनीकी समस्या के कारण आपकी इंटरनेट सेवा बाधित है। हमारी फील्ड टीम बहाली कार्य कर रही है।
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
              {incidentSubscribers.map((sub) => (
                <div key={sub.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0b1120', padding: '8px 12px', borderRadius: '6px', fontSize: '12px' }}>
                  <span>{sub.display_name || sub.id}</span>
                  <a
                    href={getWhatsAppBroadcastLink(sub, activeIncident)}
                    target="_blank"
                    rel="noreferrer"
                    className="btn-small btn-whatsapp"
                    style={{ textDecoration: 'none' }}
                  >
                    Send WhatsApp
                  </a>
                </div>
              ))}
            </div>

            <div className="modal-actions" style={{ marginTop: '16px' }}>
              <button className="btn-secondary" onClick={() => setBroadcastModalOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Alert Overlay */}
      <AlertOverlay />
    </div>
  );
}

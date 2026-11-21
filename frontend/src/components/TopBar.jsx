import useStore from '../store/appStore';

const LANG_OPTIONS = [
  { code: 'hi', label: 'हिंदी' },
  { code: 'en', label: 'EN' },
  { code: 'ta', label: 'தமிழ்' },
  { code: 'mr', label: 'मराठी' },
  { code: 'te', label: 'తెలుగు' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
  { code: 'bn', label: 'বাংলা' },
];

export default function TopBar({ onRefresh }) {
  const backendOnline = useStore(s => s.backendOnline);
  const wsConnected = useStore(s => s.wsConnected);
  const sarvamLanguage = useStore(s => s.sarvamLanguage);
  const setSarvamLanguage = useStore(s => s.setSarvamLanguage);
  const dashboardMode = useStore(s => s.dashboardMode);
  const setDashboardMode = useStore(s => s.setDashboardMode);
  const loading = useStore(s => s.loading);
  const networkStatus = useStore(s => s.networkStatus);
  const cascadeDetected = useStore(s => s.cascadeDetected);
  const telemetryDataSource = useStore(s => s.telemetryDataSource);
  const dataMode = useStore(s => s.dataMode);
  const setDataMode = useStore(s => s.setDataMode);
  const agents = useStore(s => s.agents);
  const liveMeasurements = useStore(s => s.liveMeasurements);
  const topology = useStore(s => s.topology);
  const activeIncident = useStore(s => s.activeIncident);
  const alertArmed = useStore(s => s.alertArmed);
  const setAlertArmed = useStore(s => s.setAlertArmed);
  const voiceMuted = useStore(s => s.voiceMuted);
  const setVoiceMuted = useStore(s => s.setVoiceMuted);
  const alertOpen = useStore(s => s.alertOpen);
  const setAlertOpen = useStore(s => s.setAlertOpen);

  const isLive =
    telemetryDataSource === 'live' ||
    dataMode === 'live' ||
    topology?.data_source === 'live' ||
    (Array.isArray(liveMeasurements) && liveMeasurements.some(m => m.data_source === 'live'));

  const silentAgent = Array.isArray(agents) ? agents.find(a => a.status === 'silent') : null;
  const isAgentSilent = Boolean(silentAgent);
  const hasAgents = Array.isArray(agents) && agents.length > 0;

  return (
    <header className="flex items-center gap-3 px-4 py-2 bg-[#060e1c] border-b border-slate-800 shrink-0 flex-wrap sm:flex-nowrap">
      {/* Brand */}
      <div className="flex items-center gap-2 mr-2 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-black text-sm">HT</div>
        <div className="hidden md:block">
          <div className="text-white font-bold text-sm leading-tight">HopTrace</div>
          <div className="text-slate-500 text-xs">Rural ISP Intelligence</div>
        </div>
      </div>

      {/* Network status pill */}
      <div className={`hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs font-medium ${
        networkStatus === 'healthy' ? 'border-emerald-700 bg-emerald-950 text-emerald-400' :
        networkStatus === 'degraded' ? 'border-amber-700 bg-amber-950 text-amber-400' :
        'border-red-700 bg-red-950 text-red-400'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${networkStatus === 'healthy' ? 'bg-emerald-400' : networkStatus === 'degraded' ? 'bg-amber-400' : 'bg-red-400'} ${networkStatus !== 'healthy' ? 'animate-pulse' : ''}`} />
        {networkStatus.toUpperCase()}
        {cascadeDetected && <span className="ml-1 text-red-300">· CASCADE</span>}
      </div>

      {/* Interactive Mode Switcher: Demo Mode <-> Live Edge Telemetry */}
      <button
        type="button"
        data-testid="telemetry-source-badge"
        onClick={() => {
          const next = dataMode === 'live' ? 'demo' : 'live';
          setDataMode(next);
          if (next === 'live') {
            const cur = useStore.getState().liveMeasurements;
            if (cur && cur.length > 0) {
              const noDataBatch = cur.map(m => ({
                ...m,
                freshness: 'no_data',
                latency_ms: null,
                packet_loss_pct: null,
                throughput_mbps: null,
              }));
              useStore.getState().setLiveTelemetry({
                data_mode: 'live',
                data_source: 'live',
                measurements: noDataBatch,
              });
            }
          }
        }}
        title={`Click to switch between Demo Simulation and Live Telemetry (Current: ${dataMode === 'live' ? 'Live' : 'Demo'})`}
        className={`hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs font-semibold transition-all cursor-pointer hover:scale-105 active:scale-95 ${
          isLive
            ? 'border-emerald-600 bg-emerald-950 text-emerald-300 hover:border-emerald-400'
            : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-500 hover:text-slate-200'
        }`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
        <span>{isLive ? '● Live Telemetry' : '○ Demo Mode'}</span>
        <span className="text-[10px] text-slate-500 ml-0.5 uppercase tracking-wider font-mono">⇄ Switch</span>
      </button>

      {/* Monitoring Agent Status Chip (live mode only, hidden in demo) */}
      {dataMode === 'live' && (
        <div
          data-testid="agent-status-chip"
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs font-semibold ${
            !hasAgents
              ? 'border-slate-700 bg-slate-900 text-slate-400'
              : isAgentSilent
              ? 'border-red-700 bg-red-950 text-red-300'
              : 'border-emerald-700 bg-emerald-950 text-emerald-300'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              !hasAgents
                ? 'bg-slate-500'
                : isAgentSilent
                ? 'bg-red-400 animate-pulse'
                : 'bg-emerald-400'
            }`}
          />
          <span className="capitalize">
            {!hasAgents
              ? 'no agent connected'
              : isAgentSilent
              ? `silent ${silentAgent.silent_for_seconds ?? 0}s`
              : 'online'}
          </span>
        </div>
      )}

      <div className="flex-1" />

      {/* Language selector dropdown */}
      <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs">
        <span className="text-slate-400">🌐</span>
        <select
          value={sarvamLanguage}
          onChange={(e) => setSarvamLanguage(e.target.value)}
          aria-label="Sarvam AI Language"
          className="bg-transparent text-slate-200 text-xs font-medium focus:outline-none cursor-pointer"
        >
          {LANG_OPTIONS.map(l => (
            <option key={l.code} value={l.code} className="bg-slate-900 text-slate-200">
              {l.label}
            </option>
          ))}
        </select>
      </div>

      {/* Mode switcher */}
      <div className="flex items-center gap-0.5 bg-slate-900 rounded-lg p-0.5 border border-slate-700">
        {['noc', 'business'].map(m => (
          <button
            key={m}
            onClick={() => setDashboardMode(m)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              dashboardMode === m ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {m === 'noc' ? '⚡ NOC' : '🏪 Business'}
          </button>
        ))}
      </div>

      {/* WS indicator */}
      <div className={`flex items-center gap-1 text-xs ${wsConnected ? 'text-emerald-400' : 'text-slate-500'}`}>
        <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
        <span className="hidden sm:inline">{wsConnected ? 'Live' : 'Offline'}</span>
      </div>

      {/* Backend status */}
      <div className={`flex items-center gap-1 text-xs ${backendOnline ? 'text-emerald-400' : 'text-red-400'}`}>
        <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-400' : 'bg-red-500'}`} />
        <span className="hidden sm:inline">API</span>
      </div>

      {/* Demo Voice & Alert Controls */}
      <div className="hidden lg:flex items-center gap-1.5" aria-label="Demo Voice Controls">
        <button
          type="button"
          onClick={() => setAlertArmed(prev => !prev)}
          title="Arm audio for immediate playback on fault"
          className={`flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-semibold whitespace-nowrap transition-colors ${
            alertArmed
              ? 'border-emerald-600 bg-emerald-950/80 text-emerald-300'
              : 'border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>{alertArmed ? '● Armed' : '○ Arm Audio Demo'}</span>
        </button>

        <button
          type="button"
          onClick={() => setVoiceMuted(prev => !prev)}
          title="Toggle Voice Mute"
          className={`flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-semibold whitespace-nowrap transition-colors ${
            voiceMuted
              ? 'border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200'
              : 'border-blue-600/60 bg-blue-950/60 text-blue-300 hover:text-blue-200'
          }`}
        >
          <span>{voiceMuted ? '🔇 Muted' : '🔊 Voice On'}</span>
        </button>

        {activeIncident && !alertOpen && (
          <button
            type="button"
            onClick={() => setAlertOpen(true)}
            title="Replay Alert Overlay"
            className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-red-700 bg-red-950/80 text-red-300 hover:bg-red-900 text-xs font-semibold whitespace-nowrap transition-colors"
          >
            <span>🚨 Replay Alert</span>
          </button>
        )}
      </div>

      {/* Refresh */}
      <button
        onClick={onRefresh}
        disabled={loading}
        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-300 text-xs rounded-lg transition-colors disabled:opacity-50"
      >
        {loading ? '↻' : '⟳'} Refresh
      </button>
    </header>
  );
}

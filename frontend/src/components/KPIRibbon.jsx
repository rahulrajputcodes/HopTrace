import useStore from '../store/appStore';
import { isHealthyForKpi } from '../lib/freshness';

function KPICard({ title, value, sub, statusDot, needsAttention, children }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3 rounded-xl border border-slate-800 bg-[#0a1628] min-w-0 transition-colors">
      <div className="flex items-center justify-between gap-1.5">
        <span className="text-xs text-slate-400 font-medium truncate">{title}</span>
        {statusDot && <span className={`w-2 h-2 rounded-full shrink-0 ${statusDot}`} />}
      </div>
      <div className={`text-xl font-bold leading-tight truncate ${needsAttention ? 'text-amber-400' : 'text-white'}`}>
        {value}
      </div>
      {sub && <span className="text-xs text-slate-400 leading-tight truncate">{sub}</span>}
      {children}
    </div>
  );
}

export default function KPIRibbon() {
  const allSubscribers = useStore(s => s.allSubscribers);
  const affectedSubscribers = useStore(s => s.affectedSubscribers);
  const villages = useStore(s => s.villages);
  const topology = useStore(s => s.topology);
  const liveMeasurements = useStore(s => s.liveMeasurements);
  const riskSnapshot = useStore(s => s.riskSnapshot);
  const activeIncident = useStore(s => s.activeIncident);
  const cascadeDetected = useStore(s => s.cascadeDetected);
  const flappingLinks = useStore(s => s.flappingLinks);

  const totalSubs = allSubscribers.length || 20;
  const affectedCount = affectedSubscribers.length;
  const activeSubs = Math.max(0, totalSubs - affectedCount);

  let mrr = 0;
  let paidCount = 0;
  const planPrices = { Basic: 399, Enterprise: 999, Community: 0 };
  allSubscribers.forEach(s => {
    mrr += planPrices[s.plan] ?? 399;
    if (s.payment_status === 'paid') paidCount++;
  });
  const collectionRate = totalSubs > 0 ? Math.round((paidCount / totalSubs) * 100) : 100;

  const villageStatuses = villages.length > 0 ? villages : [
    { name: 'Rampur', status: 'healthy', health: 'healthy' },
    { name: 'Bhatpur', status: 'healthy', health: 'healthy' },
    { name: 'Daulatpur', status: 'healthy', health: 'healthy' },
  ];

  const healthyVillageCount = villageStatuses.filter(v => (v.status || v.health) === 'healthy').length;
  const allVillagesHealthy = healthyVillageCount === villageStatuses.length;

  const villageHealthColor = (h) =>
    h === 'healthy' ? 'bg-emerald-400' : h === 'degraded' ? 'bg-amber-400' : 'bg-red-500';

  // ── Calculate link freshness and KPI health ─────────────────────────────
  const rawLinks = topology?.links || [];
  const liveMap = new Map();
  (liveMeasurements || []).forEach(m => {
    if (m?.link_id) liveMap.set(m.link_id, m);
  });

  const linksWithMetadata = rawLinks.map(l => {
    const live = liveMap.get(l.id);
    const snap = riskSnapshot?.[l.id];
    const freshness = live?.freshness || snap?.freshness || (l.data_source === 'live' ? 'live' : 'simulated');
    return {
      ...l,
      freshness,
      live,
      risk_score: snap?.risk_score ?? live?.risk_score ?? l.risk_score ?? 0,
      isDown: live?.connectivity_ok === false || l.connectivity_ok === false,
    };
  });

  const noDataLinks = linksWithMetadata.filter(l => l.freshness === 'no_data');
  const noDataCount = noDataLinks.length;
  const linksWithData = linksWithMetadata.filter(l => l.freshness !== 'no_data');
  const healthyLinksWithData = linksWithData.filter(isHealthyForKpi);
  const healthyPercent = linksWithData.length > 0
    ? Math.round((healthyLinksWithData.length / linksWithData.length) * 100)
    : 0;

  return (
  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 px-3 pt-2 pb-1 shrink-0">
      {/* Active Connections */}
      <KPICard
        statusDot={affectedCount > 0 ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}
        needsAttention={affectedCount > 0}
        title="Active Connections"
        value={`${activeSubs} / ${totalSubs}`}
        sub={affectedCount > 0 ? `⚠ ${affectedCount} subscriber(s) impacted` : '100% Village coverage active'}
      />

      {/* MRR */}
      <KPICard
        statusDot="bg-emerald-400"
        title="Monthly Revenue (MRR)"
        value={`₹${mrr.toLocaleString('en-IN')}`}
        sub={`${collectionRate}% collected · ${paidCount} paid`}
      />

      {/* Village status & Link Health */}
      <KPICard
        statusDot={allVillagesHealthy && noDataCount === 0 ? 'bg-emerald-400' : (noDataCount > 0 ? 'bg-slate-400' : 'bg-amber-400')}
        needsAttention={!allVillagesHealthy || noDataCount > 0}
        title="Village & Link Health"
        value={`${healthyPercent}% Healthy`}
        sub={
          noDataCount > 0
            ? `${noDataCount} No Data · ${healthyLinksWithData.length}/${linksWithData.length} monitored`
            : `${healthyVillageCount}/${villageStatuses.length} Villages · ${healthyLinksWithData.length}/${linksWithData.length || 14} links ok`
        }
      >
        <div className="flex items-center justify-between gap-1 mt-0.5 flex-wrap">
          <div className="flex items-center gap-1.5">
            {villageStatuses.map(v => (
              <div key={v.name || v.village_id} className="flex items-center gap-1">
                <span className={`w-2 h-2 rounded-full ${villageHealthColor(v.status || v.health)}`} />
                <span className="text-xs text-slate-400">{v.name}</span>
              </div>
            ))}
          </div>
          {noDataCount > 0 && (
            <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700 text-xs font-mono">
              {noDataCount} no data
            </span>
          )}
        </div>
      </KPICard>

      {/* Fault Detection */}
      <KPICard
        accent={activeIncident ? 'red' : 'green'}
        title="Fault Detection"
        value={
          activeIncident
            ? <span className="text-red-400">{activeIncident.suspected_component_id || 'ALARM'}</span>
            : <span className="text-emerald-400">HEALTHY</span>
        }
        sub={
          activeIncident
            ? `${Math.round((activeIncident.confidence_score || 0.9) * 100)}% confidence${cascadeDetected ? ' � CASCADE' : ''}`
            : `Zero open incidents � ${flappingLinks.length > 0 ? flappingLinks.length + ' flapping' : 'All stable'}`
        }
      />
    </div>
  );
}

import useStore from '../store/appStore';

function KPICard({ title, value, sub, accent, children }) {
  const border = {
    blue:   'border-blue-800 bg-blue-950/40',
    green:  'border-emerald-800 bg-emerald-950/40',
    amber:  'border-amber-800 bg-amber-950/40',
    purple: 'border-purple-800 bg-purple-950/40',
    red:    'border-red-800 bg-red-950/40',
  }[accent] || 'border-slate-700 bg-slate-900';

  return (
    <div className={`flex flex-col gap-1 px-4 py-3 rounded-xl border ${border} min-w-0`}>
      <span className="text-xs text-slate-400 font-medium truncate">{title}</span>
      <div className="text-xl font-bold text-white leading-tight truncate">{value}</div>
      {sub && <span className="text-xs text-slate-400 leading-tight">{sub}</span>}
      {children}
    </div>
  );
}

export default function KPIRibbon() {
  const allSubscribers = useStore(s => s.allSubscribers);
  const affectedSubscribers = useStore(s => s.affectedSubscribers);
  const activeIncident = useStore(s => s.activeIncident);
  const villages = useStore(s => s.villages);
  const networkStatus = useStore(s => s.networkStatus);
  const cascadeDetected = useStore(s => s.cascadeDetected);
  const flappingLinks = useStore(s => s.flappingLinks);

  const totalSubs = allSubscribers.length || 20;
  const affectedCount = affectedSubscribers.length;
  const activeSubs = totalSubs - affectedCount;

  let mrr = 0;
  let paidCount = 0;
  const planPrices = { Basic: 399, Enterprise: 999, Community: 0 };
  allSubscribers.forEach(s => {
    mrr += planPrices[s.plan] ?? 399;
    if (s.payment_status === 'paid') paidCount++;
  });
  const collectionRate = totalSubs > 0 ? Math.round((paidCount / totalSubs) * 100) : 100;

  const villageStatuses = villages.length > 0 ? villages : [
    { name: 'Rampur', health: 'healthy' },
    { name: 'Bhatpur', health: 'healthy' },
    { name: 'Daulatpur', health: 'healthy' },
  ];

  const villageHealthColor = (h) =>
    h === 'healthy' ? 'bg-emerald-400' : h === 'degraded' ? 'bg-amber-400' : 'bg-red-500';

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 px-3 pt-2 pb-1 shrink-0">
      {/* Active Connections */}
      <KPICard
        accent={affectedCount > 0 ? 'red' : 'blue'}
        title="Active Connections"
        value={`${activeSubs} / ${totalSubs}`}
        sub={affectedCount > 0 ? `⚠ ${affectedCount} subscriber(s) impacted` : '100% Village coverage active'}
      />

      {/* MRR */}
      <KPICard
        accent="green"
        title="Monthly Revenue (MRR)"
        value={`₹${mrr.toLocaleString('en-IN')}`}
        sub={`${collectionRate}% collected · ${paidCount} paid`}
      />

      {/* Village status */}
      <KPICard
        accent="purple"
        title="Village Network Status"
        value={villageStatuses.filter(v => v.health === 'healthy').length + '/' + villageStatuses.length + ' Healthy'}
      >
        <div className="flex items-center gap-2 mt-0.5">
          {villageStatuses.map(v => (
            <div key={v.name} className="flex items-center gap-1">
              <span className={`w-2 h-2 rounded-full ${villageHealthColor(v.health)}`} />
              <span className="text-[10px] text-slate-400">{v.name}</span>
            </div>
          ))}
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
            ? `${Math.round((activeIncident.confidence_score || 0.9) * 100)}% confidence${cascadeDetected ? ' · CASCADE' : ''}`
            : `Zero open incidents · ${flappingLinks.length > 0 ? flappingLinks.length + ' flapping' : 'All stable'}`
        }
      />

      {/* Solar & Power */}
      <KPICard
        accent="amber"
        title="Solar & Power Fleet"
        value="12.7V avg"
        sub="☀️ 2 Solar towers · Grid PoP nominal"
      />
    </div>
  );
}

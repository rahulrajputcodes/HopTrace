import useStore from '../store/appStore';

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

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 px-3 pt-2 pb-1 shrink-0">
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

      {/* Village status */}
      <KPICard
        statusDot={allVillagesHealthy ? 'bg-emerald-400' : 'bg-amber-400'}
        needsAttention={!allVillagesHealthy}
        title="Village Network Status"
        value={`${healthyVillageCount} / ${villageStatuses.length} Healthy`}
      >
        <div className="flex items-center gap-2 mt-0.5">
          {villageStatuses.map(v => (
            <div key={v.name || v.village_id} className="flex items-center gap-1">
              <span className={`w-2 h-2 rounded-full ${villageHealthColor(v.status || v.health)}`} />
              <span className="text-xs text-slate-400">{v.name}</span>
            </div>
          ))}
        </div>
      </KPICard>

      {/* Solar & Power */}
      <KPICard
        statusDot="bg-emerald-400"
        title="Solar & Power Fleet"
        value="12.7V avg"
        sub="☀️ 2 Solar towers · Grid PoP nominal"
      />
    </div>
  );
}

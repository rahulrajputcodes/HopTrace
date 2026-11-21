import { useState, useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import useStore from '../../store/appStore';
import { useApi } from '../../hooks/useApi';
import { getSubscriberVillage, getSubscriberAp } from './helpers';

const PLAN_META = {
  Basic:      { price: 399,  color: '#3b82f6', speed: '20 Mbps' },
  Enterprise: { price: 999,  color: '#8b5cf6', speed: '100 Mbps' },
  Community:  { price: 0,    color: '#10b981', speed: '50 Mbps' },
};

const PAYMENT_BADGE = {
  paid:    'bg-emerald-900 border-emerald-700 text-emerald-300',
  due:     'bg-amber-900 border-amber-700 text-amber-300',
  overdue: 'bg-red-900 border-red-700 text-red-300',
};

function QRModal({ subscriber, onClose }) {
  const plan = PLAN_META[subscriber?.plan] || PLAN_META.Basic;
  const upiUri = `upi://pay?pa=hoptrace.gramin@sbi&pn=HopTrace+Rural+ISP&am=${plan.price}&tn=${encodeURIComponent((subscriber?.id || '') + ' Internet Bill')}&cu=INR`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-[#0d1829] border border-slate-700 rounded-2xl p-6 w-80 text-center shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="text-white font-bold mb-1">{subscriber?.display_name || subscriber?.id}</div>
        <div className="text-slate-400 text-xs mb-4">{subscriber?.plan} Plan · ₹{plan.price}/month</div>
        <div className="bg-white rounded-xl p-4 mx-auto w-48 h-48 flex items-center justify-center mb-4">
          <div className="text-center text-xs text-gray-600 break-all">
            <div className="text-2xl mb-2">📱</div>
            UPI QR<br/>
            <span className="text-[9px]">hoptrace.gramin@sbi</span>
          </div>
        </div>
        <div className="text-emerald-400 font-bold text-2xl mb-1">₹{plan.price}</div>
        <div className="text-slate-500 text-xs mb-4">Scan with PhonePe · GPay · Paytm</div>
        <div className="flex gap-2">
          <button
            onClick={() => { try { window.open(upiUri); } catch { /* ignore popup block */ } }}
            className="flex-1 py-2 bg-emerald-700 hover:bg-emerald-600 text-white text-xs rounded-lg transition-colors font-medium"
          >
            Open UPI App
          </button>
          <button onClick={onClose} className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded-lg transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SubscriberOps() {
  const allSubscribers = useStore(s => s.allSubscribers);
  const affectedSubscribers = useStore(s => s.affectedSubscribers);
  const villages = useStore(s => s.villages);
  const dashboardMode = useStore(s => s.dashboardMode);
  const { sendReminder } = useApi();

  const [filter, setFilter] = useState('all');
  const [upiModal, setUpiModal] = useState(null);
  const [sentReminders, setSentReminders] = useState({});

  const affectedIds = useMemo(() => new Set(affectedSubscribers.map(s => s.id)), [affectedSubscribers]);

  const filteredSubs = useMemo(() => {
    if (filter === 'affected') return allSubscribers.filter(s => affectedIds.has(s.id));
    if (filter === 'due')      return allSubscribers.filter(s => s.payment_status === 'due' || s.payment_status === 'overdue');
    return allSubscribers;
  }, [allSubscribers, affectedIds, filter]);

  const pieData = useMemo(() => {
    const counts = {};
    allSubscribers.forEach(s => { counts[s.plan] = (counts[s.plan] || 0) + 1; });
    return Object.entries(counts).map(([plan, count]) => ({
      name: plan,
      value: count,
      revenue: (PLAN_META[plan]?.price || 0) * count,
    }));
  }, [allSubscribers]);

  const totalMRR = allSubscribers.reduce((sum, s) => sum + (PLAN_META[s.plan]?.price || 0), 0);
  const dueCount = allSubscribers.filter(s => s.payment_status === 'due' || s.payment_status === 'overdue').length;

  const handleReminder = async (sub) => {
    setSentReminders(p => ({ ...p, [sub.id]: 'sending' }));
    try {
      await sendReminder(sub.id, 'hi');
      setSentReminders(p => ({ ...p, [sub.id]: 'sent' }));
    } catch {
      setSentReminders(p => ({ ...p, [sub.id]: 'error' }));
    }
  };

  const getWALink = (sub) => {
    const msg = `नमस्ते ${sub.display_name || sub.id},\n\nग्राम नेट सूचना: आपकी इंटरनेट सेवा में अस्थायी व्यवधान है। हमारी टीम कार्य कर रही है। — हॉपट्रेस ग्रामीण इंटरनेट`;
    return `https://wa.me/?text=${encodeURIComponent(msg)}`;
  };

  return (
    <div className="bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
        <span className="text-sm">👥</span>
        <span className="text-white font-semibold text-sm">Subscriber Operations</span>
        <span className="text-slate-500 text-xs hidden sm:inline">· {allSubscribers.length} subscribers across 3 villages</span>
        <div className="flex items-center gap-0.5 ml-auto bg-slate-900 rounded-lg p-0.5 border border-slate-700">
          {[
            { id: 'all',      label: `All (${allSubscribers.length})` },
            { id: 'affected', label: `Affected (${affectedSubscribers.length})` },
            { id: 'due',      label: `Due (${dueCount})` },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                filter === tab.id ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className={dashboardMode === 'business' ? 'grid grid-cols-1 lg:grid-cols-3' : ''}>
        {/* Table */}
        <div className={dashboardMode === 'business' ? 'lg:col-span-2 border-r border-slate-800' : ''}>
          <div className="overflow-x-auto max-h-64">
            <table className="w-full text-xs">
              <thead className="bg-slate-900/80 sticky top-0 z-10">
                <tr>
                  {['Subscriber', 'Village', 'AP', 'Plan', 'Status', 'Actions'].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-slate-500 font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredSubs.map(sub => {
                  const isAffected = affectedIds.has(sub.id);
                  const reminder = sentReminders[sub.id];
                  return (
                    <tr
                      key={sub.id}
                      className={`border-t border-slate-800/60 transition-colors ${
                        isAffected ? 'bg-red-950/20 hover:bg-red-950/30' : 'hover:bg-slate-800/30'
                      }`}
                    >
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          {isAffected && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse shrink-0"/>}
                          <div>
                            <div className="text-slate-200 font-medium whitespace-nowrap">{sub.display_name || sub.id}</div>
                            <div className="text-slate-500 text-[10px]">{sub.id}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-slate-400 whitespace-nowrap">{getSubscriberVillage(sub, villages)}</td>
                      <td className="px-3 py-2 text-slate-400">{getSubscriberAp(sub)}</td>
                      <td className="px-3 py-2">
                        <span
                          className="px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap"
                          style={{
                            background: (PLAN_META[sub.plan]?.color || '#64748b') + '22',
                            color: PLAN_META[sub.plan]?.color || '#94a3b8',
                          }}
                        >
                          {sub.plan}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-medium capitalize whitespace-nowrap ${PAYMENT_BADGE[sub.payment_status] || 'bg-slate-800 border-slate-600 text-slate-400'}`}>
                          {sub.payment_status || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleReminder(sub)}
                            disabled={reminder === 'sending' || reminder === 'sent'}
                            title="Send payment reminder"
                            className={`px-2 py-1 rounded text-[10px] font-medium transition-colors disabled:opacity-50 ${
                              reminder === 'sent'  ? 'bg-emerald-900 text-emerald-300' :
                              reminder === 'error' ? 'bg-red-900 text-red-300' :
                              'bg-slate-700 hover:bg-slate-600 text-slate-300'
                            }`}
                          >
                            {reminder === 'sent' ? '✓' : reminder === 'error' ? '✗' : '💬'}
                          </button>
                          <button
                            onClick={() => setUpiModal(sub)}
                            title="UPI payment QR"
                            className="px-2 py-1 bg-emerald-900 hover:bg-emerald-800 text-emerald-300 rounded text-[10px] transition-colors"
                          >
                            ₹QR
                          </button>
                          {isAffected && (
                            <a
                              href={getWALink(sub)}
                              target="_blank" rel="noopener noreferrer"
                              title="WhatsApp outage notice"
                              className="px-2 py-1 bg-green-900 hover:bg-green-800 text-green-300 rounded text-[10px] transition-colors"
                            >
                              WA
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredSubs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-6 text-slate-500 text-xs">
                      No subscribers match the current filter
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Billing sidebar (business mode) */}
        {dashboardMode === 'business' && (
          <div className="p-4 space-y-3">
            <div className="text-[10px] text-slate-500 font-medium uppercase">Billing Overview</div>
            <div>
              <div className="text-2xl font-bold text-white">₹{totalMRR.toLocaleString('en-IN')}</div>
              <div className="text-xs text-slate-500">Monthly Recurring Revenue</div>
            </div>
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={45} paddingAngle={3}>
                  {pieData.map(entry => (
                    <Cell key={entry.name} fill={PLAN_META[entry.name]?.color || '#64748b'}/>
                  ))}
                </Pie>
                <Tooltip
                  formatter={(val, name, props) => [`${val} subs · ₹${props.payload.revenue}`, props.payload.name]}
                  contentStyle={{ background: '#0d1829', border: '1px solid #334155', borderRadius: '8px', fontSize: '10px' }}
                />
                <Legend iconSize={8} wrapperStyle={{ fontSize: '10px', color: '#94a3b8' }}/>
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-1.5">
              {pieData.map(p => (
                <div key={p.name} className="flex items-center gap-2 text-xs">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: PLAN_META[p.name]?.color || '#64748b' }}/>
                  <span className="text-slate-400 flex-1">{p.name}</span>
                  <span className="text-slate-300 font-medium">{p.value}</span>
                  <span className="text-slate-500">₹{p.revenue.toLocaleString('en-IN')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {upiModal && <QRModal subscriber={upiModal} onClose={() => setUpiModal(null)}/>}
    </div>
  );
}

import { useState, useEffect } from 'react';
import useStore from '../../store/appStore';
import { useApi } from '../../hooks/useApi';

export default function BusinessImpactPanel() {
  const activeIncident = useStore(s => s.activeIncident);
  const allSubscribers = useStore(s => s.allSubscribers);
  const { fetchBusinessImpact, sendReminder } = useApi();

  const [rawImpactData, setImpactData] = useState(null);
  const impactData = activeIncident ? rawImpactData : null;
  const [loading, setLoading] = useState(false);
  const [reminderStates, setReminderStates] = useState({});
  const [bulkSending, setBulkSending] = useState(false);

  useEffect(() => {
    const incidentId = activeIncident?.id;
    if (!incidentId) {
      return;
    }
    let ignore = false;
    fetchBusinessImpact(incidentId)
      .then((data) => {
        if (!ignore) {
          setImpactData(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setImpactData(null);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [activeIncident?.id, fetchBusinessImpact]);

  const handleSendReminder = async (subId) => {
    setReminderStates(prev => ({ ...prev, [subId]: 'sending' }));
    try {
      await sendReminder(subId, 'hi');
      setReminderStates(prev => ({ ...prev, [subId]: 'sent' }));
    } catch {
      setReminderStates(prev => ({ ...prev, [subId]: 'error' }));
    }
  };

  const handleBulkReminders = async () => {
    if (!impactData?.affected_subscribers?.length) return;
    setBulkSending(true);
    for (const sub of impactData.affected_subscribers) {
      setReminderStates(prev => ({ ...prev, [sub.id]: 'sending' }));
      try {
        await sendReminder(sub.id, 'hi');
        setReminderStates(prev => ({ ...prev, [sub.id]: 'sent' }));
      } catch {
        setReminderStates(prev => ({ ...prev, [sub.id]: 'error' }));
      }
    }
    setBulkSending(false);
  };

  const totalMRR = allSubscribers.reduce((sum, s) => sum + (s.plan_price ?? (s.plan === 'Enterprise' ? 999 : s.plan === 'Community' ? 0 : 399)), 0);

  return (
    <div className="bg-[#0a1628] border border-slate-800 rounded-xl overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
        <div className="flex items-center gap-2">
          <span className="text-amber-400 text-base">💼</span>
          <div>
            <div className="text-white font-semibold text-sm leading-tight">Business & Revenue Impact</div>
            <div className="text-slate-400 text-[11px]">SLA compensation & subscriber revenue monitor</div>
          </div>
        </div>
        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
          activeIncident ? 'bg-red-950/80 border-red-700 text-red-300' : 'bg-emerald-950/80 border-emerald-700 text-emerald-300'
        }`}>
          {activeIncident ? 'Outage Active' : 'All Clear'}
        </span>
      </div>

      {/* Body */}
      <div className="p-3 space-y-3 overflow-y-auto max-h-[32rem]">
        {/* Metric Cards Row */}
        <div className="grid grid-cols-2 gap-2">
          {/* Revenue at Risk */}
          <div className={`p-3 rounded-lg border ${
            impactData?.revenue_at_risk > 0
              ? 'bg-red-950/30 border-red-800'
              : 'bg-slate-900/40 border-slate-800'
          }`}>
            <span className="text-[10px] text-slate-400 uppercase font-medium">Revenue at Risk</span>
            <div className={`text-xl font-bold mt-0.5 ${
              impactData?.revenue_at_risk > 0 ? 'text-red-400' : 'text-emerald-400'
            }`}>
              ₹{(impactData?.revenue_at_risk ?? 0).toLocaleString('en-IN')}
            </div>
            <span className="text-[10px] text-slate-500">
              {impactData?.affected_count ? `${impactData.affected_count} household(s) down` : '100% Protected'}
            </span>
          </div>

          {/* SLA Credit Owed */}
          <div className={`p-3 rounded-lg border ${
            impactData?.estimated_sla_credit_owed > 0
              ? 'bg-amber-950/30 border-amber-800'
              : 'bg-slate-900/40 border-slate-800'
          }`}>
            <span className="text-[10px] text-slate-400 uppercase font-medium">SLA Credit Owed</span>
            <div className={`text-xl font-bold mt-0.5 ${
              impactData?.estimated_sla_credit_owed > 0 ? 'text-amber-400' : 'text-slate-300'
            }`}>
              ₹{(impactData?.estimated_sla_credit_owed ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <span className="text-[10px] text-slate-500">
              {impactData?.outage_duration_formatted ? `Duration: ${impactData.outage_duration_formatted}` : 'Zero penalty'}
            </span>
          </div>
        </div>

        {/* Affected Households by Village */}
        {impactData && impactData.households_by_village && Object.keys(impactData.households_by_village).length > 0 ? (
          <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-300 font-medium">
              <span>Affected Households by Village</span>
              <span className="text-amber-400 font-bold">{impactData.affected_count} Total</span>
            </div>
            <div className="grid grid-cols-3 gap-2 pt-1">
              {Object.entries(impactData.households_by_village).map(([village, count]) => (
                <div key={village} className="bg-slate-950/70 p-2 rounded border border-slate-800 text-center">
                  <div className="text-[11px] text-slate-400 truncate">{village}</div>
                  <div className={`text-base font-bold mt-0.5 ${count > 0 ? 'text-red-400' : 'text-slate-500'}`}>
                    {count}
                  </div>
                  <div className="text-[9px] text-slate-500">households</div>
                </div>
              ))}
            </div>
          </div>
        ) : !activeIncident ? (
          /* Healthy Village Distribution */
          <div className="p-3 bg-slate-900/40 rounded-lg border border-slate-800/80 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
              <span>Village Coverage (Healthy)</span>
              <span className="text-emerald-400 text-[11px]">₹{totalMRR.toLocaleString('en-IN')} Total MRR</span>
            </div>
            <div className="grid grid-cols-3 gap-2 pt-0.5">
              <div className="bg-slate-950/50 p-2 rounded border border-slate-800 text-center">
                <div className="text-[10px] text-slate-400">Rampur</div>
                <div className="text-sm font-bold text-emerald-400 mt-0.5">7 Subs</div>
                <div className="text-[9px] text-slate-500">100% Up</div>
              </div>
              <div className="bg-slate-950/50 p-2 rounded border border-slate-800 text-center">
                <div className="text-[10px] text-slate-400">Bhatpur</div>
                <div className="text-sm font-bold text-emerald-400 mt-0.5">6 Subs</div>
                <div className="text-[9px] text-slate-500">100% Up</div>
              </div>
              <div className="bg-slate-950/50 p-2 rounded border border-slate-800 text-center">
                <div className="text-[10px] text-slate-400">Daulatpur</div>
                <div className="text-sm font-bold text-emerald-400 mt-0.5">7 Subs</div>
                <div className="text-[9px] text-slate-500">100% Up</div>
              </div>
            </div>
          </div>
        ) : null}

        {/* Affected Subscribers List & Reminder Actions */}
        {impactData && impactData.affected_subscribers && impactData.affected_subscribers.length > 0 ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">
                Impacted Subscribers ({impactData.affected_subscribers.length})
              </span>
              <button
                onClick={handleBulkReminders}
                disabled={bulkSending}
                className="text-[11px] px-2 py-1 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium rounded transition-colors flex items-center gap-1"
              >
                {bulkSending ? 'Sending...' : '📢 Remind All'}
              </button>
            </div>

            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {impactData.affected_subscribers.map((sub) => {
                const state = reminderStates[sub.id];
                return (
                  <div
                    key={sub.id}
                    className="flex items-center justify-between gap-2 p-2 bg-slate-900/60 rounded border border-slate-800 text-xs hover:border-slate-700 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-white font-medium truncate">{sub.display_name}</div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                        <span className="text-amber-300">₹{sub.plan_price}/mo</span>
                        <span>·</span>
                        <span>{sub.plan}</span>
                        <span>·</span>
                        <span className="text-slate-500">{sub.village || sub.access_point_id}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleSendReminder(sub.id)}
                      disabled={state === 'sending'}
                      className={`text-[10px] px-2 py-1 rounded font-medium shrink-0 transition-colors ${
                        state === 'sent'
                          ? 'bg-emerald-900/60 border border-emerald-600 text-emerald-300'
                          : state === 'error'
                          ? 'bg-red-900/60 border border-red-600 text-red-300'
                          : state === 'sending'
                          ? 'bg-slate-700 text-slate-300'
                          : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                      }`}
                    >
                      {state === 'sent' ? '✓ Reminded' : state === 'sending' ? 'Sending...' : state === 'error' ? 'Retry' : '🔔 Remind'}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ) : !activeIncident ? (
          <div className="p-4 text-center bg-slate-900/30 rounded-lg border border-slate-800/60">
            <div className="text-2xl mb-1">🛡️</div>
            <div className="text-emerald-400 text-xs font-semibold">Zero Revenue at Risk</div>
            <div className="text-slate-500 text-[11px] mt-0.5">
              All 20 village households and commercial kiranas are receiving service normally.
            </div>
          </div>
        ) : (
          <div className="text-center py-4 text-slate-500 text-xs">
            {loading ? 'Calculating business impact...' : 'No subscribers impacted by this incident.'}
          </div>
        )}
      </div>
    </div>
  );
}

import { useState } from 'react';
import { ChevronDown, ChevronUp, History, CheckCircle2, XCircle } from 'lucide-react';
import DeliveryStatus from './DeliveryStatus';

export default function NotificationHistory({
  batches = [],
  onRetry,
  isRetrying,
}) {
  const [expandedBatchId, setExpandedBatchId] = useState(null);

  if (batches.length === 0) {
    return (
      <div className="text-center py-6 border border-slate-800 rounded-lg bg-slate-950/40 text-xs text-slate-500">
        <History className="w-5 h-5 mx-auto mb-1.5 opacity-50 text-slate-400" />
        No notification batches dispatched for this incident yet.
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
      {batches.map((batch) => {
        const isExpanded = expandedBatchId === batch.id;
        const delivs = batch.deliveries || [];
        const sentC = delivs.filter(d => d.status === 'sent' || d.status === 'delivered').length;
        const failedC = delivs.filter(d => d.status === 'failed').length;

        return (
          <div
            key={batch.id}
            className="border border-slate-800 rounded-lg bg-slate-950 overflow-hidden"
          >
            <button
              type="button"
              onClick={() => setExpandedBatchId(isExpanded ? null : batch.id)}
              className="w-full text-left p-2.5 flex items-center justify-between hover:bg-slate-900/50 transition-colors"
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs font-bold text-slate-200">
                  {batch.id}
                </span>
                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.2 rounded border ${
                  batch.kind === 'restored'
                    ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                    : 'bg-amber-950 text-amber-400 border-amber-800'
                }`}>
                  {batch.kind || 'outage'}
                </span>
                <span className="text-[10px] uppercase font-semibold px-1 rounded bg-slate-800 text-slate-400">
                  {batch.channel || 'sms'}
                </span>
                <span className="text-[10px] px-1 rounded bg-slate-800 text-slate-400">
                  {batch.provider}
                </span>
                <span className="text-slate-500 text-[10px]">
                  {batch.created_at ? new Date(batch.created_at).toLocaleTimeString() : ''}
                </span>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-emerald-400 flex items-center gap-0.5 text-[11px]">
                    <CheckCircle2 className="w-3 h-3" /> {sentC}
                  </span>
                  {failedC > 0 && (
                    <span className="text-red-400 flex items-center gap-0.5 text-[11px]">
                      <XCircle className="w-3 h-3" /> {failedC}
                    </span>
                  )}
                </div>
                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                )}
              </div>
            </button>

            {isExpanded && (
              <div className="p-3 border-t border-slate-800 bg-slate-900/30">
                <DeliveryStatus
                  deliveries={delivs}
                  onRetry={onRetry}
                  isRetrying={isRetrying}
                  batchId={batch.id}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
